import argparse
import json

import pytest
from conftest import StubDetector, StubRecognizer, page, rect

import anaksor.ocr
from anaksor import cli


@pytest.fixture
def fake_ocr(monkeypatch):
    boxes = [rect(40, 40 + 40 * i, 740, 64 + 40 * i) for i in range(3)]

    class FakeOCR(anaksor.ocr.OCR):
        def __init__(self, **kw):
            super().__init__(
                StubDetector(boxes), StubRecognizer(), **{k: v for k, v in kw.items() if k in ("pad_y", "pad_x", "min_rec_score")}
            )

    monkeypatch.setattr(anaksor.ocr, "OCR", FakeOCR)
    return page([(40, 40 + 40 * i, 740) for i in range(3)])


def test_parse_pages():
    assert cli.parse_pages("1-3,5") == [1, 2, 3, 5]
    assert cli.parse_pages(None) is None
    for bad in ("0", "3-1", "x"):
        with pytest.raises(argparse.ArgumentTypeError):
            cli.parse_pages(bad)


def test_text_json_docx_pdf(tmp_path, fake_ocr, capsys):
    src = tmp_path / "scan.png"
    fake_ocr.save(src)
    assert cli.main([str(src)]) == 0
    text = capsys.readouterr().out
    assert text.count("\n") >= 3

    assert cli.main([str(src), "-f", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["file"] == str(src) and len(data["pages"][0]["lines"]) == 3

    pytest.importorskip("docx")
    pytest.importorskip("pypdfium2")
    for ext in ("docx", "pdf"):
        out = tmp_path / f"scan.{ext}"
        assert cli.main([str(src), "-o", str(out)]) == 0
        assert out.stat().st_size > 1000

    outdir = tmp_path / "out"
    assert cli.main([str(src), str(src), "-o", str(outdir), "-f", "json"]) == 0
    assert (outdir / "scan.json").is_file()


def test_errors(tmp_path, fake_ocr, capsys):
    src = tmp_path / "scan.png"
    fake_ocr.save(src)
    with pytest.raises(SystemExit):
        cli.main([str(src), "-f", "pdf"])  # pdf needs -o
    with pytest.raises(SystemExit):
        cli.main([str(tmp_path / "missing.png")])
    bad = tmp_path / "bad.gif"
    fake_ocr.save(bad, "GIF")
    assert cli.main([str(bad)]) == 1
    assert "allowed formats" in capsys.readouterr().err
