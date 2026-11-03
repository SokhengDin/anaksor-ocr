"""Searchable PDF: each page is the page image with every line's text laid over it in
invisible text (render mode 3), positioned, rotated and stretched to the line's box. The
page looks exactly like the scan while its text can be selected, searched and copied in
reading order.

The text uses a one-glyph "glyphless" font (Identity-H, CID = Unicode code point, identity
ToUnicode map), the approach of Tesseract and OCRmyPDF: no Khmer shaping is needed because
nothing is drawn, and copy/paste returns the recognised Unicode text unchanged.

A page is an OCR result with its "image" (``OCR.read(..., keep_images=True)``);
"width"/"height" are the frame the coordinates refer to and "size_pt" (optional, set for
PDF input) the page size in points. Images without it are fitted to A4.
"""

from __future__ import annotations

import io
import zlib

from ..geometry import line_geometry
from ..models import data_path

A4_PT = (595.28, 841.89)


class _Pdf:
    def __init__(self):
        self.objs = []

    def add(self, body: bytes) -> int:
        self.objs.append(body)
        return len(self.objs)

    def stream(self, data: bytes, extra: str = "", compress: bool = True) -> int:
        if compress:
            data = zlib.compress(data, 9)
            extra += " /Filter /FlateDecode"
        return self.add(f"<< /Length {len(data)}{extra} >>\nstream\n".encode() + data + b"\nendstream")

    def output(self, root: int, info: int) -> bytes:
        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, body in enumerate(self.objs, 1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(self.objs) + 1}\n0000000000 65535 f \n".encode()
        out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
        out += f"trailer\n<< /Size {len(self.objs) + 1} /Root {root} 0 R /Info {info} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        return bytes(out)


def _pdf_str(s: str) -> str:
    return "<FEFF" + s.encode("utf-16-be").hex().upper() + ">"


def _glyphless_font(pdf: _Pdf) -> int:
    ttf = data_path("glyphless.ttf").read_bytes()
    file2 = pdf.stream(ttf, f" /Length1 {len(ttf)}")
    desc = pdf.add(
        f"<< /Type /FontDescriptor /FontName /GlyphLessFont /Flags 5 /FontBBox [0 -200 500 800] "
        f"/ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 800 /StemV 80 /FontFile2 {file2} 0 R >>".encode()
    )
    cid2gid = pdf.stream(b"\x00\x01" * 65536)  # every CID → the one blank glyph
    cidfont = pdf.add(
        f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /GlyphLessFont "
        f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
        f"/FontDescriptor {desc} 0 R /DW 500 /CIDToGIDMap {cid2gid} 0 R >>".encode()
    )
    ranges = [f"<{h:02X}00> <{h:02X}FF> <{h:02X}00>" for h in range(256)]
    blocks = "".join(
        f"{len(c)} beginbfrange\n" + "\n".join(c) + "\nendbfrange\n" for c in (ranges[i : i + 100] for i in range(0, 256, 100))
    )
    cmap = (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
        "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        + blocks
        + "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
    )
    tounicode = pdf.stream(cmap.encode())
    return pdf.add(
        f"<< /Type /Font /Subtype /Type0 /BaseFont /GlyphLessFont /Encoding /Identity-H "
        f"/DescendantFonts [{cidfont} 0 R] /ToUnicode {tounicode} 0 R >>".encode()
    )


def _page_size(page) -> tuple:
    if page.get("size_pt"):
        return tuple(page["size_pt"])
    w, h = page["width"], page["height"]  # images: fit to A4, keep the aspect
    k = min(A4_PT[0] / w, A4_PT[1] / h) if w <= h else min(A4_PT[1] / w, A4_PT[0] / h)
    return w * k, h * k


def _text_ops(page, W, H) -> str:
    k = W / page["width"]
    ops = ["BT", "3 Tr"]  # 3 = invisible
    for ln in page["lines"]:
        text = "".join(c for c in ln.get("text", "") if ord(c) <= 0xFFFF)
        if not text.strip() or not ln.get("quads"):
            continue
        origin, d, w_px, h_px = line_geometry(ln["quads"])
        fs = max(h_px * k, 1.0)
        ax, ay = d[0], -d[1]  # text direction, PDF y-up
        ux, uy = -ay, ax  # up
        ox, oy = origin[0] * k + ux * 0.2 * fs, H - origin[1] * k + uy * 0.2 * fs  # baseline above descent
        tz = 100.0 * (w_px * k) / (len(text) * 0.5 * fs)
        ops.append(
            f"/F1 {fs:.2f} Tf {tz:.2f} Tz {ax:.5f} {ay:.5f} {ux:.5f} {uy:.5f} {ox:.2f} {oy:.2f} Tm "
            f"<{text.encode('utf-16-be').hex().upper()}> Tj"
        )
    ops.append("ET")
    return "\n".join(ops)


def build_pdf(pages, title: str = "Khmer OCR", jpeg_quality: int = 85) -> bytes:
    """Searchable PDF from page results that carry their "image" (see the module docstring)."""
    pdf = _Pdf()
    font = _glyphless_font(pdf)
    pages_id = len(pdf.objs) + 1 + 3 * len(pages)  # Pages object comes after all page objects
    kids = []
    for page in pages:
        W, H = _page_size(page)
        img = page["image"].convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=jpeg_quality)
        im = pdf.stream(
            buf.getvalue(),
            f" /Type /XObject /Subtype /Image /Width {img.width} /Height {img.height} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode",
            compress=False,
        )
        content = f"q {W:.2f} 0 0 {H:.2f} 0 0 cm /Im0 Do Q\n" + _text_ops(page, W, H)
        cs = pdf.stream(content.encode("latin-1"))
        kids.append(
            pdf.add(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {W:.2f} {H:.2f}] "
                f"/Resources << /XObject << /Im0 {im} 0 R >> /Font << /F1 {font} 0 R >> >> "
                f"/Contents {cs} 0 R >>".encode()
            )
        )
    assert pdf.add(f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>".encode()) == pages_id
    root = pdf.add(f"<< /Type /Catalog /Pages {pages_id} 0 R /Lang (km) >>".encode())
    info = pdf.add(f"<< /Title {_pdf_str(title)} /Producer (anaksor-ocr) /Creator (anaksor-ocr) >>".encode())
    return pdf.output(root, info)
