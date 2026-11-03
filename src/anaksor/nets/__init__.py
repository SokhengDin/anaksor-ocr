"""anaksor's networks, written for inference, from the papers.

Implemented: RepViT + DBNet (detection); SVTRv2 with RCTC + SMTR heads, RCTC alone, or a
CPPD head (recognition).

The model specs (``anaksor/data/*.yml``) describe architectures in the same terms as the
Alpha-OCR training configs, so an ``Architecture`` block can be copied from a training
config unchanged, and the tensor names match the checkpoints Alpha-OCR writes.
"""

from __future__ import annotations

from .dbnet import DBNet
from .textline import TextLineNet

__all__ = ["DBNet", "TextLineNet", "build_detector", "build_recognizer"]

_DET_PARTS = {"Backbone": ("RepSVTR_det",), "Neck": ("RSEFPN",), "Head": ("DBHead",)}
_ENCODERS = ("SVTRv2LNConvTwo33",)
_GTC = ("GTCDecoder", "GTCCountDecoder")  # the count head is training-only


def _part(arch: dict, key: str, names: tuple[str, ...]) -> dict:
    cfg = dict(arch.get(key) or {})
    cfg.pop("in_channels", None)  # set from the previous part
    name = cfg.pop("name", None)
    if name not in names:
        raise ValueError(f"unsupported {key} {name!r}: anaksor implements {', '.join(names)}")
    return cfg


def build_detector(arch: dict) -> DBNet:
    """DBNet from a spec's ``architecture`` block."""
    parts = {k: _part(arch, k, names) for k, names in _DET_PARTS.items()}
    return DBNet(parts["Backbone"], parts["Neck"], parts["Head"], in_channels=arch.get("in_channels", 3))


def build_recognizer(
    arch: dict, ctc_classes: int, gtc_classes: int | None = None, cppd_classes: int | None = None
) -> TextLineNet:
    """Text-line recogniser from a spec's ``architecture`` block. ``ctc_classes`` counts
    the CTC blank; ``gtc_classes`` the SMTR vocabulary (needed when the spec has an SMTR
    head); ``cppd_classes`` the CPPD vocabulary (end symbol + characters)."""
    if arch.get("Transform"):
        raise ValueError("input transforms (TPS) are not supported")
    encoder = _part(arch, "Encoder", _ENCODERS)
    dec = dict(arch.get("Decoder") or {})
    name = dec.get("name")
    smtr = None
    if name in _GTC:
        _part(dec, "ctc_decoder", ("RCTCDecoder",))
        smtr = _part(dec, "gtc_decoder", ("SMTRDecoder",))
        if not gtc_classes:
            raise ValueError("this model has an SMTR head: pass gtc_classes")
    elif name == "RCTCDecoder":
        gtc_classes = None
    elif name == "CPPDDecoder":
        if not cppd_classes:
            raise ValueError("this model has a CPPD head: pass cppd_classes")
        cppd = {k: v for k, v in dec.items() if k != "name"}
        return TextLineNet(encoder, in_channels=arch.get("in_channels", 3), cppd=cppd, cppd_classes=cppd_classes)
    else:
        raise ValueError(
            f"unsupported Decoder {name!r}: anaksor implements GTCDecoder (RCTC + SMTR), RCTCDecoder and CPPDDecoder"
        )
    return TextLineNet(encoder, ctc_classes, gtc_classes, smtr, in_channels=arch.get("in_channels", 3))
