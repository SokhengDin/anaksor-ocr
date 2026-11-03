"""Word (.docx) from the OCR layout, rebuilt from geometry only (``anaksor-ocr[docx]``).

* headings: one or two lines clearly taller than the page's body text;
* alignment: centred and right-aligned blocks from their margins in the text area;
* indentation: left and first-line indents from x positions;
* prose versus lists and forms: lines that run to the block's right edge are reflowed into
  one paragraph (Khmer lines join without a space, other scripts with one); short or
  ragged lines (addresses, receipts, poems) keep their line breaks;
* receipts and forms: a value far to the right of its label, at the right margin, goes
  after a right-aligned tab stop, so prices line up on the right as on the paper;
* one Word page per input page.
"""

from __future__ import annotations

import io

import numpy as np

from ..geometry import line_geometry

LOW_SCORE = 0.7
KHMER_FONT = "Khmer OS Siemreap"  # the usual Khmer body font in Cambodian offices


def _is_khmer(c: str) -> bool:
    return "ក" <= c <= "៿" or "᧠" <= c <= "᧿"


def _join(a: str, b: str) -> str:
    """Join two reflowed lines: Khmer words carry no spaces, so a Khmer line break is
    a word boundary and joins without one; anything else gets a space."""
    if not a or not b:
        return ""
    return "" if _is_khmer(a[-1]) and _is_khmer(b[0]) else " "


def _font(run_or_style, size_pt=None, bold=None):
    from docx.oxml.ns import qn
    from docx.shared import Pt

    f = run_or_style.font
    f.name = KHMER_FONT
    rpr = (run_or_style.element if hasattr(run_or_style, "element") else run_or_style._element).get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), KHMER_FONT)
    if size_pt:
        f.size = Pt(size_pt)
        szcs = rpr.find(qn("w:szCs"))
        if szcs is None:
            szcs = rpr.makeelement(qn("w:szCs"), {})
            rpr.append(szcs)
        szcs.set(qn("w:val"), str(int(round(size_pt * 2))))
    if bold is not None:
        f.bold = bold
        f.cs_bold = bold


def _max_gap(quads) -> float:
    """Widest horizontal gap between consecutive boxes of a line (px)."""
    xs = sorted((min(p[0] for p in q), max(p[0] for p in q)) for q in quads)
    return max([b[0] - a[1] for a, b in zip(xs, xs[1:])] or [0.0])


def _blocks_layout(page):
    """Per block: dict(lines, heading level, alignment, indents, reflow, size)."""
    lines = page["lines"]
    if not lines:
        return []
    geo = [line_geometry(l["quads"]) for l in lines]
    hs = np.array([g[3] for g in geo])
    med = float(np.median(hs)) or 1.0
    x0s = np.array([min(p[0] for p in l["box"]) for l in lines])
    x1s = np.array([max(p[0] for p in l["box"]) for l in lines])
    ax0, ax1 = float(x0s.min()), float(x1s.max())
    aw = max(ax1 - ax0, 1.0)
    out = []
    for b in page["blocks"]:
        idx = [i for i in b["lines"] if lines[i].get("text", "").strip()]
        if not idx:
            continue
        bh = float(np.median(hs[idx]))
        ratio = bh / med
        bx0, bx1 = float(x0s[idx].min()), float(x1s[idx].max())
        bw = max(bx1 - bx0, 1.0)
        nchar = sum(len(lines[i]["text"]) for i in idx)
        heading = 1 if ratio >= 1.7 else 2 if ratio >= 1.3 else 0
        if len(idx) > 2 or nchar > 120:
            heading = 0
        lm, rm = (bx0 - ax0) / aw, (ax1 - bx1) / aw
        if lm > 0.08 and rm > 0.08 and abs(lm - rm) < 0.06:
            align = "center"
        elif lm > 0.3 and rm < 0.04:
            align = "right"
        else:
            align = "left"
        full = sum(1 for i in idx[:-1] if (x1s[i] - x0s[i]) >= 0.8 * bw)
        gapped = any(_max_gap(lines[i]["quads"]) > 2.5 * hs[i] for i in idx)  # label ...... value
        reflow = len(idx) >= 2 and full >= 0.6 * (len(idx) - 1) and align == "left" and not gapped
        first = (float(x0s[idx[0]]) - bx0) / aw if reflow and x0s[idx[0]] - bx0 > bh else 0.0
        out.append(
            {
                "lines": idx,
                "heading": heading,
                "align": align,
                "reflow": reflow,
                "area": (ax0, ax1),
                "left": lm if align == "left" and lm > 0.04 else 0.0,
                "first": first,
                "size": float(np.clip(round(12 * ratio * 2) / 2, 8, 28)),
            }
        )
    return out


def _tabbed(line, area) -> str:
    """Line text with a tab before a last part that sits alone at the right margin."""
    parts, quads = line.get("parts"), line["quads"]
    text = line["text"].strip()
    if not parts or len(parts) != len(quads) or len(parts) < 2:
        return text
    h = line_geometry(quads)[3]
    xs0 = [min(p[0] for p in q) for q in quads]
    xs1 = [max(p[0] for p in q) for q in quads]
    gap = xs0[-1] - xs1[-2]
    at_right = (area[1] - xs1[-1]) < 0.05 * max(area[1] - area[0], 1.0)
    if gap > 2.5 * h and at_right:
        return (" ".join(t for t in parts[:-1] if t).strip() + "\t" + parts[-1].strip()).strip("\t")
    return text


def build_docx(pages, title: str = "Khmer OCR", highlight_low: bool = False) -> bytes:
    """Word file rebuilt from the OCR layout (see the module docstring)."""
    try:
        from docx import Document
    except ImportError as e:
        raise ImportError("Word export needs python-docx: pip install 'anaksor-ocr[docx]'") from e
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX, WD_TAB_ALIGNMENT
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    doc.core_properties.title = title
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(2.5))
    text_cm = 16.0
    _font(doc.styles["Normal"], 12)
    for name in ("Heading 1", "Heading 2"):
        st = doc.styles[name]
        _font(st, None, True)
        st.font.color.rgb = RGBColor(0x16, 0x23, 0x2E)
    align = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER, "right": WD_ALIGN_PARAGRAPH.RIGHT}

    for pi, page in enumerate(pages):
        if pi > 0:
            doc.add_page_break()
        lines = page["lines"]
        for blk in _blocks_layout(page):
            style = f"Heading {blk['heading']}" if blk["heading"] else None
            par = doc.add_paragraph(style=style)
            par.alignment = align[blk["align"]]
            pf = par.paragraph_format
            pf.space_after = Pt(6)
            if blk["left"]:
                pf.left_indent = Cm(round(blk["left"] * text_cm, 2))
            if blk["first"]:
                pf.first_line_indent = Cm(round(blk["first"] * text_cm, 2))
            prev = ""
            for k, i in enumerate(blk["lines"]):
                text = _tabbed(lines[i], blk["area"]) if not blk["reflow"] else lines[i]["text"].strip()
                if "\t" in text and not pf.tab_stops:
                    pf.tab_stops.add_tab_stop(Cm(text_cm - (blk["left"] * text_cm if blk["left"] else 0)), WD_TAB_ALIGNMENT.RIGHT)
                if k > 0:
                    if blk["reflow"]:
                        sep = _join(prev, text)
                        if sep:
                            par.add_run(sep)
                    else:
                        par.add_run().add_break()
                run = par.add_run(text)
                _font(run, blk["size"], True if blk["heading"] else None)
                if highlight_low and lines[i].get("rec_score", 1.0) < LOW_SCORE:
                    run.font.highlight_color = WD_COLOR_INDEX.YELLOW
                prev = text
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
