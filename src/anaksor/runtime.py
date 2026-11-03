"""Where the networks run: PyTorch or ONNX Runtime.

Both runners take a float32 numpy batch and return numpy arrays, so everything around the
networks (resizing, box extraction, decoding, layout) is the same for the two.

- ``torch``: the native networks, with batch norms fused (2-3x faster detection on CPU);
  CPU, CUDA or Apple MPS. Needs ``pip install anaksor-ocr[torch]``. The only backend for
  the SMTR head (``decoder="gtc"`` / ``"auto"``), whose reading loop has a data-dependent length.
- ``onnx``: exported graphs (``tools/export_onnx.py``) in ONNX Runtime. No PyTorch needed;
  CUDA when ``onnxruntime-gpu`` is installed, otherwise CPU.

``backend="auto"`` picks ``onnx`` for an ``.onnx`` weights file, else ``torch`` when it is
installed, else ``onnx``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

BACKENDS = ("auto", "torch", "onnx")


def have_torch() -> bool:
    return importlib.util.find_spec("torch") is not None


def choose_backend(backend: str = "auto", weights=None) -> str:
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {', '.join(BACKENDS)}, not {backend!r}")
    if backend == "auto":
        if weights is not None and Path(weights).suffix == ".onnx":
            return "onnx"
        return "torch" if have_torch() else "onnx"
    if backend == "torch" and not have_torch():
        raise ImportError('the torch backend needs PyTorch: pip install "anaksor-ocr[torch]"')
    return backend


class TorchRunner:
    """A native network on a torch device; outputs as numpy (dicts stay dicts)."""

    def __init__(self, model, device):
        import torch

        self._torch = torch
        self.model = model
        self.device = device

    def __call__(self, x: np.ndarray):
        with self._torch.inference_mode():
            out = self.model(self._torch.from_numpy(np.ascontiguousarray(x)).to(self.device))
        if isinstance(out, dict):
            return {k: v.detach().float().cpu().numpy() for k, v in out.items()}
        return out.detach().float().cpu().numpy()


class OnnxRunner:
    """An exported graph in ONNX Runtime: one input ("image"), first output returned."""

    def __init__(self, path, device: str = "auto", threads: int | None = None):
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise ImportError("the onnx backend needs ONNX Runtime: pip install onnxruntime (or onnxruntime-gpu)") from e
        available = ort.get_available_providers()
        if device in ("auto", "cuda") or str(device).startswith("cuda"):
            providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in available]
            if str(device).startswith("cuda") and "CUDAExecutionProvider" not in available:
                raise RuntimeError("CUDA asked for, but this ONNX Runtime has no CUDA provider: pip install onnxruntime-gpu")
        elif device == "cpu":
            providers = ["CPUExecutionProvider"]
        else:
            raise ValueError(f"the onnx backend runs on auto, cpu or cuda, not {device!r}")
        opts = ort.SessionOptions()
        # Shapes change with every width bucket: memory patterns (planned for one shape) and
        # the arena (which keeps every peak) only add memory. 6 pages, rec v3, CPU: peak
        # 2.69 GB -> 0.88 GB at about the same speed (95 s -> 99 s).
        opts.enable_mem_pattern = False
        opts.enable_cpu_mem_arena = False
        if threads:
            opts.intra_op_num_threads = threads
        self.session = ort.InferenceSession(str(path), sess_options=opts, providers=providers)
        self.input = self.session.get_inputs()[0].name
        self.meta = dict(self.session.get_modelmeta().custom_metadata_map)
        self.device = "cuda" if self.session.get_providers()[0] == "CUDAExecutionProvider" else "cpu"

    def __call__(self, x: np.ndarray) -> np.ndarray:
        return self.session.run(None, {self.input: np.ascontiguousarray(x, dtype=np.float32)})[0]


def check_meta(meta: dict, kind: str, path, classes: int | None = None, head: str | None = None) -> None:
    """Refuse a graph exported for another kind of model or another charset."""
    if meta.get("anaksor_kind") and meta["anaksor_kind"] != kind:
        raise ValueError(f"{Path(path).name} is an exported {meta['anaksor_kind']} model, not a {kind} model")
    if head and meta.get("anaksor_head") and meta["anaksor_head"] != head:
        raise ValueError(f"{Path(path).name} has a {meta['anaksor_head']} head, the spec a {head} head")
    if classes and meta.get("anaksor_classes") and int(meta["anaksor_classes"]) != classes:
        raise ValueError(f"{Path(path).name} has {meta['anaksor_classes']} classes, the spec's charset {classes}")
