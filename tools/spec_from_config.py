"""Make an anaksor model spec from an Alpha-OCR training config.

    python tools/spec_from_config.py configs/svtrv2_cppd_khmer.yml --out specs/ [--name rec-cppd] [--dict path]
    python tools/spec_from_config.py configs/repvit_db_khmer_v3.yml --out specs/

Writes <out>/<name>.yml and, for a recogniser, copies its character dict next to it. Then

    anaksor.Recognizer("specs/rec-cppd.yml", weights="best.pth")    # or the converted .safetensors

Dict paths in training configs are relative to the OpenOCR/ folder training runs from; the
dict is looked for there, next to the config and in ../ocr/dicts, unless --dict is given.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml


def _find_dict(path: str, config: Path) -> Path:
    p = Path(path)
    roots = [config.parent.parent / "OpenOCR", config.parent, config.parent.parent, config.parent.parent / "ocr" / "dicts"]
    for cand in [p, *(r / p for r in roots), *(r / p.name for r in roots)]:
        if cand.is_file():
            return cand.resolve()
    raise SystemExit(f"character dict {path!r} not found; pass --dict")


def _transform(cfg: dict, name: str) -> dict:
    for t in cfg.get("Eval", {}).get("dataset", {}).get("transforms", []) or []:
        if isinstance(t, dict) and name in t:
            return t[name] or {}
    return {}


def rec_spec(cfg: dict, name: str, dict_name: str) -> dict:
    glob, ev = cfg.get("Global", {}), cfg.get("Eval", {})
    ds, loader, serve = ev.get("dataset", {}), ev.get("loader", {}), cfg.get("Serve", {})
    arch = {k: v for k, v in cfg["Architecture"].items() if k != "Transform" or v}
    return {
        "name": name,
        "kind": "rec",
        "weights": {"file": f"{name}.safetensors", "sha256": None, "onnx": f"{name}.onnx", "onnx_sha256": None},
        "charset": {
            "dict": dict_name,
            "use_space_char": bool(glob.get("use_space_char", True)),
            "max_text_length": glob.get("max_text_length"),
        },
        "input": {
            "base_h": ds.get("base_h", 32),
            "base_shape": ds.get("base_shape", [[64, 64], [96, 48], [112, 40], [128, 32]]),
            "max_ratio": loader.get("max_ratio", 12),
        },
        "crop": {"pad_y": serve.get("crop_pad_y", 0.04), "pad_x": serve.get("crop_pad_x", 0.04)},
        "architecture": arch,
    }


def det_spec(cfg: dict, name: str) -> dict:
    resize, norm = _transform(cfg, "DetResizeForTest"), _transform(cfg, "NormalizeImage")
    post = {k: v for k, v in (cfg.get("PostProcess") or {}).items() if k != "name"}
    post.setdefault("use_dilation", False)
    return {
        "name": name,
        "kind": "det",
        "weights": {"file": f"{name}.safetensors", "sha256": None, "onnx": f"{name}.onnx", "onnx_sha256": None},
        "input": {
            "limit_side_len": resize.get("limit_side_len", 1280),
            "min_side_len": 736,
            "mean": norm.get("mean", [0.485, 0.456, 0.406]),
            "std": norm.get("std", [0.229, 0.224, 0.225]),
        },
        "architecture": cfg["Architecture"],
        "postprocess": {"name": "DBPostProcess", **post},
    }


def convert(config: Path, out: Path, name: str | None = None, dict_path: Path | None = None) -> Path:
    cfg = yaml.safe_load(config.read_text())
    is_det = "Backbone" in cfg.get("Architecture", {})
    name = name or ("det-" if is_det else "rec-") + config.stem.replace("_", "-")
    out.mkdir(parents=True, exist_ok=True)
    if is_det:
        spec = det_spec(cfg, name)
    else:
        src = dict_path or _find_dict(cfg["Global"]["character_dict_path"], config)
        dict_name = f"{name}_dict.txt"
        shutil.copyfile(src, out / dict_name)
        spec = rec_spec(cfg, name, dict_name)
    header = (
        f"# Made by tools/spec_from_config.py from {config.name}. Fill in weights.sha256 (tools/convert_weights.py)\n"
        "# and weights.onnx_sha256 (tools/export_onnx.py) when the files are published.\n"
    )
    dest = out / f"{name}.yml"
    dest.write_text(header + yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, default_flow_style=None))
    return dest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", type=Path)
    ap.add_argument("--out", type=Path, default=Path("."))
    ap.add_argument("--name")
    ap.add_argument("--dict", type=Path, help="character dict, if the config's path doesn't resolve")
    a = ap.parse_args()
    print(convert(a.config, a.out, a.name, a.dict))


if __name__ == "__main__":
    main()
