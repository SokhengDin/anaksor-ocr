"""Inference-time re-parameterisation: fold batch norms and RepVGG branches into convs.

At inference a batch norm is a fixed per-channel affine map, so ``bn(conv(x))`` is one
convolution with rescaled weights and a bias. RepViT's depthwise mixer
``bn(dw3x3(x) + dw1x1(x) + x)`` is linear too: the 1x1 kernel and the identity are 3x3
kernels with a single centre tap, so the three branches add up to one 3x3 depthwise conv
(RepVGG, Ding et al., CVPR 2021). The outputs are unchanged up to float rounding; there
are fewer, larger kernels to run.

Fusing replaces modules in place, so do it after the weights are loaded. A fused model's
tensor names no longer match the checkpoints.
"""

from __future__ import annotations

import torch
from torch import nn

from .dbnet import _ProbHead
from .layers import ConvBN, ConvBNAct
from .repvit import RepDWConv
from .resnet_dcn import Bottleneck, ModulatedDeformConv, ResNetDCN


def _bn_affine(bn: nn.BatchNorm2d) -> tuple[torch.Tensor, torch.Tensor]:
    """(scale, shift) with bn(x) == scale * x + shift per channel."""
    scale = bn.weight / torch.sqrt(bn.running_var + bn.eps)
    return scale, bn.bias - bn.running_mean * scale


@torch.no_grad()
def fold_conv_bn(conv: nn.Conv2d, bn: nn.BatchNorm2d) -> nn.Conv2d:
    """One conv computing bn(conv(x))."""
    scale, shift = _bn_affine(bn)
    out = nn.Conv2d(
        conv.in_channels,
        conv.out_channels,
        conv.kernel_size,
        conv.stride,
        conv.padding,
        conv.dilation,
        conv.groups,
        bias=True,
        device=conv.weight.device,
        dtype=conv.weight.dtype,
    )
    out.weight.copy_(conv.weight * scale.reshape(-1, 1, 1, 1))
    bias = conv.bias if conv.bias is not None else torch.zeros_like(shift)
    out.bias.copy_(bias * scale + shift)
    return out


@torch.no_grad()
def fold_convt_bn(conv: nn.ConvTranspose2d, bn: nn.BatchNorm2d) -> nn.ConvTranspose2d:
    """One transposed conv computing bn(convT(x)) (output channels are weight dim 1)."""
    scale, shift = _bn_affine(bn)
    out = nn.ConvTranspose2d(
        conv.in_channels,
        conv.out_channels,
        conv.kernel_size,
        conv.stride,
        conv.padding,
        conv.output_padding,
        conv.groups,
        bias=True,
        dilation=conv.dilation,
        device=conv.weight.device,
        dtype=conv.weight.dtype,
    )
    out.weight.copy_(conv.weight * scale.reshape(1, -1, 1, 1))
    bias = conv.bias if conv.bias is not None else torch.zeros_like(shift)
    out.bias.copy_(bias * scale + shift)
    return out


@torch.no_grad()
def fold_dcn_bn(conv: ModulatedDeformConv, bn: nn.BatchNorm2d) -> ModulatedDeformConv:
    """One deformable conv computing bn(dcn(x, offset, mask))."""
    scale, shift = _bn_affine(bn)
    out = ModulatedDeformConv(conv.weight.shape[1], conv.weight.shape[0], conv.weight.shape[2], conv.stride, conv.padding)
    out.to(device=conv.weight.device, dtype=conv.weight.dtype)
    out.weight.copy_(conv.weight * scale.reshape(-1, 1, 1, 1))
    bias = conv.bias if conv.bias is not None else torch.zeros_like(shift)
    out.bias = nn.Parameter(bias * scale + shift)
    return out


def _fold_pair(m: nn.Module, conv: str, bn: str) -> None:
    c, b = getattr(m, conv), getattr(m, bn)
    if isinstance(b, nn.BatchNorm2d):
        setattr(m, conv, fold_dcn_bn(c, b) if isinstance(c, ModulatedDeformConv) else fold_conv_bn(c, b))
        setattr(m, bn, nn.Identity())


@torch.no_grad()
def fuse_rep_dw(m: RepDWConv) -> nn.Conv2d:
    """bn(dw3x3(x) + dw1x1(x) + x) as one 3x3 depthwise conv."""
    k3 = fold_conv_bn(m.conv.c, m.conv.bn)
    dim = k3.out_channels
    weight = k3.weight.clone()
    weight[:, :, 1, 1] += m.conv1.weight[:, :, 0, 0] + 1.0  # 1x1 branch and identity: centre taps
    bias = k3.bias + m.conv1.bias
    merged = nn.Conv2d(dim, dim, 3, 1, 1, groups=dim, bias=True, device=weight.device, dtype=weight.dtype)
    merged.weight.copy_(weight)
    merged.bias.copy_(bias)
    return fold_conv_bn(merged, m.bn)


def fuse(model: nn.Module) -> nn.Module:
    """Fold every batch norm that follows a conv, in place; returns ``model`` (eval only).
    Fusing an already fused model changes nothing."""
    if model.training:
        raise ValueError("fuse an eval() model: training batch norms use batch statistics")
    for name, child in list(model.named_children()):
        if isinstance(child, ConvBN):
            setattr(model, name, fold_conv_bn(child.c, child.bn))
        elif isinstance(child, RepDWConv):
            setattr(model, name, fuse_rep_dw(child))
        else:
            fuse(child)
    if isinstance(model, ConvBNAct) and isinstance(model.norm, nn.BatchNorm2d):
        model.conv = fold_conv_bn(model.conv, model.norm)
        model.norm = nn.Identity()
    elif isinstance(model, ResNetDCN):
        _fold_pair(model, "conv1", "bn1")
    elif isinstance(model, Bottleneck):
        for i in (1, 2, 3):
            _fold_pair(model, f"conv{i}", f"bn{i}")
        if model.downsample is not None and isinstance(model.downsample[-1], nn.BatchNorm2d):
            model.downsample = nn.Sequential(fold_conv_bn(model.downsample[0], model.downsample[1]))
    elif isinstance(model, _ProbHead) and isinstance(model.conv_bn1, nn.BatchNorm2d):
        model.conv1 = fold_conv_bn(model.conv1, model.conv_bn1)
        model.conv_bn1 = nn.Identity()
        model.conv2 = fold_convt_bn(model.conv2, model.conv_bn2)
        model.conv_bn2 = nn.Identity()
    return model
