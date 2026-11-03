"""ONNX export and the onnx backend: same boxes and text as the torch backend, no torch needed."""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import torch
import yaml
from safetensors.torch import save_file

pytest.importorskip("onnxruntime")
pytest.importorskip("onnx")
pytest.importorskip("onnxscript")

from anaksor import OCR, Detector, Recognizer  # noqa: E402
from anaksor.models import WeightsError, data_path, load_spec, resolve_weights  # noqa: E402
from anaksor.nets import build_detector, build_recognizer  # noqa: E402
from anaksor.onnx_export import export_onnx  # noqa: E402

TINY_ENCODER = {
    "name": "SVTRv2LNConvTwo33",
    "use_pos_embed": False,
    "dims": [32, 64, 96],
    "depths": [2, 3, 1],
    "num_heads": [1, 2, 3],
    "mixer": [["Conv", "Conv"], ["Conv", "FGlobal", "Global"], ["Global"]],
    "sub_k": [[1, 1], [2, 1], [-1, -1]],
}
HEADS = {
    "gtc": {
        "name": "GTCDecoder",
        "infer_gtc": True,
        "gtc_decoder": {"name": "SMTRDecoder", "num_layer": 1, "ds": True, "max_len": 30, "next_mode": True, "sub_str_len": 5},
        "ctc_decoder": {"name": "RCTCDecoder"},
    },
    "cppd": {"name": "CPPDDecoder", "ds": True, "num_layer": 1, "rec_layer": 1, "max_len": 30},
}


def tiny_rec(tmp: Path, head: str) -> tuple[Path, Path]:
    """A small recogniser spec + weights: the real code paths, quick to export."""
    base = load_spec("rec-svtrv2-v3").config
    encoder = {**TINY_ENCODER, "feat2d": head != "cppd"}
    arch = {"in_channels": 3, "Encoder": encoder, "Decoder": HEADS[head]}
    spec = {**base, "name": f"rec-tiny-{head}", "architecture": arch, "weights": {"file": f"tiny_{head}.safetensors"}}
    spec["charset"] = {**base["charset"], "dict": str(data_path(base["charset"]["dict"]))}
    path = tmp / f"rec-tiny-{head}.yml"
    path.write_text(yaml.safe_dump(spec, allow_unicode=True))
    torch.manual_seed(1)
    net = build_recognizer(arch, ctc_classes=213, gtc_classes=217, cppd_classes=213)
    with torch.no_grad():  # move batch norm statistics off their identity init
        for m in net.modules():
            if isinstance(m, torch.nn.BatchNorm2d):
                m.running_mean.normal_(0, 0.1)
                m.running_var.uniform_(0.5, 1.5)
    save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(tmp / f"tiny_{head}.safetensors"))
    return path, tmp / f"tiny_{head}.safetensors"


def page(lines=((40, 40, 700), (40, 140, 1500), (60, 260, 420))) -> np.ndarray:
    img = np.full((400, 1600, 3), 255, np.uint8)
    for x, y, w in lines:
        img[y : y + 30, x : x + w] = 30
        img[y + 8 : y + 22, x + 10 : x + w - 10 : 25] = 255  # gaps, like letters
    return img


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    d = tmp_path_factory.mktemp("onnx")
    from anaksor.models import load_into  # noqa: F401  (weights go through the normal loader)

    torch.manual_seed(0)
    det_net = build_detector(load_spec("det-repvit-db-v2").architecture)
    save_file({k: v.contiguous() for k, v in det_net.state_dict().items()}, str(d / "det.safetensors"))
    out = {"det": (load_spec("det-repvit-db-v2").source, d / "det.safetensors")}
    for head in ("gtc", "cppd"):
        out[head] = tiny_rec(d, head)
    for key, (spec, w) in out.items():
        model = (Detector if key == "det" else Recognizer)(spec, weights=w, device="cpu", backend="torch")
        r = export_onnx(model, d / f"{key}.onnx")
        assert r["max_diff"] < 1e-4
    return d, out


def test_detector_same_boxes(exported):
    d, out = exported
    spec, w = out["det"]
    a = Detector(spec, weights=w, device="cpu", backend="torch")
    b = Detector(spec, weights=d / "det.onnx", device="cpu")  # auto: .onnx -> onnx backend
    assert b.backend == "onnx" and b.model is None
    img = page()
    ra, rb = a.detect(img), b.detect(img)
    assert ra["boxes"] == rb["boxes"] and np.allclose(ra["scores"], rb["scores"], atol=1e-5)


@pytest.mark.parametrize("head", ["gtc", "cppd"])
def test_recogniser_same_text(exported, head):
    d, out = exported
    spec, w = out[head]
    a = Recognizer(spec, weights=w, device="cpu", backend="torch")
    b = Recognizer(spec, weights=d / f"{head}.onnx", device="cpu", backend="onnx")
    rng = np.random.default_rng(0)
    crops = [rng.integers(0, 255, (48, wd, 3), dtype=np.uint8) for wd in (40, 100, 190, 480, 960, 2000)]
    ra, rb = a.recognize(crops, positions=True), b.recognize(crops, positions=True)
    for x, y in zip(ra, rb):
        assert x["text"] == y["text"] and abs(x["score"] - y["score"]) < 1e-4
        assert (x["chars"] is None) == (y["chars"] is None) == (head == "cppd")
        if x["chars"]:
            assert [c[0] for c in x["chars"]] == [c[0] for c in y["chars"]]


def test_full_pipeline_same_result(exported):
    d, out = exported
    torch_ocr = OCR(Detector(*out["det"], device="cpu"), Recognizer(*out["gtc"], device="cpu"), min_rec_score=0.0)
    onnx_ocr = OCR(
        Detector(out["det"][0], weights=d / "det.onnx", device="cpu"),
        Recognizer(out["gtc"][0], weights=d / "gtc.onnx", device="cpu"),
        min_rec_score=0.0,
    )
    a, b = torch_ocr(page()), onnx_ocr(page())
    assert [(ln["text"], ln["box"]) for ln in a["lines"]] == [(ln["text"], ln["box"]) for ln in b["lines"]]


def test_onnx_backend_refuses_what_it_cannot_do(exported):
    d, out = exported
    spec, _ = out["gtc"]
    with pytest.raises(ValueError, match="SMTR"):
        Recognizer(spec, weights=d / "gtc.onnx", decoder="gtc")
    with pytest.raises(ValueError, match="det model"):
        Recognizer(spec, weights=d / "det.onnx")
    with pytest.raises(ValueError, match="cppd head"):
        Recognizer(out["cppd"][0], weights=d / "gtc.onnx")
    with pytest.raises(WeightsError, match="needs an exported .onnx"):
        resolve_weights(load_spec(spec), out["gtc"][1], fmt="onnx")
    with pytest.raises(WeightsError, match="export_onnx"):
        resolve_weights(load_spec(spec), fmt="onnx")


def test_runs_without_torch(exported):
    """The onnx path never imports torch (as in a plain `pip install anaksor-ocr`)."""
    d, out = exported
    code = f"""
import sys, importlib.abc
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name == "torch" or name.startswith("torch.") or name.startswith("safetensors"):
            raise ImportError("torch is blocked in this test")
sys.meta_path.insert(0, Block())
import numpy as np
import anaksor
from anaksor.runtime import have_torch
img = np.full((400, 1600, 3), 255, np.uint8); img[40:70, 40:740] = 30
det = anaksor.Detector({str(out["det"][0])!r}, weights={str(d / "det.onnx")!r})
rec = anaksor.Recognizer({str(out["gtc"][0])!r}, weights={str(d / "gtc.onnx")!r})
r = anaksor.OCR(det, rec, min_rec_score=0.0)(img)
assert det.backend == rec.backend == "onnx" and "torch" not in sys.modules
print("ok", len(r["lines"]))
"""
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert res.returncode == 0, res.stderr
    assert res.stdout.startswith("ok")
