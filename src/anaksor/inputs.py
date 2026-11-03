"""Reading inputs: images (with a format allowlist) and PDF pages.

Images from outside (uploads, files from users) are decoded only as JPEG, PNG, WEBP,
BMP or TIFF. Pillow otherwise sniffs and parses dozens of rarer formats (PSD, MSP, MIC,
FITS...), which is where most of its security bugs have been. Multi-picture phone JPEGs
(MPO) come through the JPEG decoder.

PDF pages are always rendered and OCR'd, never read from the text layer: Khmer PDFs
often carry legacy-font encodings (Limon and friends) or text in glyph order (a vowel
such as េ stored before its consonant), so the text layer is unreliable even when
present. Rendering uses PDFium through pypdfium2 (``pip install anaksor-ocr[pdf]``).
PDFium is not thread-safe, so every call goes through one lock.
"""

from __future__ import annotations

import io
import os
import threading
from collections.abc import Iterator
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

IMAGE_FORMATS = ("JPEG", "PNG", "WEBP", "BMP", "TIFF")
PDF_DPI = 200

_PDF_LOCK = threading.Lock()


class InputError(ValueError):
    """The input can't be read (not an allowed image format, damaged, encrypted PDF...)."""


def load_image(src, formats: tuple[str, ...] | None = IMAGE_FORMATS, max_px: int | None = None) -> Image.Image:
    """RGB image from a path, bytes, PIL image or numpy array (RGB or grayscale).

    EXIF orientation is applied. ``formats`` limits which decoders may run on paths and
    bytes (None allows every Pillow format). ``max_px`` downscales the long side."""
    if isinstance(src, Image.Image):
        img = src
    elif isinstance(src, np.ndarray):
        if src.ndim == 2:
            return Image.fromarray(src).convert("RGB")
        img = Image.fromarray(np.ascontiguousarray(src[..., :3]))
    elif isinstance(src, (str, os.PathLike, bytes, bytearray)):
        fp = io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else Path(src)
        try:
            img = Image.open(fp, formats=formats)
            if max_px and img.format in ("JPEG", "MPO"):
                img.draft("RGB", (max_px, max_px))  # decode big photos at reduced size
            img.load()
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as e:
            raise InputError(
                f"not a readable image ({type(e).__name__}); allowed formats: {', '.join(formats or ['any'])}"
            ) from e
    else:
        raise TypeError(f"unsupported image input: {type(src).__name__}")
    img = ImageOps.exif_transpose(img).convert("RGB")
    if max_px and max(img.size) > max_px:
        s = max_px / max(img.size)
        img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.Resampling.LANCZOS)
    return img


def is_pdf(src) -> bool:
    if isinstance(src, (bytes, bytearray)):
        return b"%PDF" in bytes(src[:1024])
    if isinstance(src, (str, os.PathLike)) and Path(src).is_file():
        with open(src, "rb") as f:
            return b"%PDF" in f.read(1024)
    return False


def _pdfium():
    try:
        import pypdfium2 as pdfium
    except ImportError as e:
        raise ImportError("reading PDFs needs pypdfium2: pip install 'anaksor-ocr[pdf]'") from e
    return pdfium


def open_pdf(src, password: str | None = None):
    """Open a PDF from a path or bytes. Raises InputError with a message fit for users."""
    pdfium = _pdfium()
    data = src if isinstance(src, (bytes, bytearray)) else Path(src).read_bytes()
    if b"%PDF" not in bytes(data[:1024]):
        raise InputError("this file isn't a PDF")
    try:
        with _PDF_LOCK:
            return pdfium.PdfDocument(bytes(data), password=password)
    except pdfium.PdfiumError as e:
        if "password" in str(e).lower():
            raise InputError("this PDF is password-protected") from e
        raise InputError("this PDF is damaged or can't be opened") from e


def page_count(doc) -> int:
    with _PDF_LOCK:
        return len(doc)


def render_page(doc, index: int, dpi: int = PDF_DPI, max_px: int = 2400) -> tuple[Image.Image, tuple]:
    """(RGB image, page size in points) of page ``index`` (0-based). 200 dpi puts body
    text at about 35-45 px line height, where the recogniser is accurate; ``max_px``
    keeps poster-sized pages from exhausting memory."""
    with _PDF_LOCK:
        page = doc[index]
        try:
            w, h = page.get_size()  # points, page rotation applied
            scale = min(dpi / 72.0, max_px / max(w, h, 1.0))
            img = page.render(scale=scale).to_pil().convert("RGB")
        finally:
            page.close()
    return img, (float(w), float(h))


def close_pdf(doc) -> None:
    with _PDF_LOCK:
        doc.close()


def pdf_pages(
    src, pages: list[int] | range | None = None, dpi: int = PDF_DPI, password: str | None = None
) -> Iterator[tuple[int, Image.Image, tuple]]:
    """Yield (page number from 1, image, size in points) for the chosen pages (1-based;
    default all)."""
    doc = open_pdf(src, password)
    try:
        n = page_count(doc)
        for p in pages or range(1, n + 1):
            if not 1 <= p <= n:
                raise InputError(f"page {p} out of range: the PDF has {n} pages")
            img, size = render_page(doc, p - 1, dpi)
            yield p, img, size
    finally:
        close_pdf(doc)
