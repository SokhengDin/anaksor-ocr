"""Reading order: recognised boxes to lines to paragraphs.

1. Deskew: geometry is analysed in a frame rotated by the page's dominant text angle
   (a 2 degree phone photo makes neighbouring lines' rectangles overlap otherwise).
2. Columns first: a recursive XY-cut over the boxes. A vertical cut is taken only when
   both sides are text columns: several lines each, much wider than the gutter. A
   receipt's label and price fail that test, so the price stays on its label's line.
3. Lines inside each region: boxes are taken left to right and each joins the line
   whose centre line is closest (tight Khmer leading makes boxes of adjacent lines
   overlap, so a pairwise union would chain a whole paragraph into one line).
4. Paragraphs: consecutive lines that are close, of similar size and aligned.
"""

from __future__ import annotations

import numpy as np

from .geometry import quad_angle, quad_size

# characters of numbers, prices, dates and phone numbers (Latin and Khmer digits)
_NUMERIC = set("0123456789០១២៣៤៥៦៧៨៩.,:;/-+()%$៛€£¥#*")


def layout(items: list[dict]) -> list[list[dict]]:
    """items ({"quad", "text", "rec_score", "det_score"}) to paragraphs (lists of line
    dicts) in reading order. Each line has text, rect, quads, parts and scores."""
    if not items:
        return []
    sizes = [quad_size(it["quad"]) for it in items]
    angles = [quad_angle(it["quad"]) for it, (w, h) in zip(items, sizes) if w > 2 * h]
    skew = float(np.median(angles)) if angles else 0.0
    if abs(skew) > 30:  # rotated page / vertical script: no deskew
        skew = 0.0
    c, s = np.cos(np.radians(skew)), np.sin(np.radians(skew))
    rot = np.array([[c, s], [-s, c]], dtype=np.float32)  # rotates the text direction onto +x
    for it, (w, h) in zip(items, sizes):
        q = it["quad"]
        lq = q @ rot.T
        it["rect"] = [float(q[:, 0].min()), float(q[:, 1].min()), float(q[:, 0].max()), float(q[:, 1].max())]
        it["lrect"] = [float(lq[:, 0].min()), float(lq[:, 1].min()), float(lq[:, 0].max()), float(lq[:, 1].max())]
        it["tilted"] = abs(quad_angle(q) - skew) > 12
        # line height is the side across the text direction; a lone digit or Khmer
        # cluster is narrower than tall, so min(w, h) would halve it
        it["h"] = min(w, h) if it["tilted"] else h
    mh = float(np.median([it["h"] for it in items]))
    lines = [_line(row) for reg in _regions(items, mh) for row in _rows(reg)]
    return _paragraphs(lines)


# ── regions (XY-cut)
def _gaps(lo, hi):
    """Empty intervals of a projection [(gap, cut position)], largest first."""
    order = np.argsort(lo)
    out, reach = [], hi[order[0]]
    for k in order[1:]:
        if lo[k] > reach:
            out.append((lo[k] - reach, (reach + lo[k]) / 2))
        reach = max(reach, hi[k])
    return sorted(out, reverse=True)


def _row_widths(items):
    """Quick row clustering by vertical centre to the width of each row. Boxes are
    often single words, so a column test must look at rows, not boxes."""
    its = sorted(items, key=lambda it: (it["lrect"][1] + it["lrect"][3]) / 2)
    rows, cur, cy = [], [], None
    for it in its:
        y = (it["lrect"][1] + it["lrect"][3]) / 2
        if cur and abs(y - cy) > 0.5 * it["h"]:
            rows.append(cur)
            cur = []
        cur.append(it)
        cy = np.mean([(c["lrect"][1] + c["lrect"][3]) / 2 for c in cur])
    if cur:
        rows.append(cur)
    return [max(c["lrect"][2] for c in r) - min(c["lrect"][0] for c in r) for r in rows]


def _mostly_numeric(items) -> bool:
    """Prices, dates, phone numbers: a receipt's value column, not running text."""
    s = "".join(it["text"] for it in items).replace(" ", "")
    return bool(s) and sum(ch in _NUMERIC for ch in s) / len(s) >= 0.6


def _is_columns(left, right, gap, mh) -> bool:
    if len(left) < 2 or len(right) < 2:
        return False
    if _mostly_numeric(left) or _mostly_numeric(right):
        return False
    wl, wr = _row_widths(left), _row_widths(right)
    if len(wl) < 2 or len(wr) < 2:
        return False
    w = min(np.median(wl), np.median(wr))
    if w < 3 * mh:  # a few words per side: a table or form, read by rows
        return False
    # Narrow gutter, or a wide one between two real blocks of lines (dictionary pages
    # and ragged columns have short lines and a gutter wider than them).
    return bool(w >= 2.5 * gap or min(len(wl), len(wr)) >= 3)


def _regions(items, mh, depth=0):
    if len(items) <= 1 or depth > 200:
        return [items]
    r = np.array([it["lrect"] for it in items], dtype=np.float64)
    for gap, x in _gaps(r[:, 0], r[:, 2])[:3]:
        if gap < 0.6 * mh:
            break
        left = [it for it in items if it["lrect"][2] <= x]
        right = [it for it in items if it["lrect"][2] > x]
        if _is_columns(left, right, gap, mh):
            return _regions(left, mh, depth + 1) + _regions(right, mh, depth + 1)
    gy = _gaps(r[:, 1], r[:, 3])
    if gy:
        y = gy[0][1]
        top = [it for it in items if it["lrect"][3] <= y]
        bot = [it for it in items if it["lrect"][3] > y]
        return _regions(top, mh, depth + 1) + _regions(bot, mh, depth + 1)
    return [items]


# ── lines
def _vertical_overlap(a, b) -> float:
    """Overlap of y-ranges relative to the smaller height."""
    inter = min(a[3], b[3]) - max(a[1], b[1])
    return inter / max(min(a[3] - a[1], b[3] - b[1]), 1e-6)


def _rows(items):
    """Grow lines left to right; return them top to bottom, boxes left to right.

    Each box joins the line whose last box it sits right of (sharing that box's band)
    and whose median centre line is closest, else starts a new line."""
    lines = []  # [members, centres, heights]
    for it in sorted(items, key=lambda it: it["lrect"][0]):
        x0, y0, x1, y1 = it["lrect"]
        cy, best, best_d = (y0 + y1) / 2, None, None
        if not it["tilted"]:
            for ln in lines:
                last = ln[0][-1]
                if last["tilted"]:
                    continue
                lx0, _, lx1, _ = last["lrect"]
                vov = _vertical_overlap(last["lrect"], it["lrect"])
                ratio = max(it["h"], last["h"]) / max(min(it["h"], last["h"]), 1e-6)
                # similar heights, or a small box (price, time) well inside a taller line's
                # band (stacked subscripts make some boxes much taller)
                if vov < 0.5 or ratio >= 3.0 or (ratio >= 2.0 and vov < 0.8):
                    continue
                h = max(it["h"], float(np.median(ln[2])))
                d = abs(cy - float(np.median(ln[1]))) / h
                if lx1 - x0 > 0.3 * min(x1 - x0, lx1 - lx0) and not (vov >= 0.8 and d < 0.25):
                    continue  # overlaps the line's end: stacked, not next
                if d < 0.5 and (best_d is None or d < best_d):
                    best, best_d = ln, d
        if best is None:
            lines.append([[it], [cy], [it["h"]]])
        else:
            best[0].append(it)
            best[1].append(cy)
            best[2].append(it["h"])
    return sorted(
        (ln[0] for ln in lines), key=lambda row: float(np.median([(it["lrect"][1] + it["lrect"][3]) / 2 for it in row]))
    )


def _line(boxes) -> dict:
    # DBNet only splits a line at a clear blank run (spacing inside a Khmer word never
    # separates boxes), so separate boxes on one line are separate words: join with a space.
    lens = [max(len(i["text"]), 1) for i in boxes]
    return {
        "text": " ".join(i["text"] for i in boxes if i["text"]).strip(),
        "rect": [
            min(i["rect"][0] for i in boxes),
            min(i["rect"][1] for i in boxes),
            max(i["rect"][2] for i in boxes),
            max(i["rect"][3] for i in boxes),
        ],
        "lrect": [
            min(i["lrect"][0] for i in boxes),
            min(i["lrect"][1] for i in boxes),
            max(i["lrect"][2] for i in boxes),
            max(i["lrect"][3] for i in boxes),
        ],
        "h": float(np.median([i["h"] for i in boxes])),
        "quads": [i["quad"] for i in boxes],
        "parts": [i["text"] for i in boxes],
        "rec_score": float(np.average([i["rec_score"] for i in boxes], weights=lens)),
        "det_score": float(np.mean([i["det_score"] for i in boxes])),
    }


# ── paragraphs
def _paragraphs(lines):
    """Consecutive lines (reading order) to paragraphs."""
    blocks = []
    for ln in lines:
        if blocks:
            last = blocks[-1][-1]
            a, b = last["lrect"], ln["lrect"]
            h = max(ln["h"], last["h"])
            gap = b[1] - a[3]
            xov = min(a[2], b[2]) - max(a[0], b[0])
            aligned = abs(b[0] - a[0]) < 1.5 * h
            similar = 0.7 < ln["h"] / max(last["h"], 1e-6) < 1.4
            if -0.3 * h < gap < 0.9 * h and similar and (xov > 0 or aligned):
                blocks[-1].append(ln)
                continue
        blocks.append([ln])
    return blocks
