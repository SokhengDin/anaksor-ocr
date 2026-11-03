import io

import numpy as np
import pytest
import torch
from conftest import StubDetector, StubRecognizer, page, rect
from safetensors.torch import save_file

import anaksor
from anaksor import OCR, Detector, Recognizer, export

BOXES = [rect(40, 40 + 40 * i, 740, 64 + 40 * i) for i in range(4)] + [rect(40, 300, 1900, 324)]


def test_result_structure_and_reading_order(stub_ocr):
    ocr = stub_ocr(BOXES[:4])
    r = ocr(page([(40, 40 + 40 * i, 740) for i in range(4)]))
    assert set(r) >= {"text", "blocks", "lines", "width", "height", "time"}
    assert (r["width"], r["height"]) == (800, 600)
    assert len(r["lines"]) == 4 and len(r["blocks"]) == 1
    assert r["text"] == "\n\n".join(b["text"] for b in r["blocks"])
    assert [ln["box"][0][1] for ln in r["lines"]] == sorted(ln["box"][0][1] for ln in r["lines"])
    for ln in r["lines"]:
        assert set(ln) >= {"text", "box", "quads", "parts", "rec_score", "det_score", "block"}


def test_crop_margin_defaults_to_the_recogniser_and_can_be_overridden(stub_ocr):
    ocr = stub_ocr([rect(40, 40, 740, 80)])
    assert (ocr.pad_y, ocr.pad_x) == StubRecognizer.crop_pad
    img = page([(40, 40, 740)], h=40)
    ocr(img)
    assert ocr.recognizer.sizes[-1][1] == round(40 * (1 + 2 * 0.1))
    ocr(img, pad_y=0.3)
    assert ocr.recognizer.sizes[-1][1] == round(40 * 1.6)
    ocr(img)
    assert ocr.recognizer.sizes[-1][1] == round(40 * 1.2)  # per-call value doesn't stick


def test_low_scores_are_dropped(stub_ocr):
    assert stub_ocr(BOXES[:2], score=0.3)(page([]))["lines"] == []
    assert len(stub_ocr(BOXES[:2], score=0.3)(page([]), min_rec_score=0.2)["lines"]) == 2


def test_long_line_is_read_in_windows():
    rec = StubRecognizer()
    ocr = OCR(StubDetector([BOXES[4]]), rec)
    r = ocr(page([(40, 300, 1900)], size=(2000, 400)))
    assert len(rec.sizes) > 1  # several windows
    assert len(r["lines"]) == 1 and r["lines"][0]["text"]


def test_exports_round_trip(stub_ocr):
    pdfium = pytest.importorskip("pypdfium2")
    docx = pytest.importorskip("docx")
    ocr = stub_ocr(BOXES[:4])
    pages = ocr.read(page([(40, 40 + 40 * i, 740) for i in range(4)]), keep_images=True)
    assert anaksor.export.to_text(pages) == pages[0]["text"]

    pdf = export.to_pdf(pages, title="test")
    doc = pdfium.PdfDocument(pdf)
    layer = doc[0].get_textpage().get_text_range()
    assert [t.strip() for t in layer.split("\n") if t.strip()] == [ln["text"] for ln in pages[0]["lines"]]

    # the searchable PDF is itself an input: the 4:3 image fills A4 landscape height
    w_pt = 595.28 * 800 / 600
    again = list(ocr.read_pdf(pdf, dpi=72 * 800 / w_pt))
    assert again[0]["size_pt"] == pytest.approx((w_pt, 595.28), abs=0.1)
    assert abs(again[0]["width"] - 800) <= 1 and abs(again[0]["height"] - 600) <= 1
    assert again[0]["text"] == pages[0]["text"]

    d = docx.Document(io.BytesIO(export.to_docx(pages)))
    assert "".join(p.text for p in d.paragraphs).replace("\n", "") == pages[0]["text"].replace("\n", "")
    with pytest.raises(ValueError, match="keep_images"):
        export.to_pdf([{**pages[0], "image": None}])


@pytest.fixture(scope="module")
def random_models(tmp_path_factory):
    """The real architectures with random weights: exercises building, loading and
    inference end to end (the output text is meaningless)."""
    d = tmp_path_factory.mktemp("w")
    torch.manual_seed(0)
    from anaksor.models import load_spec
    from anaksor.nets import build_detector, build_recognizer

    det = build_detector(load_spec("det-repvit-db-v2").architecture)
    save_file({k: v.contiguous() for k, v in det.state_dict().items()}, str(d / "det.safetensors"))
    rec = build_recognizer(load_spec("rec-svtrv2-v3").architecture, ctc_classes=213, gtc_classes=217)
    save_file({k: v.contiguous() for k, v in rec.state_dict().items()}, str(d / "rec.safetensors"))
    return d / "det.safetensors", d / "rec.safetensors"


def test_real_architectures_run(random_models):
    det_w, rec_w = random_models
    rec = Recognizer("rec-svtrv2-v3", weights=rec_w, device="cpu")
    assert rec.crop_pad == (0.22, 0.20) and rec.max_ratio == 20 and len(rec.charset) == 213
    out = rec.recognize([np.full((48, 300, 3), 255, np.uint8), np.zeros((40, 40, 3), np.uint8)], positions=True)
    assert len(out) == 2 and all(isinstance(o["text"], str) and "chars" in o for o in out)
    det = Detector("det-repvit-db-v2", weights=det_w, device="cpu")
    r = OCR(det, rec, min_rec_score=0.0)(page([(40, 40, 740)]))
    assert r["width"] == 800
