"""Shared fixtures: synthetic pages and stand-in models (no weights, no network)."""

import os

import numpy as np
import pytest
from PIL import Image, ImageDraw

from anaksor import OCR


@pytest.fixture(autouse=True)
def _no_network_cache(tmp_path, monkeypatch):
    """Tests never touch the real cache or download anything."""
    monkeypatch.setenv("ANAKSOR_HOME", str(tmp_path / "cache"))
    monkeypatch.delenv("ANAKSOR_WEIGHTS_DIR", raising=False)


def page(lines, size=(800, 600), h=24):
    """White page with black bars standing in for text lines: [(x0, y0, x1), ...]."""
    img = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    for x0, y0, x1 in lines:
        d.rectangle([x0, y0, x1, y0 + h], fill="black")
    return img


class StubDetector:
    """Returns the boxes it was given (TL, TR, BR, BL) with score 0.9."""

    def __init__(self, boxes):
        self.boxes = [np.asarray(b, np.float32) for b in boxes]
        self.calls = []

    def detect(self, image, **kw):
        self.calls.append(kw)
        return {"boxes": [b.tolist() for b in self.boxes], "scores": [0.9] * len(self.boxes), "time": 0.0}


class StubRecognizer:
    """Reads every crop as ក/ខ characters, two per line height, with CTC positions."""

    max_ratio = 8
    crop_pad = (0.1, 0.05)

    def __init__(self, score=0.9):
        self.score = score
        self.sizes = []

    def recognize(self, images, positions=False):
        out = []
        for im in images:
            h, w = im.shape[:2] if isinstance(im, np.ndarray) else im.size[::-1]
            self.sizes.append((w, h))
            n = max(1, int(w / h * 2))
            chars = [("ក" if i % 2 else "ខ", (i + 0.5) / n, self.score) for i in range(n)]
            out.append({"text": "".join(c for c, _, _ in chars), "score": self.score, "chars": chars})
        return out


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


@pytest.fixture
def stub_ocr():
    def make(boxes, score=0.9, **kw):
        return OCR(StubDetector(boxes), StubRecognizer(score), **kw)

    return make


def real_weights():
    """(det, rec) weight paths from $ANAKSOR_TEST_WEIGHTS, or skip."""
    d = os.getenv("ANAKSOR_TEST_WEIGHTS")
    if not d:
        pytest.skip("set ANAKSOR_TEST_WEIGHTS to a folder with the release weights")
    det = os.path.join(d, "khmer_det_repvit_db_latest.safetensors")
    rec = os.path.join(d, "khmer_rec_svtrv2_latest.safetensors")
    return (det if os.path.exists(det) else None), (rec if os.path.exists(rec) else None)
