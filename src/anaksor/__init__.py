"""anaksor: Khmer OCR (អានអក្សរ, "read the letters").

import anaksor

ocr = anaksor.OCR()                          # weights download on first use
result = ocr("page.jpg")
print(result["text"])

pages = ocr.read("scan.pdf", keep_images=True)            # needs anaksor-ocr[pdf]
open("scan.pdf", "wb").write(anaksor.export.to_pdf(pages))   # searchable PDF
"""

from __future__ import annotations

import threading
from importlib.metadata import PackageNotFoundError, version

from . import export
from .detector import Detector
from .inputs import InputError, load_image
from .models import WeightsError
from .ocr import OCR
from .recognizer import Recognizer
from .text import normalize

try:
    __version__ = version("anaksor-ocr")
except PackageNotFoundError:  # running from a source tree
    __version__ = "0.0.0"

__all__ = [
    "OCR",
    "Detector",
    "InputError",
    "Recognizer",
    "WeightsError",
    "__version__",
    "export",
    "load_image",
    "normalize",
    "read",
]

_default: OCR | None = None
_default_lock = threading.Lock()


def read(src, **kwargs) -> list[dict]:
    """OCR an image or PDF with a shared default ``OCR()``; returns one result per page."""
    global _default
    with _default_lock:
        if _default is None:
            _default = OCR()
    return _default.read(src, **kwargs)
