"""Building blocks shared by the detection and recognition networks.

Module and parameter names are part of the weights format: they spell the tensor names
of the checkpoints trained in Alpha-OCR, so renaming an attribute breaks loading.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn


class ConvBN(nn.Sequential):
    """Convolution without bias followed by batch norm (children ``c`` and ``bn``)."""

    def __init__(self, cin: int, cout: int, k: int = 1, stride: int | tuple = 1, pad: int = 0, groups: int = 1):
        super().__init__()
        self.c = nn.Conv2d(cin, cout, k, stride, pad, groups=groups, bias=False)
        self.bn = nn.BatchNorm2d(cout)


class ConvBNAct(nn.Module):
    """Convolution, batch norm, GELU (children ``conv`` and ``norm``)."""

    def __init__(self, cin: int, cout: int, k: int = 3, stride: int = 1, pad: int = 0, bias: bool = False):
        super().__init__()
        self.conv = nn.Conv2d(cin, cout, k, stride, pad, bias=bias)
        self.norm = nn.BatchNorm2d(cout)

    def forward(self, x):
        return F.gelu(self.norm(self.conv(x)))


class Mlp(nn.Module):
    """Two-layer feed-forward network with GELU (Vaswani et al., 2017)."""

    def __init__(self, dim: int, hidden: int):
        super().__init__()
        self.fc1 = nn.Linear(dim, hidden)
        self.fc2 = nn.Linear(hidden, dim)

    def forward(self, x):
        return self.fc2(F.gelu(self.fc1(x)))


class SelfAttention(nn.Module):
    """Multi-head self-attention over tokens (B, N, C) with a fused qkv projection."""

    def __init__(self, dim: int, num_heads: int, qkv_bias: bool = True):
        super().__init__()
        self.num_heads = num_heads
        self.qkv = nn.Linear(dim, dim * 3, bias=qkv_bias)
        self.proj = nn.Linear(dim, dim)

    def forward(self, x):
        b, n, c = x.shape
        q, k, v = self.qkv(x).reshape(b, n, 3, self.num_heads, c // self.num_heads).permute(2, 0, 3, 1, 4).unbind(0)
        x = F.scaled_dot_product_attention(q, k, v)  # softmax(q k^T / sqrt(d)) v
        return self.proj(x.transpose(1, 2).reshape(b, n, c))


class CrossAttention(nn.Module):
    """Multi-head attention of queries (B, Q, C) over keys/values (B, N, C), with an
    optional additive mask broadcast over the heads. ``scale`` defaults to 1/sqrt(head dim)."""

    def __init__(self, dim: int, num_heads: int, qkv_bias: bool = True, scale: float | None = None):
        super().__init__()
        self.num_heads = num_heads
        self.scale = scale or (dim // num_heads) ** -0.5
        self.q = nn.Linear(dim, dim, bias=qkv_bias)
        self.kv = nn.Linear(dim, dim * 2, bias=qkv_bias)
        self.proj = nn.Linear(dim, dim)

    def forward(self, q, kv, mask=None):
        b, n, c = kv.shape
        nq, hd = q.shape[1], c // self.num_heads
        q = self.q(q).reshape(-1, nq, self.num_heads, hd).transpose(1, 2) * self.scale
        k, v = self.kv(kv).reshape(-1, n, 2, self.num_heads, hd).permute(2, 0, 3, 1, 4)
        attn = q @ k.transpose(2, 3)
        if mask is not None:
            attn = attn + mask.unsqueeze(1)
        x = (F.softmax(attn, -1) @ v).transpose(1, 2).reshape(-1, nq, c)
        return self.proj(x)


class PreNormBlock(nn.Module):
    """Transformer block, pre-norm (ViT layout): x + attn(norm(x)), x + mlp(norm(x))."""

    def __init__(self, dim: int, num_heads: int, mlp_ratio: float = 4.0, qkv_bias: bool = False, eps: float = 1e-5):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim, eps=eps)
        self.attn = SelfAttention(dim, num_heads, qkv_bias)
        self.norm2 = nn.LayerNorm(dim, eps=eps)
        self.mlp = Mlp(dim, int(dim * mlp_ratio))

    def forward(self, x):
        x = x + self.attn(self.norm1(x))
        return x + self.mlp(self.norm2(x))


class Flatten2D(nn.Module):
    """(B, C, H, W) -> (B, H*W, C). No parameters; it holds a slot in a block list."""

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x.flatten(2).transpose(1, 2)
