"""Box geometry: quads (4 corner points, TL, TR, BR, BL) and line crops."""

from __future__ import annotations

import cv2
import numpy as np


def order_quad(pts) -> np.ndarray:
    """Order 4 points TL, TR, BR, BL (works for rotated boxes). More points are
    reduced to their minimum-area rectangle first."""
    pts = np.asarray(pts, dtype=np.float32).reshape(-1, 2)
    if len(pts) != 4:
        pts = cv2.boxPoints(cv2.minAreaRect(pts))
    c = pts.mean(0)
    ang = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    pts = pts[np.argsort(ang)]  # clockwise in image coords, starting ~TL
    return np.roll(pts, -int(np.argmin(pts.sum(1))), axis=0)


def quad_size(q) -> tuple[float, float]:
    """(width along the top/bottom edges, height along the sides)."""
    w = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
    h = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
    return float(w), float(h)


def quad_angle(q) -> float:
    """Angle of the top edge in degrees (image coords, y down)."""
    d = q[1] - q[0]
    return float(np.degrees(np.arctan2(d[1], d[0])))


def expand_quad(q, pad_x: float, pad_y: float) -> np.ndarray:
    """Grow a TL,TR,BR,BL quad along its own axes by pad_x / pad_y pixels."""
    ux = q[1] - q[0]
    ux = ux / (np.linalg.norm(ux) + 1e-6)
    uy = q[3] - q[0]
    uy = uy / (np.linalg.norm(uy) + 1e-6)
    return np.stack(
        [
            q[0] - ux * pad_x - uy * pad_y,
            q[1] + ux * pad_x - uy * pad_y,
            q[2] + ux * pad_x + uy * pad_y,
            q[3] - ux * pad_x + uy * pad_y,
        ]
    ).astype(np.float32)


def warp_crop(img: np.ndarray, q) -> np.ndarray:
    """Perspective-warp the quad's content to an upright rectangle."""
    w, h = quad_size(q)
    w, h = max(int(round(w)), 2), max(int(round(h)), 2)
    dst = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(np.asarray(q, np.float32), dst)
    return cv2.warpPerspective(img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def drop_contained(quads, min_inside: float = 0.8) -> list[int]:
    """Indices of the boxes to keep. A box lying (at least min_inside of its area)
    inside a bigger one is dropped when it is a fragment (a detached vowel or
    subscript, much shorter) or a duplicate (same height). A line box inside a
    two-line merged box (about half its height) is kept."""
    n = len(quads)
    if n < 2:
        return list(range(n))
    q = [np.asarray(x, dtype=np.float32).reshape(4, 2) for x in quads]
    area = np.array([abs(cv2.contourArea(x)) for x in q])
    side = np.array([min(quad_size(x)) for x in q])
    lo = np.array([x.min(0) for x in q])
    hi = np.array([x.max(0) for x in q])
    drop = set()
    for i in np.argsort(area):
        if area[i] <= 0:
            continue
        cand = np.where((area > area[i]) & np.all(lo <= hi[i], 1) & np.all(hi >= lo[i], 1))[0]
        for j in cand:
            if j in drop:
                continue
            inter = cv2.intersectConvexConvex(q[i], q[j])[0]
            r = side[i] / max(side[j], 1e-6)
            if inter >= min_inside * area[i] and (r < 0.4 or r > 0.75):
                drop.add(int(i))
                break
    return [i for i in range(n) if i not in drop]


def overlap_ratio(a, b) -> float:
    """Intersection over the smaller polygon's area (0 for invalid polygons)."""
    from shapely.geometry import Polygon

    pa, pb = Polygon(a), Polygon(b)
    if not (pa.is_valid and pb.is_valid):
        return 0.0
    return float(pa.intersection(pb).area / max(min(pa.area, pb.area), 1e-6))


def line_geometry(quads) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Rotated box of a line from its quads (image coords): (bottom-left point, unit
    direction along the text, width px, height px)."""
    q0 = np.asarray(quads[0], np.float64)
    d = q0[1] - q0[0]
    n = np.linalg.norm(d)
    d = d / n if n > 1e-6 else np.array([1.0, 0.0])
    down = np.array([-d[1], d[0]])  # perpendicular, pointing down the page
    pts = np.asarray([p for q in quads for p in q], np.float64) - q0[0]
    s, t = pts @ d, pts @ down
    origin = q0[0] + d * s.min() + down * t.max()
    return origin, d, float(s.max() - s.min()), float(t.max() - t.min())
