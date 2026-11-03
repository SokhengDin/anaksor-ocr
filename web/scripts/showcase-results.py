"""Read the showcase photos with the real models and save each result next to its photo.

    .venv/bin/python web/scripts/showcase-results.py      # from the repository root

public/showcase/<id>.jpg -> public/showcase/<id>.json, in the OCR API's shape (src/lib/types.ts
OcrPage: `results` for the blocks, `time` in seconds plus `timing`), so the site can show them
like the demo's sample. Run it again whenever a photo changes. The weights come from the cache
(`anaksor --fetch-models` downloads them).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from anaksor import OCR

SHOWCASE = Path(__file__).resolve().parent.parent / "public" / "showcase"
IDS = ("document", "receipt", "sign")
EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def api_page(page: dict) -> dict:
    """A page from OCR.read() in the API's shape, scores rounded to keep the file small."""

    def scores(item: dict) -> dict:
        return {**item, "rec_score": round(item["rec_score"], 3), "det_score": round(item["det_score"], 3)}

    return {
        "text": page["text"],
        "results": [scores(b) for b in page["blocks"]],
        "lines": [scores(line) for line in page["lines"]],
        "width": page["width"],
        "height": page["height"],
        "time": page["time"]["total"],
        "timing": page["time"],
    }


def main() -> int:
    ocr = OCR()
    for id_ in IDS:
        photo = next((SHOWCASE / f"{id_}{ext}" for ext in EXTENSIONS if (SHOWCASE / f"{id_}{ext}").is_file()), None)
        if photo is None:
            print(f"skip {id_}: no photo in {SHOWCASE}", file=sys.stderr)
            continue
        page = api_page(ocr.read(photo)[0])
        out = SHOWCASE / f"{id_}.json"
        out.write_text(json.dumps(page, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{photo.name} -> {out.name}: {len(page['lines'])} lines, {page['time']:.2f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
