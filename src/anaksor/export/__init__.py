"""OCR results to documents: plain text, searchable PDF, Word.

import anaksor
pages = anaksor.OCR().read("scan.pdf", keep_images=True)
open("scan.txt", "w").write(anaksor.export.to_text(pages))
open("scan.pdf", "wb").write(anaksor.export.to_pdf(pages))
open("scan.docx", "wb").write(anaksor.export.to_docx(pages))
"""

from __future__ import annotations

from .searchable_pdf import build_pdf
from .word import build_docx

__all__ = ["to_docx", "to_pdf", "to_text"]


def to_text(pages, page_break: str = "\f") -> str:
    """Text of every page in reading order, pages separated by a form feed."""
    return page_break.join(p["text"] for p in pages)


def to_pdf(pages, title: str = "Khmer OCR", jpeg_quality: int = 85) -> bytes:
    """Searchable PDF (page images plus an invisible text layer). Pages need "image"."""
    missing = [i + 1 for i, p in enumerate(pages) if p.get("image") is None]
    if missing:
        raise ValueError(f"pages {missing} have no image: read them with keep_images=True")
    return build_pdf(pages, title=title, jpeg_quality=jpeg_quality)


def to_docx(pages, title: str = "Khmer OCR", highlight_low: bool = False) -> bytes:
    """Word file rebuilt from the layout; highlight_low marks lines read with low confidence."""
    return build_docx(pages, title=title, highlight_low=highlight_low)
