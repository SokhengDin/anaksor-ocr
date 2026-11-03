"""SMTR head: autoregressive recognition by substring matching.

SMTR (Du et al., "Out of Length Text Recognition with Sub-String Matching", AAAI 2025)
reads a line one character at a time without a full-sequence decoder: the next character
is predicted from the *last few characters read* (a substring of length ``sub_str_len``)
and the image. A learned query attends to that substring's embeddings (plus a learned
prompt per slot; empty slots are masked), then to the visual tokens, and a linear layer
classifies the result. Because it only ever sees a short window, the head generalises to
lines longer than the training ones. ``next_mode`` reads left to right; otherwise the
mirrored "previous character" query reads right to left.

Vocabulary: 0 = end of text, 1..n the characters, then <s> (substring start, also the
fill of empty slots), and two training-only symbols and <pad>, which are never predicted.
"""

from __future__ import annotations

import math

import torch
import torch.nn.functional as F
from torch import nn

from .layers import CrossAttention


class CharEmbedding(nn.Module):
    """Token embedding scaled by sqrt(d), as in the transformer."""

    def __init__(self, vocab: int, dim: int):
        super().__init__()
        self.embedding = nn.Embedding(vocab, dim)
        self.scale = math.sqrt(dim)

    def forward(self, ids):
        return self.embedding(ids) * self.scale


class SubstringMatchLayer(nn.Module):
    """Query -> substring (prompt) attention, then query -> image attention."""

    def __init__(self, dim: int, prompt_heads: int, image_heads: int, last: bool, eps: float = 1e-6):
        super().__init__()
        self.dim = dim
        self.last = last
        self.normq1 = nn.LayerNorm(dim, eps=eps)
        self.normkv1 = nn.LayerNorm(dim, eps=eps)
        self.images_to_question_cross_attn = CrossAttention(dim, prompt_heads)
        self.normq2 = nn.LayerNorm(dim, eps=eps)
        self.normkv2 = nn.LayerNorm(dim, eps=eps)
        self.question_to_images_cross_attn = CrossAttention(dim, image_heads)

    def forward(self, query, prompt, visual, mask=None):
        query = query + self.images_to_question_cross_attn(self.normq1(query), self.normkv1(prompt), mask)
        query = query.reshape(visual.shape[0], -1, self.dim)
        query = self.question_to_images_cross_attn(self.normq2(query), self.normkv2(visual))
        return query if self.last else query.flatten(0, 1).unsqueeze(1)


class SMTRHead(nn.Module):
    """Visual tokens (B, N, C) -> (B, T, out_channels - 3) per-step probabilities, read
    greedily until every line has emitted the end symbol (index 0) or ``max_len`` + 2 steps."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        num_layer: int = 2,
        nextq2subs_head2: int | None = None,
        dynq2img_heads: int = 2,
        max_len: int = 25,
        sub_str_len: int = 5,
        next_mode: bool = True,
        ds: bool = False,
        vis_seq: int = 50,
        pos2d: bool = False,
        **train_only,
    ):
        super().__init__()
        if ds and pos2d:
            raise NotImplementedError("SMTR with a 2-D visual position embedding (pos2d) is not supported")
        dim = in_channels
        self.max_len = max_len + 3  # + end, start and padding positions
        self.sub_str_len = sub_str_len
        self.next_mode = next_mode
        self.eos = 0
        self.bos_next = out_channels - 3
        self.bos_pre = out_channels - 2
        self.ds = ds
        if not ds:  # sequence features of a fixed length get a learned position embedding
            self.vis_pos_embed = nn.Parameter(torch.zeros(1, vis_seq, dim))
        self.char_embed = CharEmbedding(out_channels, dim)
        self.cmff_decoder = nn.ModuleList(
            SubstringMatchLayer(dim, nextq2subs_head2 or dim // 32, dynq2img_heads, last=i == num_layer - 1)
            for i in range(num_layer)
        )
        self.next_token = nn.Parameter(torch.zeros(1, 1, 1, dim))
        self.pre_token = nn.Parameter(torch.zeros(1, 1, 1, dim))
        self.prompt_next_embed = nn.Parameter(torch.zeros(1, 1, sub_str_len + 1, dim))
        self.prompt_pre_embed = nn.Parameter(torch.zeros(1, 1, sub_str_len + 1, dim))
        self.norm_pred = nn.LayerNorm(dim, eps=1e-6)
        self.ques1_head = nn.Linear(dim, out_channels - 3)

    def forward(self, visual):
        if not self.ds:
            visual = visual + self.vis_pos_embed
        b = visual.shape[0]
        query, slots, bos = (
            (self.next_token, self.prompt_next_embed, self.bos_next)
            if self.next_mode
            else (self.pre_token, self.prompt_pre_embed, self.bos_pre)
        )
        query = query.expand(b, -1, -1, -1).squeeze(1)  # (B, 1, C)
        slots = slots.expand(b, -1, -1, -1).squeeze(1)  # (B, L + 1, C): query slot + L substring slots
        sub = torch.full((b, self.sub_str_len), bos, dtype=torch.long, device=visual.device)
        done = torch.zeros(b, dtype=torch.bool, device=visual.device)
        no_mask = torch.zeros(b, 1, device=visual.device)
        steps = []
        for _ in range(self.max_len - 1):
            prompt = torch.cat([slots[:, :1], slots[:, 1:] + self.char_embed(sub)], 1)
            mask = torch.cat([no_mask, torch.where(sub == bos, float("-inf"), 0.0)], 1)  # empty slots
            q = query
            for layer in self.cmff_decoder:
                q = layer(q, prompt, visual, mask.unsqueeze(1))
            probs = F.softmax(self.ques1_head(self.norm_pred(q)), -1)  # (B, 1, V)
            steps.append(probs)
            ids = probs.argmax(-1)
            done |= ids[:, 0] == self.eos
            if done.all():
                break
            sub = torch.cat([sub[:, 1:], ids], 1) if self.next_mode else torch.cat([ids, sub[:, :-1]], 1)
        return torch.cat(steps, 1)
