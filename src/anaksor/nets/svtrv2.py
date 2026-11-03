"""SVTRv2 text-line encoder.

SVTRv2 (Du et al., "SVTRv2: CTC Beats Encoder-Decoder Models in Scene Text Recognition",
ICCV 2025; arXiv 2411.15858) keeps the image 2-D through three stages of *mixing blocks*:

- a conv stem ("POPE" patch embedding) downsamples by 4 with two stride-2 conv-BN-GELU;
- *local* mixing blocks use grouped convolutions (one group per head) to model strokes;
- *global* mixing blocks are post-norm multi-head self-attention over all positions;
- between stages a strided 3x3 conv merges height (2, 1) and widens the channels.

The input keeps its aspect ratio (one of a few fixed width buckets) instead of being
squashed into a fixed size, which is the paper's multi-size resizing. The output stays a
2-D map (B, C, H/8, W/4) for the RCTC and SMTR heads.
"""

from __future__ import annotations

import torch
from torch import nn

from .layers import ConvBNAct, Flatten2D, Mlp, SelfAttention


class PosEmbed2D(nn.Module):
    """Learned 2-D position embedding, cropped to the feature size."""

    def __init__(self, max_hw, dim):
        super().__init__()
        self.pos_embed = nn.Parameter(torch.zeros(1, dim, max_hw[0], max_hw[1]))

    def forward(self, x):
        return x + self.pos_embed[:, :, : x.shape[2], : x.shape[3]]


class PatchEmbed(nn.Module):
    """Conv stem: two stride-2 conv-BN-GELU, (B, 3, H, W) -> (B, dim, H/4, W/4)."""

    def __init__(self, in_channels: int, dim: int, max_hw, use_pos_embed: bool, flatten: bool, bias: bool):
        super().__init__()
        layers: list[nn.Module] = [
            ConvBNAct(in_channels, dim // 2, 3, 2, 1, bias=bias),
            ConvBNAct(dim // 2, dim, 3, 2, 1, bias=bias),
        ]
        if use_pos_embed:
            layers.append(PosEmbed2D(max_hw, dim))
        if flatten:
            layers.append(Flatten2D())
        self.patch_embed = nn.Sequential(*layers)

    def forward(self, x):
        return self.patch_embed(x)


class LocalMixing(nn.Module):
    """Local mixing block on a 2-D map: x + grouped convs, then post-norm FFN."""

    def __init__(self, dim: int, num_heads: int, kernel: int, num_conv: int, mlp_ratio: float, eps: float):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim, eps=eps)
        self.mixer = nn.Sequential(*[nn.Conv2d(dim, dim, kernel, 1, kernel // 2, groups=num_heads) for _ in range(num_conv)])
        self.norm2 = nn.LayerNorm(dim, eps=eps)
        self.mlp = Mlp(dim, int(dim * mlp_ratio))

    def forward(self, x):
        c, h, w = x.shape[1:]
        x = self.norm1((x + self.mixer(x)).flatten(2).transpose(1, 2))
        x = self.norm2(x + self.mlp(x))
        return x.transpose(1, 2).reshape(-1, c, h, w)


class GlobalMixing(nn.Module):
    """Global mixing block on tokens (B, N, C): post-norm self-attention and FFN."""

    def __init__(self, dim: int, num_heads: int, mlp_ratio: float, qkv_bias: bool, eps: float):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim, eps=eps)
        self.mixer = SelfAttention(dim, num_heads, qkv_bias)
        self.norm2 = nn.LayerNorm(dim, eps=eps)
        self.mlp = Mlp(dim, int(dim * mlp_ratio))

    def forward(self, x):
        x = self.norm1(x + self.mixer(x))
        return self.norm2(x + self.mlp(x))


class GlobalMixing2D(GlobalMixing):
    """A global mixing block that takes and returns a 2-D map."""

    def forward(self, x):
        b, c, h, w = x.shape
        x = super().forward(x.flatten(2).transpose(1, 2))
        return x.transpose(1, 2).reshape(b, c, h, w)


class Merge(nn.Module):
    """Strided 3x3 conv + LayerNorm between stages. ``tokens_in``: the stage ended on
    tokens (B, N, C) and is reshaped to 2-D first; the output keeps the input's form."""

    def __init__(self, cin: int, cout: int, stride, tokens_in: bool):
        super().__init__()
        self.conv = nn.Conv2d(cin, cout, 3, tuple(stride), 1)
        self.norm = nn.LayerNorm(cout)
        self.tokens_in = tokens_in

    def forward(self, x, hw):
        if self.tokens_in:
            x = x.transpose(1, 2).reshape(-1, x.shape[-1], hw[0], hw[1])
        x = self.conv(x)
        c, h, w = x.shape[1:]
        x = self.norm(x.flatten(2).transpose(1, 2))
        if not self.tokens_in:
            x = x.transpose(1, 2).reshape(-1, c, h, w)
        return x, (h, w)


class Stage(nn.Module):
    def __init__(self, dim, out_dim, mixer, kernels, num_convs, stride, num_heads, mlp_ratio, qkv_bias, eps):
        super().__init__()
        self.blocks = nn.Sequential()
        for kind, k, n in zip(mixer, kernels, num_convs):
            if kind == "Conv":
                self.blocks.append(LocalMixing(dim, num_heads, k, n, mlp_ratio, eps))
            elif kind in ("Global", "FGlobal"):
                if kind == "FGlobal":  # the 2-D map becomes tokens here
                    self.blocks.append(Flatten2D())
                self.blocks.append(GlobalMixing(dim, num_heads, mlp_ratio, qkv_bias, eps))
            elif kind == "FGlobalRe2D":
                self.blocks.append(GlobalMixing2D(dim, num_heads, mlp_ratio, qkv_bias, eps))
            else:
                raise ValueError(f"unknown SVTRv2 mixer {kind!r}")
        self.downsample = Merge(dim, out_dim, stride, tokens_in=mixer[-1] not in ("Conv", "FGlobalRe2D")) if out_dim else None

    def forward(self, x, hw):
        x = self.blocks(x)
        if x.dim() == 4:
            hw = tuple(x.shape[2:])
        if self.downsample is not None:
            x, hw = self.downsample(x, hw)
        return x, hw


class LastStage(nn.Module):
    """Optional 1-D head: average over height, linear, hardswish -> (B, W, out)."""

    def __init__(self, cin: int, cout: int):
        super().__init__()
        self.last_conv = nn.Linear(cin, cout, bias=False)

    def forward(self, x, hw):
        x = x.reshape(-1, hw[0], hw[1], x.shape[-1]).mean(1)
        return nn.functional.hardswish(self.last_conv(x)), (1, hw[1])


def _per_block(values, mixer, default):
    """A per-block setting, or ``default`` for every block when the list doesn't fit
    the stage (configs write [-1] for "not applicable")."""
    return list(values) if values is not None and len(values) == len(mixer) else [default] * len(mixer)


class SVTRv2(nn.Module):
    """Text-line image (B, 3, H, W) -> features: (B, C, H/8, W/4) with ``feat2d``, else
    tokens (or (B, W/4, out_channels) with ``last_stage``)."""

    def __init__(
        self,
        in_channels: int = 3,
        dims=(64, 128, 256),
        depths=(3, 6, 3),
        num_heads=(2, 4, 8),
        mixer=(("Conv",) * 3, ("Conv",) * 3 + ("Global",) * 3, ("Global",) * 3),
        sub_k=((1, 1), (2, 1), (1, 1)),
        kernel_sizes=None,
        num_convs=None,
        mlp_ratio: float = 4.0,
        qkv_bias: bool = True,
        use_pos_embed: bool = True,
        max_sz=(32, 128),
        pope_bias: bool = False,
        last_stage: bool = False,
        out_channels: int = 192,
        feat2d: bool = False,
        eps: float = 1e-6,
        **train_only,
    ):
        super().__init__()
        kernel_sizes = kernel_sizes or [[3] * len(m) for m in mixer]
        num_convs = num_convs or [[2] * 3, [2] * 3 + [3] * 3, [3] * 3]
        self.pope = PatchEmbed(
            in_channels, dims[0], (max_sz[0] // 4, max_sz[1] // 4), use_pos_embed, flatten=mixer[0][0] != "Conv", bias=pope_bias
        )
        self.stages = nn.ModuleList()
        n = len(depths)
        for i in range(n):
            self.stages.append(
                Stage(
                    dims[i],
                    dims[i + 1] if i < n - 1 else 0,
                    mixer[i],
                    _per_block(kernel_sizes[i], mixer[i], 3),
                    _per_block(num_convs[i], mixer[i], 2),
                    sub_k[i],
                    num_heads[i],
                    mlp_ratio,
                    qkv_bias,
                    eps,
                )
            )
        self.out_channels = dims[-1]
        if last_stage:  # registered under stages so its tensor names follow the checkpoints
            self.stages.append(LastStage(dims[-1], out_channels))
            self.out_channels = out_channels
        self.feat2d = feat2d

    def forward(self, x):
        hw = (x.shape[2] // 4, x.shape[3] // 4)
        x = self.pope(x)
        for stage in self.stages:
            x, hw = stage(x, hw)
        if self.feat2d and x.dim() == 3:
            x = x.transpose(1, 2).reshape(-1, x.shape[-1], hw[0], hw[1])
        return x
