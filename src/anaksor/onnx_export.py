"""Export the networks to ONNX, for the onnx backend (no PyTorch at inference).

    det = anaksor.Detector(backend="torch")
    export_onnx(det, "khmer_det_repvit_db_v2.onnx")
    export_onnx(anaksor.Recognizer(backend="torch"), "khmer_rec_svtrv2_v3.onnx")

What is exported: the detector's probability map, a recogniser's CTC head (the SMTR head's
reading loop has a data-dependent length and stays on the torch backend), or a CPPD head.
Batch norms are fused first. Shapes are dynamic: any batch, any image size (multiples of 32)
for the detector, any width (and bucket height) for a recogniser. The graph is checked against PyTorch on a few
shapes before it is written. Needs ``pip install onnx onnxscript`` (and onnxruntime to check).
"""

from __future__ import annotations

import copy
import gc
import hashlib
from pathlib import Path

import numpy as np

OPSET = 18


def _check(model, path: Path, shapes, atol: float) -> float:
    import onnxruntime as ort
    import torch

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    worst = 0.0
    g = torch.Generator().manual_seed(0)
    for shape in shapes:
        x = torch.randn(*shape, generator=g)
        with torch.inference_mode():
            ref = model(x).numpy()
        got = sess.run(None, {"image": x.numpy()})[0]
        if got.shape != ref.shape:
            raise RuntimeError(f"exported graph gives shape {got.shape} for {tuple(shape)}, PyTorch {ref.shape}")
        worst = max(worst, float(np.abs(got - ref).max()))
    if worst > atol:
        raise RuntimeError(f"exported graph differs from PyTorch by {worst:.2e} (> {atol:.0e})")
    return worst


def export_onnx(model, path, check: bool = True, atol: float = 1e-4) -> dict:
    """Export a torch-backend Detector or Recognizer to ``path``. Returns
    {"path", "sha256", "max_diff"} (max_diff: largest difference to PyTorch in the check)."""
    import logging

    import onnx
    import torch

    logging.getLogger("torch.onnx").setLevel(logging.ERROR)  # optional-op registration notices

    from .detector import Detector
    from .nets.fuse import fuse
    from .recognizer import Recognizer

    if getattr(model, "backend", None) != "torch":
        raise ValueError("export a model loaded with backend='torch'")
    net = copy.deepcopy(model.model).cpu().eval()
    dyn = torch.export.Dim
    if isinstance(model, Detector):
        kind, head, classes = "det", "db", 0
        sample = torch.randn(1, 3, 640, 640)
        dims = {0: dyn("batch", max=64), 2: dyn.AUTO, 3: dyn.AUTO}
        shapes = [(1, 3, 96, 160), (2, 3, 640, 960)]
    elif isinstance(model, Recognizer):
        kind = "rec"
        head = "cppd" if model.kind == "cppd" else "ctc"
        classes = len(model.charset)
        if model.kind != "cppd":
            net.decoder.infer_gtc = False  # CTC head only
        h = model.resize.base_h
        sample = torch.randn(2, 3, h, 4 * h)
        dims = {0: dyn("batch", max=4096), 2: dyn.AUTO, 3: dyn.AUTO}  # buckets differ in height too
        ratios = sorted({*range(1, len(model.resize.base_shape) + 2), model.max_ratio // 2, model.max_ratio})
        buckets = sorted({tuple(model.resize.shape_for(r * 100, 100)) for r in ratios if r >= 1})
        shapes = [(2 if bw <= 4 * bh else 1, 3, bh, bw) for bw, bh in buckets]  # every fixed bucket, mid, widest
    else:
        raise TypeError(f"export_onnx takes a Detector or a Recognizer, not {type(model).__name__}")
    fuse(net)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        net,
        (sample,),
        str(path),
        dynamo=True,
        dynamic_shapes={"x": dims},
        input_names=["image"],
        output_names=["probs"],
        opset_version=OPSET,
        external_data=False,
        verbose=False,
    )
    proto = onnx.load(str(path))
    meta = {"anaksor_kind": kind, "anaksor_head": head, "anaksor_spec": model.spec.name}
    if classes:
        meta["anaksor_classes"] = str(classes)
    for k, v in meta.items():
        proto.metadata_props.add(key=k, value=v)
    onnx.save(proto, str(path))
    del proto
    gc.collect()  # the export's intermediate graphs before running the check
    max_diff = _check(net, path, shapes, atol) if check else None
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "max_diff": max_diff}
