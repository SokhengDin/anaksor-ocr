"""CPPD head: parallel (non-autoregressive) decoding with character-position queries.

CPPD (Du et al., "Context Perception Parallel Decoder for Scene Text Recognition",
TPAMI 2025) predicts every character of a line at once. One learned query per output
position (a position embedding plus a learned offset) reads the visual tokens; a
recognition layer then lets those position queries attend to the visual tokens refined
by a separate stack, and a linear layer classifies each position. During training, two
side tasks shape the queries: character *counting* (one query per class: how often does
it occur) and character *ordering* (which position holds which character); their layers
are not needed to read text.

Output: (B, max_len + 1, classes) probabilities; class 0 ends the text.
"""

from __future__ import annotations

import math

import torch
import torch.nn.functional as F
from torch import nn

from .layers import CrossAttention, Mlp


class PostNormCrossBlock(nn.Module):
    """norm(q + attn(q, kv)), then norm(x + mlp(x))."""

    def __init__(self, dim: int, num_heads: int, scale: float | None = None, eps: float = 1e-6):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim, eps=eps)
        self.mixer = CrossAttention(dim, num_heads, qkv_bias=True, scale=scale)
        self.norm2 = nn.LayerNorm(dim, eps=eps)
        self.mlp = Mlp(dim, dim * 4)

    def forward(self, q, kv, mask=None):
        x = self.norm1(q + self.mixer(q, kv, mask))
        return self.norm2(x + self.mlp(x))


class PositionEmbedding(nn.Module):
    """Embedding table scaled by sqrt(d) (transformer convention)."""

    def __init__(self, n: int, dim: int):
        super().__init__()
        self.embedding = nn.Embedding(n, dim)
        self.scale = math.sqrt(dim)

    def forward(self, ids):
        return self.embedding(ids) * self.scale


class CPPDHead(nn.Module):
    """Visual tokens (B, N, C) -> (B, max_len + 1, out_channels) probabilities."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        num_layer: int = 2,
        rec_layer: int = 1,
        max_len: int = 25,
        num_heads: int | None = None,
        ds: bool = False,
        vis_seq: int = 50,
        **train_only,
    ):
        super().__init__()
        dim = in_channels
        heads = num_heads or dim // 32
        self.max_len = max_len + 1  # + end of text
        self.ds = ds
        if not ds:
            self.vis_pos_embed = nn.Parameter(torch.zeros(1, vis_seq, dim))
        self.pos_node_embed = PositionEmbedding(self.max_len, dim)
        self.char_pos_embed = nn.Parameter(torch.zeros(1, self.max_len, dim))
        # visual refinement for the recognition layer, and the position-query stack
        self.char_node_decoder = nn.ModuleList(PostNormCrossBlock(dim, heads) for _ in range(num_layer))
        self.pos_node_decoder = nn.ModuleList(PostNormCrossBlock(dim, heads) for _ in range(num_layer))
        # recognition layers alternate: (rec_layer + i) odd -> queries read the visual tokens
        # (unscaled dot product); even -> causal self-attention among the position queries
        self.edge_decoder = nn.ModuleList(
            PostNormCrossBlock(dim, heads, scale=1.0 if (rec_layer + i) % 2 else None) for i in range(rec_layer)
        )
        self.edge_fc = nn.Linear(dim, out_channels)
        causal = torch.full((self.max_len, self.max_len), float("-inf")).triu(1)
        self.register_buffer("causal_mask", causal.unsqueeze(0), persistent=False)

    def forward(self, visual):
        if not self.ds:
            visual = visual + self.vis_pos_embed
        b = visual.shape[0]
        pos = self.pos_node_embed(torch.arange(self.max_len, device=visual.device)).unsqueeze(0) + self.char_pos_embed
        vis = visual
        pos_vis = torch.cat([pos.expand(b, -1, -1), visual], 1)
        for char_layer, pos_layer in zip(self.char_node_decoder, self.pos_node_decoder):
            vis = char_layer(vis, vis)
            pos_vis = pos_layer(pos_vis, pos_vis[:, self.max_len :])
        q = pos_vis[:, : self.max_len]
        n = len(self.edge_decoder)
        for i, layer in enumerate(self.edge_decoder):
            q = layer(q, vis) if (n + i) % 2 else layer(q, q, self.causal_mask)
        return F.softmax(self.edge_fc(q), -1)
