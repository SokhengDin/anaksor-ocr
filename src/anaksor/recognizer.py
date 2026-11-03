"""Text-line recognition: SVTRv2 with a CTC head (and an SMTR head for short crops)."""

from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

from .decoding import Charset, cppd_greedy, ctc_greedy, ctc_positions, read_dict, smtr_greedy
from .inputs import load_image
from .models import REC_DEFAULT, ModelSpec, data_path, load_into, load_spec, pick_device, resolve_weights
from .runtime import OnnxRunner, TorchRunner, choose_backend
from .runtime import check_meta as _check_meta
from .text import normalize


def _numpy(a) -> np.ndarray:
    return np.asarray(a, dtype=np.float32)


def _batch_for(ratio: float, batch_size: int) -> int:
    """Crops per batch for a width/height ratio: full batches up to ratio 4, then shrinking
    with ratio^2 (attention over all positions: memory ~ batch * width^2)."""
    return batch_size if ratio <= 4 else max(1, int(batch_size * 16 / ratio**2))


def _resolve_dict(path: str, spec: ModelSpec) -> str:
    """A spec's dict path: absolute, else next to the spec file, else shipped in anaksor/data."""
    p = Path(path)
    if p.is_absolute():
        return str(p)
    if spec.source and (Path(spec.source).parent / p).exists():
        return str(Path(spec.source).parent / p)
    return str(data_path(path))


class _RatioResize:
    """Same shape buckets as training (aspect-ratio buckets, no padding), so inference
    sees exactly the input shapes the model learned from."""

    def __init__(self, inp: dict):
        self.max_ratio = inp.get("max_ratio", 12)
        self.base_shape = inp.get("base_shape", [[64, 64], [96, 48], [112, 40], [128, 32]])
        self.base_h = inp.get("base_h", 32)

    def shape_for(self, w, h) -> tuple[int, int]:
        ratio = min(max(1, round(w / max(h, 1))), self.max_ratio)
        if ratio <= len(self.base_shape):
            return tuple(self.base_shape[ratio - 1])
        return self.base_h * ratio, self.base_h

    def __call__(self, img: Image.Image) -> np.ndarray:
        w, h = self.shape_for(*img.size)
        x = np.asarray(img.resize((w, h), Image.Resampling.BICUBIC), np.float32) / 255.0
        return ((x - 0.5) / 0.5).transpose(2, 0, 1)  # CHW in [-1, 1]


class Recognizer:
    """Khmer text-line recogniser.

        rec = Recognizer()                         # bundled rec-svtrv2-v4
        rec.recognize(crop)                        # {"text", "score", "ctc", "gtc", "time"}
        rec.recognize([crop_a, crop_b])            # list of dicts

    decoder: "ctc" (default) is both more accurate on Khmer and handles long lines, and
    skips the autoregressive loop of the SMTR head, so it is much faster. "gtc" forces
    the SMTR head; "auto" takes the more confident of the two per crop. A CPPD model has
    a single head and ignores it (results carry "cppd" instead of "ctc" / "gtc").
    """

    def __init__(
        self,
        model: str | ModelSpec = REC_DEFAULT,
        weights=None,
        device: str = "auto",
        decoder: str = "ctc",
        normalize_output: bool = True,
        download: bool = True,
        backend: str = "auto",
        fuse: bool = True,
    ):
        self.spec = load_spec(model)
        if self.spec.kind != "rec":
            raise ValueError(f"{self.spec.name} is a {self.spec.kind} model, not a recogniser")
        cfg = self.spec.config
        charset = cfg.get("charset", {})
        dict_path = charset.get("dict")
        if not dict_path:
            raise ValueError(f"{self.spec.name}: the spec names no character dict (charset.dict)")
        self._charset = Charset(read_dict(_resolve_dict(dict_path, self.spec), charset.get("use_space_char", True)))

        self.normalize_output = normalize_output
        cs = self._charset
        self.backend = choose_backend(backend, weights)
        self.weights = resolve_weights(self.spec, weights, download=download, fmt=self.backend)
        dec_cfg = self.spec.architecture.get("Decoder") or {}
        self.kind = "cppd" if dec_cfg.get("name") == "CPPDDecoder" else "ctc" if dec_cfg.get("name") == "RCTCDecoder" else "gtc"
        self.has_positions = self.kind != "cppd"  # CTC character positions, for stitching long lines
        self._smtr_reverse = not (dec_cfg.get("gtc_decoder") or {}).get("next_mode", True)
        if self.backend == "torch":
            from .nets import build_recognizer
            from .nets.fuse import fuse as fuse_bn

            self.device = pick_device(device)
            self.model = build_recognizer(self.spec.architecture, len(cs.ctc), len(cs.smtr), len(cs.cppd))
            load_into(self.model, self.weights)
            self.model.to(self.device).eval()
            if fuse:
                fuse_bn(self.model)
            self._run = TorchRunner(self.model, self.device)
        else:
            self.model = None
            self._run = OnnxRunner(self.weights, device)
            self.device = self._run.device
            head = "cppd" if self.kind == "cppd" else "ctc"
            _check_meta(self._run.meta, "rec", self.weights, len(self.charset), head)
        self.decoder = decoder

        self.resize = _RatioResize(cfg.get("input", {}))
        self.max_ratio = self.resize.max_ratio
        crop = cfg.get("crop", {})
        self.crop_pad = (float(crop.get("pad_y", 0.04)), float(crop.get("pad_x", 0.04)))

    @property
    def has_gtc(self) -> bool:
        """The SMTR head can run (a GTC model on the torch backend)."""
        return self.kind == "gtc" and self.backend == "torch"

    @property
    def decoder(self) -> str:
        return self._decoder

    @decoder.setter
    def decoder(self, value: str) -> None:
        if value not in ("ctc", "gtc", "auto"):
            raise ValueError(f"decoder must be ctc, gtc or auto, not {value!r}")
        if value != "ctc" and self.kind == "gtc" and self.backend != "torch":
            raise ValueError(f'decoder="{value}" needs the SMTR head, which runs on the torch backend only')
        self._decoder = value
        if self.model is not None and self.kind == "gtc":
            self.model.decoder.infer_gtc = value != "ctc"

    @property
    def charset(self) -> list[str]:
        """The classes of the main head: CTC ("blank", then the characters), or for a
        CPPD model "</s>" then the characters."""
        return self._charset.cppd if self.kind == "cppd" else self._charset.ctc

    def _decode(self, preds) -> list[dict]:
        if self.kind == "cppd":
            return [
                {"text": t, "score": s, "ctc": None, "gtc": None, "cppd": (t, s)}
                for t, s in cppd_greedy(_numpy(preds), self._charset.cppd)
            ]
        ctc_probs = preds["ctc_pred"] if isinstance(preds, dict) else preds
        ctc = ctc_greedy(_numpy(ctc_probs), self._charset.ctc)
        if isinstance(preds, dict):
            gtc = smtr_greedy(_numpy(preds["gtc_pred"]), self._charset.smtr, reverse=self._smtr_reverse)
        else:  # SMTR head off
            gtc = [None] * len(ctc)
        out = []
        for g, c in zip(gtc, ctc):
            if g is None or self.decoder == "ctc":
                text, score = c
            elif self.decoder == "gtc":
                text, score = g
            else:
                # the autoregressive head can stop early on long lines: fall back to CTC
                truncated = len(g[0]) < 0.8 * len(c[0])
                text, score = c if (truncated or c[1] > g[1] + 0.02) else g
            out.append({"text": text, "score": score, "ctc": c, "gtc": g})
        return out

    def _ctc_chars(self, preds) -> list[list[tuple[str, float, float]] | None]:
        """Per crop [(char, x_frac, prob)] from the CTC head, before normalisation (None
        for a CPPD model, which has no per-column output)."""
        if self.kind == "cppd":
            return [None] * len(preds)
        ctc = preds["ctc_pred"] if isinstance(preds, dict) else preds
        return ctc_positions(_numpy(ctc), self._charset.ctc)

    def recognize(self, images, batch_size: int = 32, positions: bool = False):
        """Recognise one crop (returns a dict) or a list of crops (returns a list).
        positions=True adds "chars": [(char, x_frac, prob)] from the CTC head (None for
        a CPPD model). batch_size: crops per batch up to 4x as wide as high; wider crops go
        in smaller batches, since global attention memory grows with the square of the width."""
        single = not isinstance(images, list)
        imgs = [load_image(i) for i in ([images] if single else images)]
        results: list[dict | None] = [None] * len(imgs)
        if not imgs:
            return results
        groups = defaultdict(list)  # same input shape: batched without padding
        for i, im in enumerate(imgs):
            groups[self.resize.shape_for(*im.size)].append(i)
        for (w, h), idxs in groups.items():
            n = _batch_for(w / h, batch_size)
            for b in range(0, len(idxs), n):
                chunk = idxs[b : b + n]
                x = np.stack([self.resize(imgs[i]) for i in chunk])
                t0 = time.time()
                preds = self._run(x)
                dec = self._decode(preds)
                if positions:
                    for d, ch in zip(dec, self._ctc_chars(preds)):
                        d["chars"] = ch
                dt = time.time() - t0
                for i, d in zip(chunk, dec):
                    if self.normalize_output:
                        d["text"] = normalize(d["text"])
                    d["time"] = dt / len(chunk)
                    results[i] = d
        return results[0] if single else results
