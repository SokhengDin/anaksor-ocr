"""Text-line recogniser: SVTRv2 encoder with either

- an RCTC head and, optionally, an SMTR head ("GTC": trained jointly, the attention head
  guiding the CTC head). At inference the CTC head is the fast default; the SMTR head runs
  only when ``infer_gtc`` is set. Or
- a CPPD head (parallel decoding of all positions at once).
"""

from __future__ import annotations

from torch import nn

from .cppd import CPPDHead
from .rctc import RCTCHead
from .smtr import SMTRHead
from .svtrv2 import SVTRv2


class Heads(nn.Module):
    """``ctc_decoder`` and, when ``gtc_classes`` is given, ``gtc_decoder``."""

    def __init__(self, in_channels: int, ctc_classes: int, gtc_classes: int | None = None, smtr: dict | None = None):
        super().__init__()
        self.ctc_decoder = RCTCHead(in_channels, ctc_classes)
        self.gtc_decoder = SMTRHead(in_channels, gtc_classes, **(smtr or {})) if gtc_classes else None
        self.infer_gtc = False

    def forward(self, x):
        ctc = self.ctc_decoder(x)
        if self.infer_gtc and self.gtc_decoder is not None:
            return {"ctc_pred": ctc, "gtc_pred": self.gtc_decoder(x.flatten(2).transpose(1, 2))}
        return ctc


class TextLineNet(nn.Module):
    """Line image (B, 3, H, W) ->

    kind "ctc" / "gtc": CTC probabilities (B, W/4, ctc_classes), or a dict with ``ctc_pred``
    and ``gtc_pred`` (B, T, gtc_classes - 3) when ``decoder.infer_gtc``;
    kind "cppd": (B, max_len + 1, cppd_classes) probabilities per position."""

    def __init__(
        self,
        encoder: dict,
        ctc_classes: int = 0,
        gtc_classes: int | None = None,
        smtr: dict | None = None,
        in_channels: int = 3,
        cppd: dict | None = None,
        cppd_classes: int = 0,
    ):
        super().__init__()
        self.encoder = SVTRv2(in_channels, **encoder)
        if cppd is not None:
            self.kind = "cppd"
            self.decoder = CPPDHead(self.encoder.out_channels, cppd_classes, **cppd)
        else:
            self.kind = "gtc" if gtc_classes else "ctc"
            self.decoder = Heads(self.encoder.out_channels, ctc_classes, gtc_classes, smtr)

    def forward(self, x):
        return self.decoder(self.encoder(x))
