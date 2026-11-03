"""RepViT backbone for text detection.

RepViT (Wang et al., "RepViT: Revisiting Mobile CNN From ViT Perspective", CVPR 2024)
restructures a MobileNetV3-style network the way a vision transformer is laid out: every
block is a *token mixer* (a depthwise 3x3 conv, re-parameterisable as in RepVGG, plus an
optional squeeze-and-excitation gate) followed by a *channel mixer* (a residual 1x1
expand-GELU-project FFN). Downsampling blocks put a strided depthwise conv and a 1x1
projection in the token mixer instead.

The detection variant returns four feature maps at strides 4, 8, 16 and 32 for the FPN.
Inference only: the RepVGG branches are kept unfused, so the trained weights load as they are.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn

from .layers import ConvBN

# kernel, expansion, channels, squeeze-excite, (unused here), stride: one row per block
DET_STAGES = [
    (3, 2, 48, True, False, 1),
    (3, 2, 48, False, False, 1),
    (3, 2, 96, False, False, 2),
    (3, 2, 96, True, False, 1),
    (3, 2, 96, False, False, 1),
    (3, 2, 192, False, True, 2),
    (3, 2, 192, True, True, 1),
    (3, 2, 192, False, True, 1),
    (3, 2, 192, True, True, 1),
    (3, 2, 192, False, True, 1),
    (3, 2, 384, False, True, 2),
    (3, 2, 384, True, True, 1),
    (3, 2, 384, False, True, 1),
]
DET_OUT_INDICES = (2, 5, 10, 13)  # feature indices (0 is the stem) of the stride 4/8/16/32 maps


def _round_channels(v: float, divisor: int = 8) -> int:
    """Channels rounded to a multiple of ``divisor``, never more than 10% below ``v``."""
    r = max(divisor, int(v + divisor / 2) // divisor * divisor)
    return r + divisor if r < 0.9 * v else r


class SqueezeExcite(nn.Module):
    """Channel gate (Hu et al., 2018): x * sigmoid(fc2(relu(fc1(mean(x)))))."""

    def __init__(self, channels: int, ratio: float = 0.25):
        super().__init__()
        hidden = max(8, int(channels * ratio + 4) // 8 * 8)
        self.fc1 = nn.Conv2d(channels, hidden, 1)
        self.fc2 = nn.Conv2d(hidden, channels, 1)

    def forward(self, x):
        g = self.fc2(F.relu(self.fc1(x.mean((2, 3), keepdim=True))))
        return x * torch.sigmoid(g)


class RepDWConv(nn.Module):
    """RepVGG-style depthwise mixer: bn(dw3x3(x) + dw1x1(x) + x)."""

    def __init__(self, dim: int):
        super().__init__()
        self.conv = ConvBN(dim, dim, 3, 1, 1, groups=dim)
        self.conv1 = nn.Conv2d(dim, dim, 1, groups=dim)
        self.bn = nn.BatchNorm2d(dim)

    def forward(self, x):
        return self.bn(self.conv(x) + self.conv1(x) + x)


class ChannelMixer(nn.Module):
    """Residual FFN on channels: x + project(gelu(expand(x)))."""

    def __init__(self, dim: int, hidden: int):
        super().__init__()
        self.m = nn.Sequential(ConvBN(dim, hidden), nn.GELU(), ConvBN(hidden, dim))

    def forward(self, x):
        return x + self.m(x)


class RepViTBlock(nn.Module):
    def __init__(self, cin: int, cout: int, k: int, stride: int, use_se: bool):
        super().__init__()
        se = SqueezeExcite(cin) if use_se else nn.Identity()
        if stride == 1:
            if cin != cout:
                raise ValueError("a stride-1 RepViT block keeps its width")
            self.token_mixer = nn.Sequential(RepDWConv(cin), se)
        else:
            self.token_mixer = nn.Sequential(ConvBN(cin, cin, k, stride, (k - 1) // 2, groups=cin), se, ConvBN(cin, cout))
        self.channel_mixer = ChannelMixer(cout, 2 * cout)

    def forward(self, x):
        return self.channel_mixer(self.token_mixer(x))


class RepViTDet(nn.Module):
    """RepViT feature extractor returning the maps at ``out_indices``."""

    def __init__(self, in_channels: int = 3, stages=DET_STAGES, out_indices=DET_OUT_INDICES, **train_only):
        super().__init__()
        width = stages[0][2]
        stem = nn.Sequential(ConvBN(in_channels, width // 2, 3, 2, 1), nn.GELU(), ConvBN(width // 2, width, 3, 2, 1))
        layers: list[nn.Module] = [stem]
        for k, _t, c, use_se, _hs, s in stages:
            cout = _round_channels(c)
            layers.append(RepViTBlock(width, cout, k, s, use_se))
            width = cout
        self.features = nn.ModuleList(layers)
        self.out_indices = tuple(out_indices)
        self.out_channels = [stages[i - 1][2] for i in self.out_indices]

    def forward(self, x):
        outs = []
        for i, f in enumerate(self.features):
            x = f(x)
            if i in self.out_indices:
                outs.append(x)
        return outs
