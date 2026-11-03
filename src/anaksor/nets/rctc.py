"""RCTC head: CTC over a 2-D feature map (SVTRv2, sec. 3.3).

A plain CTC head pools the height of the feature map before classifying each column,
which blurs characters that sit above or below each other: in Khmer that is a consonant
and its subscript (coeng) or a vowel sign. SVTRv2's rotation-robust CTC head first lets
each row attend along its width (a transformer block), then, per column, weights the
rows with attention from a learned character query before classifying. The output is a
CTC distribution for each of the W columns.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn

from .layers import PreNormBlock


class RCTCHead(nn.Module):
    """(B, C, H, W) features -> (B, W, num_classes) CTC probabilities (index 0 = blank)."""

    def __init__(self, in_channels: int, out_channels: int, **train_only):
        super().__init__()
        self.char_token = nn.Parameter(torch.zeros(1, 1, in_channels))
        self.fc = nn.Linear(in_channels, out_channels)
        self.fc_kv = nn.Linear(in_channels, 2 * in_channels)
        self.w_atten_block = PreNormBlock(in_channels, in_channels // 32, qkv_bias=False)

    def logits(self, x):
        b, c, h, w = x.shape
        rows = self.w_atten_block(x.permute(0, 2, 3, 1).reshape(b * h, w, c))  # each row along its width
        k, v = self.fc_kv(rows.reshape(b, h * w, c)).reshape(b, h * w, 2, c).permute(2, 0, 3, 1).unbind(0)
        attn = (self.char_token.expand(b, -1, -1) @ k).reshape(b, 1, h, w)  # score of every position
        attn = F.softmax(attn, dim=2).permute(0, 3, 1, 2)  # over the rows of each column: (B, W, 1, H)
        cols = (attn @ v.reshape(b, c, h, w).permute(0, 3, 2, 1)).squeeze(2)  # (B, W, C)
        return self.fc(cols)

    def forward(self, x):
        return F.softmax(self.logits(x), dim=2)
