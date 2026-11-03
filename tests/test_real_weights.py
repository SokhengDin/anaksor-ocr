"""Checks with the published weights: ANAKSOR_TEST_WEIGHTS=/dir/with/weights pytest -m weights"""

import pytest
from conftest import real_weights
from PIL import Image, ImageDraw, ImageFont

from anaksor import OCR, Detector, Recognizer

pytestmark = pytest.mark.weights


def text_page():
    img = Image.new("RGB", (900, 500), "white")
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=32)
    for i, line in enumerate(["INVOICE 2026", "Total 12.50 USD", "Phnom Penh"]):
        d.text((60, 60 + 120 * i), line, fill="black", font=font)
    return img


def test_detector_finds_the_lines():
    det_w, _ = real_weights()
    if det_w is None:
        pytest.skip("no detection weights")
    boxes = Detector(weights=det_w, device="cpu").detect(text_page())["boxes"]
    assert 3 <= len(boxes) <= 8


def test_full_pipeline_reads_latin_digits():
    det_w, rec_w = real_weights()
    if det_w is None or rec_w is None:
        pytest.skip("needs both weights")
    r = OCR(Detector(weights=det_w, device="cpu"), Recognizer(weights=rec_w, device="cpu"))(text_page())
    assert "2026" in r["text"] and "12.50" in r["text"]
