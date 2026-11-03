"""The networks against reference outputs, without weights or network access.

tests/data/checkpoint_layout.json lists every tensor (name and shape) of the checkpoints
Alpha-OCR trains, per architecture. tests/data/golden.npz holds outputs of the original
training-time implementation for weights rebuilt deterministically from that layout, on
seeded inputs, plus boxes of its DB post-processing on a synthetic probability map. If a
renamed module or a changed computation would stop anaksor reading the trained models,
these tests fail.
"""

import copy
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from anaksor.db_boxes import boxes_from_map
from anaksor.models import load_spec
from anaksor.nets import build_detector, build_recognizer

DATA = Path(__file__).parent / "data"
LAYOUT = json.loads((DATA / "checkpoint_layout.json").read_text())
GOLDEN = np.load(DATA / "golden.npz")
TRAINING_ONLY = (
    "head.thresh.",  # DB threshold branch
    "decoder.char_node_embed.",  # CPPD counting and ordering side tasks
    "decoder.char_node_fc1.",
    "decoder.pos_node_fc1.",
)


def layout_weights(layout: dict, seed: int) -> dict:
    """Deterministic non-trivial weights for {name: shape} (numpy PCG64, stable across versions)."""
    rng = np.random.default_rng(seed)
    out = {}
    for name in sorted(layout):
        shape = tuple(layout[name])
        if name.endswith("num_batches_tracked"):
            continue
        if name.endswith("running_var"):
            a = rng.uniform(0.5, 1.5, shape)
        elif name.endswith("weight") and len(shape) == 1:
            a = 1.0 + 0.05 * rng.standard_normal(shape)
        else:
            a = 0.05 * rng.standard_normal(shape)
        out[name] = torch.from_numpy(a.astype(np.float32))
    return out


def golden_input(seed: int, shape) -> torch.Tensor:
    return torch.from_numpy(np.random.default_rng(seed).standard_normal(shape).astype(np.float32))


def rec_arch(name: str) -> dict:
    if name == "rec_cppd":
        return copy.deepcopy(LAYOUT["cppd_arch"])
    arch = copy.deepcopy(load_spec("rec-svtrv2-v3").architecture)
    if name == "rec_v4":
        arch["Encoder"] = copy.deepcopy(LAYOUT["v4_encoder"])
    return arch


def build(name: str):
    if name == "det_v2":
        return build_detector(load_spec("det-repvit-db-v2").architecture)
    return build_recognizer(rec_arch(name), ctc_classes=213, gtc_classes=217, cppd_classes=213)


def loaded(name: str, seed: int):
    model = build(name)
    weights = layout_weights(LAYOUT["models"][name], seed)
    model.load_state_dict({k: v for k, v in weights.items() if k in model.state_dict()}, strict=False)
    return model.eval()


@pytest.mark.parametrize("name", ["det_v2", "rec_v3", "rec_v4", "rec_cppd"])
def test_tensor_names_and_shapes_match_the_checkpoints(name):
    ckpt = {k: tuple(v) for k, v in LAYOUT["models"][name].items()}
    own = {k: tuple(v.shape) for k, v in build(name).state_dict().items()}
    assert {k: s for k, s in own.items() if ckpt.get(k) != s} == {}, "tensors the checkpoints don't have"
    unused = [k for k in ckpt if k not in own and not k.endswith("num_batches_tracked")]
    assert all(k.startswith(TRAINING_ONLY) for k in unused), unused


def test_detector_probability_map():
    with torch.inference_mode():
        prob = loaded("det_v2", 1)(golden_input(10, (1, 3, 96, 160))).numpy()
    assert prob.shape == (1, 1, 96, 160)
    np.testing.assert_allclose(prob[:, :, ::4, ::4], GOLDEN["det_prob"], atol=1e-5)


def _check(probs: torch.Tensor, key: str):
    p = probs.numpy()
    np.testing.assert_array_equal(p.argmax(-1), GOLDEN[key + "_ids"])
    np.testing.assert_allclose(p.max(-1), GOLDEN[key + "_maxp"], atol=1e-4)
    np.testing.assert_allclose(p[:, : GOLDEN[key + "_head"].shape[1]], GOLDEN[key + "_head"], atol=1e-4)


@pytest.mark.parametrize("name", ["rec_v3", "rec_v4"])
def test_recogniser_ctc_and_smtr_heads(name):
    model = loaded(name, 2)
    model.decoder.infer_gtc = True
    for seed, width in ((20, 192), (21, 480)):
        with torch.inference_mode():
            out = model(golden_input(seed, (2, 3, 48, width)))
        _check(out["ctc_pred"], f"{name}_{width}_ctc")
        _check(out["gtc_pred"], f"{name}_{width}_gtc")
    model.decoder.infer_gtc = False
    with torch.inference_mode():
        ctc = model(golden_input(20, (2, 3, 48, 192)))  # CTC only: a plain tensor
    _check(ctc, f"{name}_192_ctc")


def test_cppd_head():
    model = loaded("rec_cppd", 3)
    assert model.kind == "cppd"
    for seed, width in ((30, 192), (31, 480)):
        with torch.inference_mode():
            _check(model(golden_input(seed, (2, 3, 48, width))), f"rec_cppd_{width}")


def test_smtr_stops_once_every_line_has_ended():
    model = loaded("rec_v3", 2)
    model.decoder.infer_gtc = True
    with torch.no_grad():
        model.decoder.gtc_decoder.ques1_head.bias[0] = 1e4  # end of text wins at once
        out = model(golden_input(20, (2, 3, 48, 192)))
    assert out["gtc_pred"].shape[:2] == (2, 1) and (out["gtc_pred"].argmax(-1) == 0).all()


@pytest.mark.parametrize("mode", ["slow", "fast"])
@pytest.mark.parametrize("ratio", [1.5, 2.0])
def test_db_boxes(mode, ratio):
    boxes, scores = boxes_from_map(GOLDEN["db_prob"], (480, 640), thresh=0.3, box_thresh=0.5, unclip_ratio=ratio, score_mode=mode)
    np.testing.assert_array_equal(np.asarray(boxes, np.int32).reshape(-1, 4, 2), GOLDEN[f"db_{mode}_{ratio}_boxes"])
    np.testing.assert_allclose(scores, GOLDEN[f"db_{mode}_{ratio}_scores"], atol=1e-9)


@pytest.mark.parametrize("prefix", ["", "module."])
def test_alpha_ocr_checkpoint_loads(tmp_path, prefix):
    """The .pth layout utils/export_weights.py writes: state_dict plus epoch, metrics, config."""
    from anaksor import Recognizer

    weights = layout_weights(LAYOUT["models"]["rec_v3"], seed=2)
    ckpt = {
        "state_dict": {prefix + k: v for k, v in weights.items()},
        "epoch": 40,
        "metrics": {"acc": 0.93, "norm_edit_dis": 0.995},
        "config": {"Global": {"max_text_length": 140}, "Architecture": rec_arch("rec_v3")},
    }
    torch.save(ckpt, tmp_path / "khmer_rec_svtrv2_v3.pth")
    rec = Recognizer("rec-svtrv2-v3", weights=tmp_path / "khmer_rec_svtrv2_v3.pth", device="cpu", fuse=False)  # compare as loaded
    own = rec.model.state_dict()
    assert all(torch.equal(own[k], v) for k, v in weights.items() if k in own)
    assert isinstance(rec.recognize(np.full((48, 200, 3), 128, np.uint8))["text"], str)


def test_unknown_parts_are_refused():
    arch = rec_arch("rec_v3")
    with pytest.raises(ValueError, match="Encoder"):
        build_recognizer({**arch, "Encoder": {"name": "ViT"}}, 213, 217)
    with pytest.raises(ValueError, match="gtc_classes"):
        build_recognizer(arch, 213)
    with pytest.raises(ValueError, match="Backbone"):
        build_detector({"Backbone": {"name": "ResNet"}, "Neck": {"name": "RSEFPN"}, "Head": {"name": "DBHead"}})
