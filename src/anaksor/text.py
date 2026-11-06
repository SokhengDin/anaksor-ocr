"""
Khmer text normalisation + the canonical recognition charset.

Why: the same rendered Khmer cluster can be typed with many code-point
sequences (vowel/shifter/coeng order, split vowels, invisible ZWSP, coeng-DA vs
coeng-TA which render identically, ...). For OCR the label must be a function of
the *pixels*, so every label (training) and every prediction (inference) goes
through `normalize()` to one canonical spelling.

    from anaksor.text import normalize, unsupported_chars, CHARSET
"""

import re
import unicodedata

# ── code points
COENG = "្"
RO = "រ"
ROBAT = "៌"
SHIFTERS = {"៉", "៊"}  # triisap
DEP_VOWELS = {chr(c) for c in range(0x17B6, 0x17C6)}  # ា .. ៅ
SIGNS = {chr(c) for c in (0x17C6, 0x17C7, 0x17C8, 0x17CB, 0x17CD, 0x17CE, 0x17CF, 0x17D0, 0x17D1, 0x17D3, 0x17DD)}
CONSONANTS = {chr(c) for c in range(0x1780, 0x17A3)}
INDEP_VOWELS = {chr(c) for c in range(0x17A3, 0x17B4)}
BASES = CONSONANTS | INDEP_VOWELS
MARKS = {ROBAT} | SHIFTERS | DEP_VOWELS | SIGNS

# split vowels that render identically to a single code point
_VOWEL_COMPOSE = {
    frozenset(("េ", "ី")): "ើ",  # េ + ី → ើ
    frozenset(("េ", "ា")): "ោ",  # េ + ា → ោ
}

# invisible / formatting characters — never visible in an image
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­឴឵"), None)

_CHAR_MAP = {
    "ឣ": "អ",  # deprecated ឣ -> អ
    "ឤ": "អា",  # deprecated ឤ -> អា
    "៘": "។ល។",  # deprecated ៘ -> ។ល។
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    "　": " ",
    "\t": " ",
    "\n": " ",
    "\r": " ",
    "‘": "'",
    "’": "'",
    "‚": "'",
    "′": "'",
    "´": "'",
    "`": "'",
    "“": '"',
    "”": '"',
    "„": '"',
    "″": '"',
    "‐": "-",
    "‑": "-",
    "‒": "-",
    "−": "-",
    "·": "•",
    "●": "•",  # middle dot / black circle -> bullet
    "…": "...",
}
_CHAR_TABLE = str.maketrans(_CHAR_MAP)
_WS = re.compile(r" {2,}")

# ── canonical charset (fixed — do NOT derive from data, so heads stay stable) ─
_KHMER = (
    [chr(c) for c in range(0x1780, 0x17A3)]  # consonants
    + [chr(c) for c in range(0x17A5, 0x17B4)]  # independent vowels (non-deprecated)
    + [chr(c) for c in range(0x17B6, 0x17D4)]  # dependent vowels, signs, coeng, bathamasat
    + ["។", "៕", "៖", "ៗ", "៙", "៚", "៛", "ៜ", "៝"]
    + [chr(c) for c in range(0x17E0, 0x17EA)]  # Khmer digits
)
_ASCII = [chr(c) for c in range(0x21, 0x7F)]  # printable ASCII minus space
_EXTRA = list("«»°×÷–—•€£¥©®±§№→✓")
CHARSET = _KHMER + _ASCII + _EXTRA  # space handled by use_space_char
CHARSET_SET = set(CHARSET) | {" "}


def _is_khmer(c: str) -> bool:
    return "ក" <= c <= "៿"


def _normalize_cluster(base, marks, unify_da):
    """Reorder the marks that follow one base: robat, coengs (Ro last), shifter, vowels, signs."""
    robat, coengs, coeng_ro, shifters, vowels, signs = [], [], [], [], [], []
    for m in marks:
        if m.startswith(COENG):
            sub = m[1]
            if unify_da and sub == "ដ":  # coeng DA renders like coeng TA
                sub = "ត"
            (coeng_ro if sub == RO else coengs).append(COENG + sub)
        elif m == ROBAT:
            robat.append(m)
        elif m in SHIFTERS:
            shifters.append(m)
        elif m in DEP_VOWELS:
            vowels.append(m)
        else:
            signs.append(m)

    def dedupe(xs):
        out = []
        for x in xs:
            if x not in out:
                out.append(x)
        return out

    vowels = dedupe(vowels)
    if len(vowels) >= 2:
        for pair, comp in _VOWEL_COMPOSE.items():
            if pair <= set(vowels):
                i = min(vowels.index(v) for v in pair)
                vowels = [v for v in vowels if v not in pair]
                vowels.insert(i, comp)
    return (
        base
        + "".join(robat[:1])
        + "".join(dedupe(coengs))
        + "".join(coeng_ro[:1])
        + "".join(shifters[:1])
        + "".join(vowels)
        + "".join(dedupe(signs))
    )


def normalize_khmer(text: str, unify_da: bool = True) -> str:
    """Canonical ordering of Khmer clusters. Non-Khmer text passes through unchanged."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c not in BASES:
            # a mark without a base (or stray coeng) — keep marks, drop dangling coeng
            if c == COENG and not (i + 1 < n and text[i + 1] in BASES):
                i += 1
                continue
            out.append(c)
            i += 1
            continue
        i += 1
        marks = []
        while i < n:
            d = text[i]
            if d == COENG:
                if i + 1 < n and text[i + 1] in BASES:
                    marks.append(d + text[i + 1])
                    i += 2
                else:  # dangling coeng — invisible, drop
                    i += 1
                continue
            if d in MARKS:
                marks.append(d)
                i += 1
                continue
            break
        out.append(_normalize_cluster(c, marks, unify_da) if marks else c)
    return "".join(out)


def normalize(text: str, unify_da: bool = True) -> str:
    """Full normalisation used for labels and predictions."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    # fullwidth ASCII (common in scraped CJK-adjacent data) -> ASCII
    text = "".join(chr(ord(c) - 0xFEE0) if "！" <= c <= "～" else c for c in text)
    text = text.translate(_INVISIBLE).translate(_CHAR_TABLE)
    if any(_is_khmer(c) for c in text):
        text = normalize_khmer(text, unify_da=unify_da)
    return _WS.sub(" ", text).strip()


def unsupported_chars(text: str) -> set:
    """Characters in `text` that the recogniser cannot output."""
    return {c for c in text if c not in CHARSET_SET}


def write_dict(path) -> int:
    """Write the canonical charset as a character dict (one char per line)."""
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(CHARSET) + "\n", encoding="utf-8")
    return len(CHARSET)
