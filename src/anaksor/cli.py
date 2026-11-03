"""Command line: ``anaksor scan.pdf -o scan.docx``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FORMATS = ("text", "json", "pdf", "docx")
_EXT = {"text": ".txt", "json": ".json", "pdf": ".pdf", "docx": ".docx"}
_BY_EXT = {".txt": "text", ".md": "text", ".json": "json", ".pdf": "pdf", ".docx": "docx"}


def parse_pages(spec: str | None) -> list[int] | None:
    """'1-3,5' to [1, 2, 3, 5]."""
    if not spec:
        return None
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        a, sep, b = part.partition("-")
        try:
            lo, hi = int(a), int(b) if sep else int(a)
        except ValueError:
            raise argparse.ArgumentTypeError(f"bad page range {part!r} (use e.g. 1-3,5)") from None
        if lo < 1 or hi < lo:
            raise argparse.ArgumentTypeError(f"bad page range {part!r}")
        pages.extend(range(lo, hi + 1))
    return pages


def build_parser() -> argparse.ArgumentParser:
    from . import __version__

    p = argparse.ArgumentParser(
        prog="anaksor",
        description="Khmer OCR: images and PDFs to text, JSON, searchable PDF or Word.",
        epilog="Examples:\n  anaksor photo.jpg\n  anaksor scan.pdf -o scan.docx\n  anaksor a.jpg b.png -o out/ -f json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("inputs", nargs="*", type=Path, help="images (JPEG, PNG, WEBP, BMP, TIFF) or PDFs")
    p.add_argument(
        "-o", "--output", type=Path, help="output file, or a directory for several inputs (default: stdout for text/json)"
    )
    p.add_argument("-f", "--format", choices=FORMATS, help="default: from the output's extension, else text")
    p.add_argument("--pages", type=parse_pages, help="PDF pages to read, e.g. 1-3,5 (default: all)")
    p.add_argument("--dpi", type=int, default=200, help="PDF render resolution (default: 200)")
    p.add_argument("--device", default="auto", help="auto, cpu, cuda, cuda:1, mps (default: auto)")
    p.add_argument(
        "--backend", choices=("auto", "torch", "onnx"), default="auto", help="torch or onnx runtime (default: torch if installed)"
    )
    p.add_argument("--det-weights", type=Path, help="detection weights file (default: cached download)")
    p.add_argument("--rec-weights", type=Path, help="recognition weights file (default: cached download)")
    p.add_argument("--pad-y", type=float, help="line crop margin above and below, fraction of line height")
    p.add_argument("--pad-x", type=float, help="line crop margin left and right")
    p.add_argument("--min-score", type=float, default=0.5, help="drop lines read below this confidence")
    p.add_argument("--highlight-low", action="store_true", help="Word: highlight low-confidence lines")
    p.add_argument("--fetch-models", action="store_true", help="download the model weights and exit")
    p.add_argument("--version", action="version", version=f"anaksor {__version__}")
    return p


def _out_path(args, src: Path, fmt: str, many: bool) -> Path | None:
    if args.output is None:
        return None
    if many or args.output.is_dir():
        args.output.mkdir(parents=True, exist_ok=True)
        return args.output / (src.stem + _EXT[fmt])
    return args.output


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    from .models import DET_DEFAULT, REC_DEFAULT, WeightsError, load_spec, resolve_weights

    if args.fetch_models:
        try:
            from .runtime import choose_backend

            for name, w in ((DET_DEFAULT, args.det_weights), (REC_DEFAULT, args.rec_weights)):
                fmt = choose_backend(args.backend, w)
                print(f"{name}: {resolve_weights(load_spec(name), w, fmt=fmt)}")
        except WeightsError as e:
            print(f"anaksor: {e}", file=sys.stderr)
            return 1
        return 0
    if not args.inputs:
        parser.error("give at least one image or PDF")
    fmt = args.format or _BY_EXT.get(args.output.suffix.lower() if args.output else "", "text")
    many = len(args.inputs) > 1
    if fmt in ("pdf", "docx") and args.output is None:
        parser.error(f"{fmt} output needs -o FILE")
    if many and args.output is not None and args.output.suffix and not args.output.is_dir():
        parser.error("several inputs: -o must be a directory")
    for src in args.inputs:
        if not src.is_file():
            parser.error(f"no such file: {src}")

    from . import export
    from .inputs import InputError
    from .ocr import OCR

    try:
        ocr = OCR(
            device=args.device,
            backend=args.backend,
            det_weights=args.det_weights,
            rec_weights=args.rec_weights,
            pad_y=args.pad_y,
            pad_x=args.pad_x,
            min_rec_score=args.min_score,
        )
    except (WeightsError, ValueError, ImportError) as e:
        print(f"anaksor: {e}", file=sys.stderr)
        return 1

    status = 0
    for src in args.inputs:
        try:
            pages = ocr.read(src, pages=args.pages, dpi=args.dpi, keep_images=fmt == "pdf")
        except (InputError, ImportError) as e:
            print(f"anaksor: {src}: {e}", file=sys.stderr)
            status = 1
            continue
        out = _out_path(args, src, fmt, many)
        if fmt == "text":
            data: str | bytes = export.to_text(pages) + "\n"
        elif fmt == "json":
            data = json.dumps({"file": str(src), "pages": pages}, ensure_ascii=False, indent=1) + "\n"
        elif fmt == "pdf":
            data = export.to_pdf(pages, title=src.stem)
        else:
            data = export.to_docx(pages, title=src.stem, highlight_low=args.highlight_low)
        if out is None:
            sys.stdout.write(data if isinstance(data, str) else data.decode())
        elif isinstance(data, bytes):
            out.write_bytes(data)
        else:
            out.write_text(data, encoding="utf-8")
        if out is not None:
            print(f"{src} -> {out}", file=sys.stderr)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
