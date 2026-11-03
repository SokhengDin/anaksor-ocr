"""Lines wider than the recogniser's input: overlapping windows stitched by CTC positions.

A window is read with about 1.5 line heights of context past each stitch, and every
Khmer cluster (a base with its subscripts, vowels and signs) is taken whole from the
window where it sits far from the edges. Cutting at blank columns instead split a
left-hand vowel such as េ from its consonant on about 8% of cuts.

Heads without per-column output (CPPD) have no character positions: their windows are
joined where the texts of neighbouring windows overlap.
"""

from __future__ import annotations

from difflib import SequenceMatcher

import cv2
import numpy as np

from .text import COENG, MARKS, normalize


def ink_profile(crop: np.ndarray) -> np.ndarray:
    """Per-column ink amount (0 = blank). Handles dark-on-light and light-on-dark."""
    g = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY) if crop.ndim == 3 else crop
    _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    border = np.concatenate([bw[0], bw[-1], bw[:, 0], bw[:, -1]])
    ink = bw > 0 if border.mean() < 127 else bw == 0  # dark background: text is the bright part
    return ink.sum(0).astype(np.float32)


def line_windows(crop: np.ndarray, max_ratio: float, overlap: float = 3.0, fill: float = 0.9):
    """Overlapping windows over a line crop.

    Returns ([(piece, x0, x1)], stitches): window i is crop[:, x0:x1]; stitches[i] is the
    column inside the overlap of windows i and i+1 (the lowest-ink column near its middle)
    where the text switches from window i to window i+1. A crop no wider than
    max_ratio * height is one window and no stitches."""
    h, w = crop.shape[:2]
    if w <= max_ratio * h:
        return [(crop, 0, w)], []
    win = min(max_ratio * h, max(fill * max_ratio * h, 2.5 * overlap * h))
    ov = min(overlap * h, 0.4 * win)  # small max_ratio: keep each window's own part
    n = int(np.ceil((w - ov) / (win - ov)))
    step = (w - ov) / n
    spans = [(int(round(i * step)), int(round(min(w, i * step + step + ov)))) for i in range(n)]
    spans[-1] = (spans[-1][0], w)
    prof = np.convolve(ink_profile(crop), np.ones(3) / 3, mode="same")
    stitches = []
    for (_, x1), (x0n, _) in zip(spans, spans[1:]):
        mid = (x0n + x1) / 2
        lo, hi = int(mid - ov / 6), int(mid + ov / 6) + 1
        seg = prof[lo:hi] + 0.01 * np.abs(np.arange(lo, hi) - mid)  # ties: nearest the middle
        stitches.append(lo + int(np.argmin(seg)))
    return [(crop[:, x0:x1], x0, x1) for x0, x1 in spans], stitches


def clusters(chars):
    """Raw CTC characters [(char, x, prob)] to Khmer clusters positioned at the base."""
    out = []
    for ch, x, p in chars:
        if out and (ch in MARKS or ch == COENG or out[-1]["chars"][-1][0] == COENG):
            out[-1]["chars"].append((ch, p))
        else:
            out.append({"x": x, "chars": [(ch, p)]})
    return out


def merge_overlapping(texts: list[str], min_match: int = 2) -> str:
    """Join the texts of overlapping windows, left to right: the longest run shared by the
    end of the text so far and the start of the next window is kept once, cut in its middle
    (both sides read the same characters there). Without a shared run they are concatenated."""
    out = texts[0] if texts else ""
    for t in texts[1:]:
        k = min(len(out), len(t))
        tail, head = out[len(out) - k :], t[:k]
        m = SequenceMatcher(None, tail, head, autojunk=False).find_longest_match(0, len(tail), 0, len(head))
        if m.size >= min_match:
            cut = m.size // 2
            out = out[: len(out) - k + m.a + cut] + t[m.b + cut :]
        else:
            out += t
    return out


def stitch(windows, stitches, results) -> tuple[str, float]:
    """Text and score of one line from its windows' recognitions: window i contributes
    the clusters whose base lies between stitches[i-1] and stitches[i]. Without character
    positions the window texts are merged on their overlap instead."""
    if any(r.get("chars") is None for r in results):
        text = normalize(merge_overlapping([r["text"] for r in results]))
        return text, float(np.mean([r["score"] for r in results])) if results else 0.0
    kept = []
    for i, ((_, x0, x1), r) in enumerate(zip(windows, results)):
        lo = stitches[i - 1] if i > 0 else -np.inf
        hi = stitches[i] if i < len(stitches) else np.inf
        for c in clusters(r.get("chars", [])):
            if lo <= x0 + c["x"] * (x1 - x0) < hi:
                kept += c["chars"]
    text = normalize("".join(ch for ch, _ in kept))
    score = float(np.mean([p for _, p in kept])) if kept else 0.0
    return text, score
