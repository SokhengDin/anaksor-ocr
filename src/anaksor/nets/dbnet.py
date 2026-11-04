"""DBNet / DBNet++ text detectors (inference: probability map only).

    mobile DBNet      RepViT     + RSEFPN (96)                              + DB head
    mobile DBNet++    RepViT     + RSEFPN (96)  + ASF scale_spatial         + DB head
    paper DBNet++     ResNet-DCN + DBFPN (256)  + ASF scale_channel_spatial + DB head

DBNet: Liao et al., AAAI 2020, arXiv:1911.08947. DBNet++ / ASF: Liao et al., TPAMI 2022,
arXiv:2202.10304. FPN: Lin et al., CVPR 2017. RSE layer: PP-OCRv3, arXiv:2206.03001.
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


class ASFBlock(nn.Module):
    """Adaptive Scale Fusion (DBNet++, MhLiao/DB ``feature_attention.py``).

    3x3 conv over the concatenated [P5, P4, P3, P2] -> x (``inter`` channels)
    scale_channel_spatial only: x = x + SE(avgpool(x))         (``channel_wise``)
    spatial attention:     s = x + sigmoid(conv1x1(relu(conv3x3(mean_c(x)))))
    scale attention:       a = sigmoid(conv1x1(s)), one map per scale (4 channels)
    out = concat(a[i] * P_i), same channels as the input
    """

    def __init__(self, in_channels: int, inter_channels: int, num_scales: int = 4, attention_type: str = "scale_spatial"):
        super().__init__()
        if attention_type not in ("scale_spatial", "scale_channel_spatial"):
            raise ValueError(f"unsupported ASF attention {attention_type!r}: scale_spatial or scale_channel_spatial")
        self.conv = nn.Conv2d(in_channels, inter_channels, 3, padding=1)
        self.channel_wise = None
        if attention_type == "scale_channel_spatial":
            self.channel_wise = nn.Sequential(
                nn.Conv2d(inter_channels, inter_channels // 4, 1, bias=False),
                nn.ReLU(),
                nn.Conv2d(inter_channels // 4, inter_channels, 1, bias=False),
                nn.Sigmoid(),
            )
        self.spatial_scale = nn.Sequential(
            nn.Conv2d(1, 1, 3, padding=1, bias=False),
            nn.ReLU(),
            nn.Conv2d(1, 1, 1, bias=False),
            nn.Sigmoid(),
        )
        self.channel_scale = nn.Sequential(nn.Conv2d(inter_channels, num_scales, 1, bias=False), nn.Sigmoid())

    def forward(self, fused, scales):
        x = self.conv(fused)
        if self.channel_wise is not None:
            x = self.channel_wise(x.mean((2, 3), keepdim=True)) + x
        att = self.channel_scale(self.spatial_scale(x.mean(1, keepdim=True)) + x)
        return torch.cat([att[:, i : i + 1] * s for i, s in enumerate(scales)], dim=1)


def _fuse_levels(outs, asf: ASFBlock | None):
    """Stride-4/8/16/32 maps -> all at stride 4, concatenated coarsest first: [P5, P4, P3, P2]."""
    outs = [F.interpolate(o, scale_factor=2**i, mode="nearest") if i else o for i, o in enumerate(outs)]
    scales = outs[::-1]
    fused = torch.cat(scales, dim=1)
    return asf(fused, scales) if asf is not None else fused


class RSEFPN(nn.Module):
    """Top-down FPN over 4 maps (strides 4..32); each level is reduced to out/4 channels,
    upsampled to stride 4 and concatenated, giving ``out_channels`` maps at stride 4.
    ``use_asf``: ASF scale_spatial, out/4 inner channels."""

    def __init__(self, in_channels, out_channels: int = 96, shortcut: bool = True, use_asf: bool = False, **train_only):
        super().__init__()
        self.out_channels = out_channels
        self.ins_conv = nn.ModuleList(RSELayer(c, out_channels, 1, shortcut) for c in in_channels)
        self.inp_conv = nn.ModuleList(RSELayer(out_channels, out_channels // 4, 3, shortcut) for _ in in_channels)
        self.asf = ASFBlock(out_channels, out_channels // 4) if use_asf else None

    def forward(self, feats):
        lat = [conv(f) for conv, f in zip(self.ins_conv, feats)]  # strides 4, 8, 16, 32
        for i in range(len(lat) - 2, -1, -1):  # top-down: add the upsampled coarser level
            lat[i] = lat[i] + F.interpolate(lat[i + 1], scale_factor=2, mode="nearest")
        return _fuse_levels([conv(m) for conv, m in zip(self.inp_conv, lat)], self.asf)


class DBFPN(nn.Module):
    """DBNet paper FPN: 1x1 laterals ``in2..in5_conv``, 3x3 ``p2..p5_conv`` to out/4, ASF optional."""

    def __init__(
        self,
        in_channels,
        out_channels: int = 256,
        use_asf: bool = False,
        asf_attention: str = "scale_spatial",
        asf_inter_channels: int | None = None,
        **train_only,
    ):
        super().__init__()
        self.out_channels = out_channels
        for i, c in zip(range(2, 6), in_channels):
            setattr(self, f"in{i}_conv", nn.Conv2d(c, out_channels, 1, bias=False))
            setattr(self, f"p{i}_conv", nn.Conv2d(out_channels, out_channels // 4, 3, padding=1, bias=False))
        inter = asf_inter_channels or out_channels // 4
        self.asf = ASFBlock(out_channels, inter, attention_type=asf_attention) if use_asf else None

    def forward(self, feats):
        lat = [getattr(self, f"in{i}_conv")(f) for i, f in zip(range(2, 6), feats)]
        for i in range(len(lat) - 2, -1, -1):
            lat[i] = lat[i] + F.interpolate(lat[i + 1], scale_factor=2, mode="nearest")
        return _fuse_levels([getattr(self, f"p{i}_conv")(m) for i, m in zip(range(2, 6), lat)], self.asf)


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

    def __init__(
        self,
        backbone: dict | None = None,
        neck: dict | None = None,
        head: dict | None = None,
        in_channels: int = 3,
        backbone_name: str = "RepSVTR_det",
        neck_name: str = "RSEFPN",
    ):
        super().__init__()
        if backbone_name == "ResNet_DCN":
            from .resnet_dcn import ResNetDCN

            self.backbone = ResNetDCN(in_channels, **(backbone or {}))
        else:
            self.backbone = RepViTDet(in_channels, **(backbone or {}))
        neck_cls = DBFPN if neck_name == "DBFPN" else RSEFPN
        self.neck = neck_cls(self.backbone.out_channels, **(neck or {}))
        self.head = DBHead(self.neck.out_channels, **(head or {}))

    def forward(self, x):
        return self.head(self.neck(self.backbone(x)))
