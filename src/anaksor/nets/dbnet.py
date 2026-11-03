"""DBNet text detector: RepViT backbone, RSE-FPN neck, DB head.

DBNet (Liao et al., "Real-time Scene Text Detection with Differentiable Binarization",
AAAI 2020) segments a *shrunk* text-region probability map. Training adds a threshold map
and an approximate binarisation 1 / (1 + exp(-k (P - T))) so the binarisation is learned;
at inference only the probability map is needed: it is thresholded and every region is
grown back ("unclipped") by D = A * r / L (area, unclip ratio, perimeter) to cover the text.

The neck is an FPN (Lin et al., 2017) whose lateral and output convs carry a residual
squeeze-and-excitation gate (RSE layer), as in PP-OCRv3's detector.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn

from .repvit import RepViTDet


class _SEGate(nn.Module):
    """x * hardsigmoid(conv2(relu(conv1(mean(x)))))."""

    def __init__(self, channels: int, reduction: int = 4):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels // reduction, 1)
        self.conv2 = nn.Conv2d(channels // reduction, channels, 1)

    def forward(self, x):
        g = self.conv2(F.relu(self.conv1(x.mean((2, 3), keepdim=True))))
        return x * F.hardsigmoid(g)


class RSELayer(nn.Module):
    """Conv followed by a residual SE gate: y = conv(x); y + se(y)."""

    def __init__(self, cin: int, cout: int, k: int, shortcut: bool = True):
        super().__init__()
        self.in_conv = nn.Conv2d(cin, cout, k, padding=k // 2, bias=False)
        self.se_block = _SEGate(cout)
        self.shortcut = shortcut

    def forward(self, x):
        y = self.in_conv(x)
        return y + self.se_block(y) if self.shortcut else self.se_block(y)


class RSEFPN(nn.Module):
    """Top-down FPN over 4 maps (strides 4..32); each level is reduced to out/4 channels,
    upsampled to stride 4 and concatenated, giving ``out_channels`` maps at stride 4."""

    def __init__(self, in_channels, out_channels: int = 96, shortcut: bool = True, **train_only):
        super().__init__()
        self.out_channels = out_channels
        self.ins_conv = nn.ModuleList(RSELayer(c, out_channels, 1, shortcut) for c in in_channels)
        self.inp_conv = nn.ModuleList(RSELayer(out_channels, out_channels // 4, 3, shortcut) for _ in in_channels)

    def forward(self, feats):
        lat = [conv(f) for conv, f in zip(self.ins_conv, feats)]  # strides 4, 8, 16, 32
        for i in range(len(lat) - 2, -1, -1):  # top-down: add the upsampled coarser level
            lat[i] = lat[i] + F.interpolate(lat[i + 1], scale_factor=2, mode="nearest")
        outs = [conv(m) for conv, m in zip(self.inp_conv, lat)]
        outs = [F.interpolate(o, scale_factor=2**i, mode="nearest") if i else o for i, o in enumerate(outs)]
        return torch.cat(outs[::-1], dim=1)


class _ProbHead(nn.Module):
    """3x3 conv, then two stride-2 transposed convs back to input resolution, sigmoid."""

    def __init__(self, cin: int):
        super().__init__()
        mid = cin // 4
        self.conv1 = nn.Conv2d(cin, mid, 3, padding=1, bias=False)
        self.conv_bn1 = nn.BatchNorm2d(mid)
        self.conv2 = nn.ConvTranspose2d(mid, mid, 2, stride=2)
        self.conv_bn2 = nn.BatchNorm2d(mid)
        self.conv3 = nn.ConvTranspose2d(mid, 1, 2, stride=2)

    def forward(self, x):
        x = F.relu(self.conv_bn1(self.conv1(x)))
        x = F.relu(self.conv_bn2(self.conv2(x)))
        return torch.sigmoid(self.conv3(x))


class DBHead(nn.Module):
    """Probability-map branch of the DB head. The threshold branch only matters for
    training; its tensors in a checkpoint are ignored."""

    def __init__(self, in_channels: int, **train_only):
        super().__init__()
        self.binarize = _ProbHead(in_channels)

    def forward(self, x):
        return self.binarize(x)


class DBNet(nn.Module):
    """Image (B, 3, H, W), H and W multiples of 32 -> text probability map (B, 1, H, W)."""

    def __init__(self, backbone: dict | None = None, neck: dict | None = None, head: dict | None = None, in_channels: int = 3):
        super().__init__()
        self.backbone = RepViTDet(in_channels, **(backbone or {}))
        self.neck = RSEFPN(self.backbone.out_channels, **(neck or {}))
        self.head = DBHead(self.neck.out_channels, **(head or {}))

    def forward(self, x):
        return self.head(self.neck(self.backbone(x)))
