"""ResNet-50-DCN, the DBNet++ paper backbone (MhLiao/DB ``deformable_resnet50``).

ResNet: He et al., CVPR 2016. DCNv2: Zhu et al., CVPR 2019, arXiv:1811.11168.
Tensor names: torchvision resnet50, plus ``*.conv2_offset.*``.

    image (B, 3, H, W)
    stem      7x7/2 conv, 3x3/2 max pool          -> stride 4
    layer1    3 bottlenecks,  256 ch, plain       -> C2, stride 4
    layer2    4 bottlenecks,  512 ch, DCN         -> C3, stride 8
    layer3    6 bottlenecks, 1024 ch, DCN         -> C4, stride 16
    layer4    3 bottlenecks, 2048 ch, DCN         -> C5, stride 32
"""

from __future__ import annotations

import torch
from torch import nn


def _torchvision_ops():
    try:
        from torchvision import ops
    except ImportError as e:
        raise ImportError("the ResNet_DCN backbone needs torchvision: pip install 'anaksor-ocr[torch]'") from e
    return ops


class ModulatedDeformConv(nn.Module):
    """DCNv2 kernel: each of the k*k taps samples at its own learned offset and is scaled by a
    learned mask in [0, 1]. Offsets and mask come from the caller (the block's offset conv)."""

    def __init__(self, cin: int, cout: int, k: int = 3, stride: int = 1, padding: int = 1):
        super().__init__()
        self.stride = stride
        self.padding = padding
        self.weight = nn.Parameter(torch.empty(cout, cin, k, k))
        self.register_parameter("bias", None)  # set only when a batch norm is folded in

    def forward(self, x, offset, mask):
        return _torchvision_ops().deform_conv2d(
            x, offset, self.weight, self.bias, stride=self.stride, padding=self.padding, mask=mask
        )


class Bottleneck(nn.Module):
    """1x1 reduce -> 3x3 (stride here, torchvision style; deformable in C3-C5) -> 1x1 expand x4,
    plus the identity or a strided 1x1 projection."""

    expansion = 4

    def __init__(self, cin: int, planes: int, stride: int = 1, downsample: nn.Module | None = None, with_dcn: bool = False):
        super().__init__()
        self.with_dcn = with_dcn
        self.conv1 = nn.Conv2d(cin, planes, 1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        if with_dcn:
            self.conv2_offset = nn.Conv2d(planes, 27, 3, stride=stride, padding=1)  # 9 dy|dx pairs (18) + 9 masks
            self.conv2 = ModulatedDeformConv(planes, planes, 3, stride=stride, padding=1)
        else:
            self.conv2 = nn.Conv2d(planes, planes, 3, stride=stride, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, planes * self.expansion, 1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes * self.expansion)
        self.downsample = downsample

    def forward(self, x):
        out = torch.relu(self.bn1(self.conv1(x)))
        if self.with_dcn:
            o1, o2, mask = torch.chunk(self.conv2_offset(out), 3, dim=1)  # split as MhLiao/DB and mmcv do
            out = self.conv2(out, torch.cat([o1, o2], dim=1), torch.sigmoid(mask))
        else:
            out = self.conv2(out)
        out = torch.relu(self.bn2(out))
        out = self.bn3(self.conv3(out))
        identity = self.downsample(x) if self.downsample is not None else x
        return torch.relu(out + identity)


class ResNetDCN(nn.Module):
    """Image -> [C2, C3, C4, C5]. ``layers``: blocks per stage ((3, 4, 6, 3) is ResNet-50);
    ``stage_with_dcn``: which stages use deformable 3x3 convs."""

    def __init__(self, in_channels: int = 3, layers=(3, 4, 6, 3), stage_with_dcn=(False, True, True, True), **train_only):
        super().__init__()
        if any(stage_with_dcn):
            _torchvision_ops()
        self.inplanes = 64
        self.conv1 = nn.Conv2d(in_channels, 64, 7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.maxpool = nn.MaxPool2d(3, stride=2, padding=1)
        self.layer1 = self._make_layer(64, layers[0], 1, stage_with_dcn[0])
        self.layer2 = self._make_layer(128, layers[1], 2, stage_with_dcn[1])
        self.layer3 = self._make_layer(256, layers[2], 2, stage_with_dcn[2])
        self.layer4 = self._make_layer(512, layers[3], 2, stage_with_dcn[3])
        self.out_channels = [256, 512, 1024, 2048]

    def _make_layer(self, planes: int, blocks: int, stride: int, with_dcn: bool) -> nn.Sequential:
        downsample = None
        if stride != 1 or self.inplanes != planes * Bottleneck.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * Bottleneck.expansion, 1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * Bottleneck.expansion),
            )
        layers = [Bottleneck(self.inplanes, planes, stride, downsample, with_dcn)]
        self.inplanes = planes * Bottleneck.expansion
        layers += [Bottleneck(self.inplanes, planes, with_dcn=with_dcn) for _ in range(1, blocks)]
        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.maxpool(torch.relu(self.bn1(self.conv1(x))))
        c2 = self.layer1(x)
        c3 = self.layer2(c2)
        c4 = self.layer3(c3)
        return [c2, c3, c4, self.layer4(c4)]
