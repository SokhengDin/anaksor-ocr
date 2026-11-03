"""tools/spec_from_config.py: Alpha-OCR training config -> anaksor spec that loads its weights."""

import sys
from pathlib import Path

import numpy as np
import torch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from spec_from_config import convert  # noqa: E402

from anaksor import Detector, Recognizer  # noqa: E402
from anaksor.models import load_spec  # noqa: E402
from anaksor.nets import build_detector, build_recognizer  # noqa: E402

REC_CONFIG = """
Global:
  character_dict_path: &character_dict_path ../ocr/dicts/khmer_dict_v3.txt
  max_text_length: &max_text_length 40
  use_space_char: &use_space_char True
Serve: {crop_pad_y: 0.16, crop_pad_x: 0.10}
Architecture:
  model_type: rec
  algorithm: CPPD
  in_channels: 3
  Transform:
  Encoder:
    name: SVTRv2LNConvTwo33
    use_pos_embed: False
    dims: [32, 64, 96]
    depths: [1, 2, 1]
    num_heads: [1, 2, 3]
    mixer: [[Conv], [Conv, FGlobal], [Global]]
    kernel_sizes: [[5], [5, -1], [-1]]
    num_convs: [[1], [1, -1], [-1]]
    pope_bias: True
    sub_k: [[1, 1], [2, 1], [-1, -1]]
    feat2d: False
  Decoder: {name: CPPDDecoder, ds: True, num_layer: 1, rec_layer: 1, max_len: *max_text_length}
PostProcess: {name: CPPDLabelDecode, character_dict_path: *character_dict_path, use_space_char: *use_space_char}
Eval:
  dataset: {name: RatioDataSetTVResize, base_h: 48, base_shape: [[64, 64], [96, 48]]}
  loader: {max_ratio: 10}
"""

DET_CONFIG = """
Architecture:
  algorithm: DB_mobile
  Backbone: {name: RepSVTR_det}
  Neck: {name: RSEFPN, out_channels: 96, shortcut: true}
  Head: {name: DBHead, k: 50}
PostProcess: {name: DBPostProcess, thresh: 0.3, box_thresh: 0.6, max_candidates: 1000, unclip_ratio: 1.5, score_mode: slow}
Eval:
  dataset:
    transforms:
      - DecodeImage: {img_mode: BGR}
      - DetResizeForTest: {limit_side_len: 960}
      - NormalizeImage: {mean: [0.485, 0.456, 0.406], std: [0.229, 0.224, 0.225]}
"""


def test_recogniser_spec_from_a_cppd_config(tmp_path):
    root = tmp_path / "Alpha-OCR"
    (root / "configs").mkdir(parents=True)
    (root / "ocr" / "dicts").mkdir(parents=True)
    (root / "ocr" / "dicts" / "khmer_dict_v3.txt").write_text("ក\nខ\nគ\n", encoding="utf-8")
    cfg = root / "configs" / "svtrv2_cppd_tiny.yml"
    cfg.write_text(REC_CONFIG)

    spec_path = convert(cfg, tmp_path / "specs")
    spec = load_spec(spec_path)
    assert spec.name == "rec-svtrv2-cppd-tiny" and spec.kind == "rec"
    assert spec.weights_file == "rec-svtrv2-cppd-tiny.safetensors" and spec.onnx_file == "rec-svtrv2-cppd-tiny.onnx"
    assert spec.config["input"] == {"base_h": 48, "base_shape": [[64, 64], [96, 48]], "max_ratio": 10}
    assert spec.config["crop"] == {"pad_y": 0.16, "pad_x": 0.10}
    assert (spec_path.parent / spec.config["charset"]["dict"]).read_text(encoding="utf-8") == "ក\nខ\nគ\n"

    torch.manual_seed(0)  # weights as training would save them: .pth with a state_dict
    net = build_recognizer(spec.architecture, ctc_classes=5, cppd_classes=5)
    torch.save({"state_dict": net.state_dict(), "epoch": 1}, tmp_path / "best.pth")
    rec = Recognizer(spec_path, weights=tmp_path / "best.pth", device="cpu")
    assert rec.kind == "cppd" and rec.charset == ["</s>", "ក", "ខ", "គ", " "] and rec.crop_pad == (0.16, 0.10)
    out = rec.recognize(np.full((48, 300, 3), 200, np.uint8), positions=True)
    assert isinstance(out["text"], str) and out["chars"] is None and out["cppd"] is not None


def test_detector_spec(tmp_path):
    cfg = tmp_path / "repvit_db_khmer_v3.yml"
    cfg.write_text(DET_CONFIG)
    spec_path = convert(cfg, tmp_path, name="det-v3")
    spec = yaml.safe_load(spec_path.read_text())
    assert spec["input"]["limit_side_len"] == 960 and spec["postprocess"]["box_thresh"] == 0.6
    assert spec["postprocess"]["use_dilation"] is False
    net = build_detector(spec["architecture"])
    torch.save(net.state_dict(), tmp_path / "det.pth")
    det = Detector(spec_path, weights=tmp_path / "det.pth", device="cpu")
    assert det.limit_side_len == 960 and det.defaults["box_thresh"] == 0.6
