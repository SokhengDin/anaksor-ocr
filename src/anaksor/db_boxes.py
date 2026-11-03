"""Text boxes from a DBNet probability map.

DBNet's inference (Liao et al., AAAI 2020, sec. 3.4): binarise the shrunk-text probability
map with a fixed threshold, take each connected region's contour, discard regions whose
mean probability is low, then *unclip*: grow the region by D = A * r / L (A area, L
perimeter, r the unclip ratio) to undo the shrinking applied to the training labels.
Each grown region becomes the minimum-area rotated rectangle around it, scaled back to
the source image.
"""

from __future__ import annotations

import cv2
import numpy as np
import pyclipper
from shapely.geometry import Polygon

MIN_SIDE = 3  # px on the probability map: smaller regions are noise


def boxes_from_map(
    prob: np.ndarray,
    src_hw: tuple[int, int],
    thresh: float = 0.3,
    box_thresh: float = 0.5,
    unclip_ratio: float = 1.5,
    max_candidates: int = 1000,
    score_mode: str = "slow",
    dilate: bool = False,
) -> tuple[list[np.ndarray], list[float]]:
    """Quads (4 x 2 int32, clockwise from top-left) and scores of the text regions in
    ``prob`` (H x W, float), in the coordinates of a ``src_hw`` image.

    score_mode "slow" averages the probability inside the region's contour, "fast"
    inside its rotated rectangle."""
    if score_mode not in ("slow", "fast"):
        raise ValueError(f"score_mode must be slow or fast, not {score_mode!r}")
    mask = (prob > thresh).astype(np.uint8)
    if dilate:
        mask = cv2.dilate(mask, np.ones((2, 2), np.uint8))
    height, width = mask.shape
    src_h, src_w = np.float64(src_hw[0]), np.float64(src_hw[1])
    contours, _ = cv2.findContours(mask * 255, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    boxes, scores = [], []
    for contour in contours[:max_candidates]:
        quad, short = _min_area_quad(contour)
        if short < MIN_SIDE:
            continue
        score = _mean_in_polygon(prob, contour.reshape(-1, 2)) if score_mode == "slow" else _mean_in_box(prob, quad)
        if score < box_thresh:
            continue
        grown = _unclip(quad, unclip_ratio)
        if len(grown) != 1:  # vanished or split: not a text line
            continue
        quad, short = _min_area_quad(np.array(grown).reshape(-1, 1, 2))
        if short < MIN_SIDE + 2:
            continue
        quad[:, 0] = np.clip(np.round(quad[:, 0] / width * src_w), 0, src_w)
        quad[:, 1] = np.clip(np.round(quad[:, 1] / height * src_h), 0, src_h)
        boxes.append(quad.astype(np.int32))
        scores.append(score)
    return boxes, scores


def _min_area_quad(points) -> tuple[np.ndarray, float]:
    """Corners of the minimum-area rectangle around ``points`` in the order top-left,
    top-right, bottom-right, bottom-left, and its shorter side."""
    rect = cv2.minAreaRect(points)
    pts = sorted(cv2.boxPoints(rect), key=lambda p: p[0])  # two left corners, then two right
    tl, bl = (pts[0], pts[1]) if pts[1][1] > pts[0][1] else (pts[1], pts[0])
    tr, br = (pts[2], pts[3]) if pts[3][1] > pts[2][1] else (pts[3], pts[2])
    return np.array([tl, tr, br, bl]), min(rect[1])


def _unclip(quad: np.ndarray, ratio: float) -> list:
    """Offset the polygon outwards by area * ratio / perimeter (round joins)."""
    poly = Polygon(quad)
    offset = pyclipper.PyclipperOffset()
    offset.AddPath(quad, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
    return offset.Execute(poly.area * ratio / poly.length)


def _mean_in_polygon(prob: np.ndarray, pts: np.ndarray) -> float:
    h, w = prob.shape
    x0, x1 = np.clip(pts[:, 0].min(), 0, w - 1), np.clip(pts[:, 0].max(), 0, w - 1)
    y0, y1 = np.clip(pts[:, 1].min(), 0, h - 1), np.clip(pts[:, 1].max(), 0, h - 1)
    return _masked_mean(prob, pts, x0, x1, y0, y1)


def _mean_in_box(prob: np.ndarray, quad: np.ndarray) -> float:
    h, w = prob.shape
    x0 = np.clip(np.floor(quad[:, 0].min()).astype(np.int32), 0, w - 1)
    x1 = np.clip(np.ceil(quad[:, 0].max()).astype(np.int32), 0, w - 1)
    y0 = np.clip(np.floor(quad[:, 1].min()).astype(np.int32), 0, h - 1)
    y1 = np.clip(np.ceil(quad[:, 1].max()).astype(np.int32), 0, h - 1)
    return _masked_mean(prob, quad, x0, x1, y0, y1)


def _masked_mean(prob, pts, x0, x1, y0, y1) -> float:
    """Mean of ``prob`` inside polygon ``pts``, over the window [y0..y1, x0..x1]."""
    mask = np.zeros((y1 - y0 + 1, x1 - x0 + 1), np.uint8)
    local = (pts - np.array([x0, y0], dtype=pts.dtype)).astype(np.int32)
    cv2.fillPoly(mask, local.reshape(1, -1, 2), 1)
    return cv2.mean(prob[y0 : y1 + 1, x0 : x1 + 1], mask)[0]
