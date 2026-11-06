"""End-to-end OCR: detect lines, crop, recognise, then lines, paragraphs and reading order."""

from __future__ import annotations

import time
from collections.abc import Iterator

import cv2
import numpy as np

from .geometry import drop_contained, expand_quad, order_quad, quad_size, warp_crop
from .inputs import PDF_DPI, is_pdf, load_image, pdf_pages
from .layout import layout
from .longline import line_windows, stitch


class OCR:
    """Khmer OCR for photos, scans and PDF pages.

        import anaksor
        ocr = anaksor.OCR()                    # downloads the weights on first use
        result = ocr("page.jpg")
        print(result["text"])                  # full text in reading order
        result["blocks"]                       # paragraphs: box, text, line indices
        result["lines"]                        # lines: text, box, quads, scores

    detector / recognizer: ready ``Detector`` / ``Recognizer`` objects; by default the
    bundled models are loaded (with ``device``, ``backend``, ``det_weights``, ``rec_weights``).
    pad_y / pad_x: margin around each line before recognition, as a fraction of its
    height (default: the recognition model's own). min_rec_score: lines read with less
    confidence are dropped. try_vertical: tall boxes are also read rotated;
    try_180: every box is also read upside down.
    """

    def __init__(
        self,
        detector=None,
        recognizer=None,
        *,
        device: str = "auto",
        backend: str = "auto",
        det_weights=None,
        rec_weights=None,
        pad_y: float | None = None,
        pad_x: float | None = None,
        min_rec_score: float = 0.5,
        try_vertical: bool = True,
        try_180: bool = False,
    ):
        if detector is None:
            from .detector import Detector

            detector = Detector(weights=det_weights, device=device, backend=backend)
        if recognizer is None:
            from .recognizer import Recognizer

            recognizer = Recognizer(weights=rec_weights, device=device, backend=backend)
        self.detector, self.recognizer = detector, recognizer
        default_y, default_x = getattr(recognizer, "crop_pad", (0.04, 0.04))
        self.pad_y = default_y if pad_y is None else pad_y
        self.pad_x = default_x if pad_x is None else pad_x
        self.min_rec_score = min_rec_score
        self.try_vertical = try_vertical
        self.try_180 = try_180

    # ── recognition of the detected boxes
    def _crops(self, img, quads, pad_y, pad_x):
        """[(line index, orientation, windows, stitches)] to recognise."""
        jobs = []
        for li, q in enumerate(quads):
            w, h = quad_size(q)
            vertical = h > 1.5 * w
            short = min(w, h)
            qq = expand_quad(q, short * pad_y, short * pad_x) if vertical else expand_quad(q, short * pad_x, short * pad_y)
            crop = warp_crop(img, qq)
            if crop.shape[0] < 6 or crop.shape[1] < 6:
                continue
            variants = [("up", crop)]
            if vertical and self.try_vertical:
                # one Khmer cluster with subscripts and vowels above and below is itself
                # taller than wide (e.g. ស្ត្រី), so upright stays a candidate
                variants += [
                    ("cw", cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE)),
                    ("ccw", cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE)),
                ]
            elif self.try_180:
                variants.append(("180", cv2.rotate(crop, cv2.ROTATE_180)))
            for name, v in variants:
                wins, stitches = line_windows(v, self.recognizer.max_ratio)
                jobs.append((li, name, wins, stitches))
        return jobs

    def recognize_quads(self, img: np.ndarray, quads, pad_y=None, pad_x=None) -> dict:
        """{line index: (text, score, orientation)}, the best orientation per box."""
        pad_y = self.pad_y if pad_y is None else pad_y
        pad_x = self.pad_x if pad_x is None else pad_x
        jobs = self._crops(img, quads, pad_y, pad_x)
        pieces = [p for _, _, wins, _ in jobs for p, _, _ in wins]
        recs = iter(self.recognizer.recognize(pieces, positions=True) if pieces else [])
        out: dict[int, tuple[tuple[str, float, str], float]] = {}
        for li, name, wins, stitches in jobs:
            rs = [next(recs) for _ in wins]
            if len(wins) == 1:
                text, score = rs[0]["text"], float(rs[0]["score"])
            else:
                text, score = stitch(wins, stitches, rs)
            key = score if name == "up" else score - 0.05  # rotations must clearly win
            if li not in out or key > out[li][1]:
                out[li] = ((text, score, name), key)
        return {li: v for li, (v, _) in out.items()}

    # ── one image
    def __call__(
        self, image, *, box_thresh=None, thresh=None, unclip_ratio=None, scales=(1.0,), min_rec_score=None, pad_y=None, pad_x=None
    ) -> dict:
        """OCR one image (path, bytes, PIL image or RGB array). Returns
        {"text", "blocks", "lines", "width", "height", "time"}; coordinates are pixels of
        the image after EXIF rotation."""
        t0 = time.time()
        img = np.asarray(load_image(image))
        min_rec_score = self.min_rec_score if min_rec_score is None else min_rec_score

        det = self.detector.detect(img, box_thresh=box_thresh, thresh=thresh, unclip_ratio=unclip_ratio, scales=scales)
        t_det = time.time() - t0
        quads = [order_quad(b) for b in det["boxes"]]
        keep = [i for i, q in enumerate(quads) if min(quad_size(q)) >= 5]
        keep = [keep[k] for k in drop_contained([quads[i] for i in keep])]
        quads = [quads[i] for i in keep]
        dscores = [det["scores"][i] for i in keep]

        recs = self.recognize_quads(img, quads, pad_y, pad_x)
        t_rec = time.time() - t0 - t_det
        items = [
            {"quad": quads[li], "text": text, "rec_score": score, "det_score": dscores[li], "rotation": rot}
            for li, (text, score, rot) in sorted(recs.items())
            if text and score >= min_rec_score
        ]
        result = _assemble(layout(items))
        result.update(
            width=int(img.shape[1]),
            height=int(img.shape[0]),
            time={"det": round(t_det, 3), "rec": round(t_rec, 3), "total": round(time.time() - t0, 3)},
        )
        return result

    # ── documents
    def read_pdf(
        self, src, pages=None, dpi: int = PDF_DPI, password: str | None = None, keep_images: bool = False, **kwargs
    ) -> Iterator[dict]:
        """OCR PDF pages one by one (needs ``anaksor-ocr[pdf]``). Yields each page's
        result with "page" (from 1) and "size_pt"; "image" too when keep_images (needed
        for export)."""
        for number, img, size in pdf_pages(src, pages, dpi, password):
            result = self(img, **kwargs)
            result.update(page=number, size_pt=size)
            if keep_images:
                result["image"] = img
            yield result

    def read(self, src, pages=None, keep_images: bool = False, dpi: int = PDF_DPI, **kwargs) -> list[dict]:
        """OCR an image or a PDF; always returns a list of page results. ``pages`` and
        ``dpi`` apply to PDFs; other keywords go to ``__call__``."""
        if is_pdf(src):
            return list(self.read_pdf(src, pages, dpi=dpi, keep_images=keep_images, **kwargs))
        img = load_image(src)
        result = self(img, **kwargs)
        result["page"] = 1
        if keep_images:
            result["image"] = img
        return [result]


def _box(r):
    return [[int(r[0]), int(r[1])], [int(r[2]), int(r[1])], [int(r[2]), int(r[3])], [int(r[0]), int(r[3])]]


def _quad(q):
    return [[int(round(p[0])), int(round(p[1]))] for p in q]


def _assemble(paragraphs) -> dict:
    blocks: list[dict] = []
    lines: list[dict] = []
    for para in paragraphs:
        r = [
            min(ln["rect"][0] for ln in para),
            min(ln["rect"][1] for ln in para),
            max(ln["rect"][2] for ln in para),
            max(ln["rect"][3] for ln in para),
        ]
        lens = [max(len(ln["text"]), 1) for ln in para]
        blocks.append(
            {
                "box": _box(r),
                "boxes": [_quad(q) for ln in para for q in ln["quads"]],
                "text": "\n".join(ln["text"] for ln in para),
                "rec_score": round(float(np.average([ln["rec_score"] for ln in para], weights=lens)), 3),
                "det_score": round(float(np.mean([ln["det_score"] for ln in para])), 3),
                "lines": list(range(len(lines), len(lines) + len(para))),
            }
        )
        for ln in para:
            lines.append(
                {
                    "text": ln["text"],
                    "box": _box(ln["rect"]),
                    "quads": [_quad(q) for q in ln["quads"]],
                    "parts": ln["parts"],  # text of each quad
                    "rec_score": round(ln["rec_score"], 3),
                    "det_score": round(ln["det_score"], 3),
                    "block": len(blocks) - 1,
                }
            )
    return {"text": "\n\n".join(b["text"] for b in blocks), "blocks": blocks, "lines": lines}
