"""Text detection: DBNet / DBNet++ to line boxes."""

from __future__ import annotations

import time

import cv2
import numpy as np

from .db_boxes import boxes_from_map
from .geometry import overlap_ratio
from .inputs import load_image
from .models import DET_DEFAULT, ModelSpec, load_into, load_spec, pick_device, resolve_weights
from .runtime import OnnxRunner, TorchRunner, choose_backend
from .runtime import check_meta as _check_meta


class Detector:
    """DBNet / DBNet++ text detector.

        det = Detector()                       # bundled det-repvit-dbpp-v1, weights from the cache
        det.detect(image)                      # {"boxes": [[[x, y] * 4], ...], "scores": [...], "time": s}

    limit_side_len: the long side is resized down to this. Small document text needs
        1280-1600; 960 is fine for photos. min_side_len: smaller images are upscaled.
    backend: "auto", "torch" or "onnx" (see anaksor.runtime). fuse: fold batch norms into
        the convs (torch backend; same output, faster).
    """

    def __init__(
        self,
        model: str | ModelSpec = DET_DEFAULT,
        weights=None,
        device: str = "auto",
        limit_side_len: int | None = None,
        min_side_len: int | None = None,
        download: bool = True,
        backend: str = "auto",
        fuse: bool = True,
    ):
        self.spec = load_spec(model)
        if self.spec.kind != "det":
            raise ValueError(f"{self.spec.name} is a {self.spec.kind} model, not a detector")
        inp = self.spec.config.get("input", {})
        self.limit_side_len = limit_side_len or inp.get("limit_side_len", 1280)
        self.min_side_len = min_side_len or inp.get("min_side_len", 736)
        self.mean = np.array(inp.get("mean", [0.485, 0.456, 0.406]), np.float32)
        self.std = np.array(inp.get("std", [0.229, 0.224, 0.225]), np.float32)

        self.backend = choose_backend(backend, weights)
        self.weights = resolve_weights(self.spec, weights, download=download, fmt=self.backend)
        if self.backend == "torch":
            from .nets import build_detector
            from .nets.fuse import fuse as fuse_bn

            self.device = pick_device(device)
            self.model = build_detector(self.spec.architecture)
            load_into(self.model, self.weights)
            self.model.to(self.device).eval()
            if fuse:
                fuse_bn(self.model)
            self._run = TorchRunner(self.model, self.device)
        else:
            self.model = None
            self._run = OnnxRunner(self.weights, device)
            self.device = self._run.device
            _check_meta(self._run.meta, "det", self.weights)

        post = self.spec.config.get("postprocess", {})
        self.defaults = {
            "thresh": post.get("thresh", 0.3),
            "box_thresh": post.get("box_thresh", 0.5),
            "unclip_ratio": post.get("unclip_ratio", 1.5),
        }
        self.box_options = {
            "max_candidates": post.get("max_candidates", 1000),
            "score_mode": post.get("score_mode", "slow"),
            "dilate": bool(post.get("use_dilation", False)),
        }

    def _resize(self, img, scale_mul=1.0):
        h, w = img.shape[:2]
        long_side = max(h, w)
        scale = 1.0
        if long_side > self.limit_side_len:
            scale = self.limit_side_len / long_side
        elif long_side < self.min_side_len:
            scale = self.min_side_len / long_side
        scale *= scale_mul
        nh = max(32, int(round(h * scale / 32)) * 32)
        nw = max(32, int(round(w * scale / 32)) * 32)
        return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR), nh / h, nw / w

    def _detect_once(self, rgb, scale_mul, thresh, box_thresh, unclip_ratio):
        img, rh, rw = self._resize(rgb, scale_mul)
        bgr = img[..., ::-1].astype(np.float32) / 255.0  # trained on BGR input
        x = ((bgr - self.mean) / self.std).transpose(2, 0, 1)[None]
        prob = self._run(x)[0, 0]
        boxes, scores = boxes_from_map(
            prob, rgb.shape[:2], thresh=thresh, box_thresh=box_thresh, unclip_ratio=unclip_ratio, **self.box_options
        )
        return [b.astype(np.float32) for b in boxes], [float(s) for s in scores]

    def detect(self, image, box_thresh=None, thresh=None, unclip_ratio=None, scales=(1.0,)) -> dict:
        """Line boxes of an image (path, bytes, PIL image or RGB array).

        thresh: pixel threshold on the probability map; box_thresh: minimum mean
        probability inside a box; unclip_ratio: how much each box is grown (bigger joins
        more). scales: extra resize factors, e.g. (1.0, 1.6), merged; slower but finds
        small text."""
        rgb = image if _is_rgb_array(image) else np.asarray(load_image(image))
        thresh = self.defaults["thresh"] if thresh is None else thresh
        box_thresh = self.defaults["box_thresh"] if box_thresh is None else box_thresh
        unclip_ratio = self.defaults["unclip_ratio"] if unclip_ratio is None else unclip_ratio
        t0 = time.time()
        boxes, scores = [], []
        for s in scales:
            b, sc = self._detect_once(rgb, s, thresh, box_thresh, unclip_ratio)
            boxes += b
            scores += sc
        if len(scales) > 1:
            boxes, scores = _merge(boxes, scores)
        return {"boxes": [b.tolist() for b in boxes], "scores": scores, "time": time.time() - t0}


def _merge(boxes, scores, thr=0.6):
    """Greedy de-duplication across scales (keeps the higher-score box)."""
    keep = []
    for i in np.argsort(scores)[::-1]:
        if all(overlap_ratio(boxes[i], boxes[j]) < thr for j in keep):
            keep.append(i)
    return [boxes[i] for i in keep], [scores[i] for i in keep]


def _is_rgb_array(a) -> bool:
    return isinstance(a, np.ndarray) and a.ndim == 3 and a.shape[2] == 3 and a.dtype == np.uint8
