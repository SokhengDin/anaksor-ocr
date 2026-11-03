"""Charsets and decoding of the recogniser's outputs into text."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CTC_BLANK = "blank"
SMTR_EOS, SMTR_BOS, SMTR_PAD = "</s>", "<s>", "<pad>"
SMTR_SPECIAL_TAIL = [SMTR_BOS, "<INF>", "<INB>", SMTR_PAD]  # after the characters; the middle two are training-only


def read_dict(path, use_space_char: bool = True) -> list[str]:
    """One character per line (UTF-8), optionally followed by the space character."""
    with open(path, "rb") as f:
        chars = [line.decode("utf-8").strip("\n").strip("\r\n") for line in f]
    if use_space_char:
        chars.append(" ")
    return chars


@dataclass(frozen=True)
class Charset:
    chars: list[str]

    @property
    def ctc(self) -> list[str]:
        """CTC classes: the blank (index 0), then the characters."""
        return [CTC_BLANK, *self.chars]

    @property
    def cppd(self) -> list[str]:
        """CPPD classes: end of text (index 0), then the characters."""
        return [SMTR_EOS, *self.chars]

    @property
    def smtr(self) -> list[str]:
        """SMTR classes: end of text (index 0), the characters, then the special symbols."""
        return [SMTR_EOS, *self.chars, *SMTR_SPECIAL_TAIL]


def ctc_greedy(probs: np.ndarray, classes: list[str]) -> list[tuple[str, float]]:
    """Best-path CTC decoding (Graves et al., 2006) of (B, T, C) probabilities: the most
    likely class per frame, repeats merged, blanks dropped. The score is the mean
    probability of the kept frames (0 for an empty result)."""
    ids, best = probs.argmax(2), probs.max(2)
    out = []
    for row, p in zip(ids, best):
        keep = row != 0
        keep[1:] &= row[1:] != row[:-1]
        text = "".join(classes[i] for i in row[keep])
        out.append((text, float(np.mean(p[keep])) if keep.any() else 0.0))
    return out


def smtr_greedy(probs: np.ndarray, classes: list[str], reverse: bool = False) -> list[tuple[str, float]]:
    """Text of (B, T, V) SMTR step probabilities, up to the first end symbol. ``reverse``
    for a head that read right to left."""
    ids, best = probs.argmax(2), probs.max(2)
    out = []
    for row, p in zip(ids, best):
        chars, conf = [], []
        for i, pr in zip(row, p):
            if i >= len(classes):
                continue
            c = classes[i]
            if c == SMTR_EOS:
                break
            if c in (SMTR_BOS, SMTR_PAD):
                continue
            chars.append(c)
            conf.append(pr)
        text = "".join(chars[::-1] if reverse else chars)
        out.append((text, float(np.mean(conf)) if conf else 0.0))
    return out


def cppd_greedy(probs: np.ndarray, classes: list[str]) -> list[tuple[str, float]]:
    """Text of (B, L, C) CPPD position probabilities: the best class per position, up to
    the first end symbol. Score: mean probability of the characters (0 if none)."""
    ids, best = probs.argmax(2), probs.max(2)
    out = []
    for row, p in zip(ids, best):
        end = int(np.argmax(row == 0)) if (row == 0).any() else len(row)
        text = "".join(classes[i] for i in row[:end])
        out.append((text, float(np.mean(p[:end])) if end else 0.0))
    return out


def ctc_positions(probs: np.ndarray, classes: list[str]) -> list[list[tuple[str, float, float]]]:
    """Per line, the characters of the best path with their horizontal position: the
    centre of each run of frames as a fraction of the width (CTC frames tile the resized
    width evenly), and the run's highest probability."""
    ids, best = probs.argmax(2), probs.max(2)
    out = []
    for row, p in zip(ids, best):
        n, seq, t = len(row), [], 0
        while t < n:
            e = t
            while e + 1 < n and row[e + 1] == row[t]:
                e += 1
            if row[t] != 0:
                seq.append((classes[row[t]], (t + e + 1) / 2 / n, float(p[t : e + 1].max())))
            t = e + 1
        out.append(seq)
    return out
