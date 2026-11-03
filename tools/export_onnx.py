"""Export detector / recogniser weights to ONNX for the onnx backend, and print the SHA-256.

    python tools/export_onnx.py --det khmer_det_repvit_db_v2.safetensors --rec khmer_rec_svtrv2_v3.safetensors --out onnx/
    python tools/export_onnx.py --rec best.pth --rec-spec specs/rec-svtrv2-cppd-khmer.yml --out onnx/

Put each printed file name and SHA-256 into its spec (weights.onnx, weights.onnx_sha256)
and upload the files next to the .safetensors. Needs torch, onnx, onnxscript, onnxruntime.
"""

import argparse
from pathlib import Path

from anaksor import Detector, Recognizer
from anaksor.models import DET_DEFAULT, REC_DEFAULT, load_spec
from anaksor.onnx_export import export_onnx


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--det", type=Path, help="detector weights (.safetensors / .pth)")
    ap.add_argument("--det-spec", default=DET_DEFAULT)
    ap.add_argument("--rec", type=Path, help="recogniser weights (.safetensors / .pth)")
    ap.add_argument("--rec-spec", default=REC_DEFAULT)
    ap.add_argument("--out", type=Path, default=Path("."))
    a = ap.parse_args()
    if not (a.det or a.rec):
        ap.error("give --det and/or --rec")
    jobs = []
    if a.det:
        jobs.append((Detector(a.det_spec, weights=a.det, device="cpu", backend="torch"), a.det_spec))
    if a.rec:
        jobs.append((Recognizer(a.rec_spec, weights=a.rec, device="cpu", backend="torch"), a.rec_spec))
    for model, spec in jobs:
        s = load_spec(spec)
        name = s.onnx_file or Path(s.weights_file or model.weights.name).with_suffix(".onnx").name
        r = export_onnx(model, a.out / name)
        size = Path(r["path"]).stat().st_size / 1e6
        print(
            f"{r['path']}  {size:.1f} MB  max diff to PyTorch {r['max_diff']:.1e}\n  onnx: {name}\n  onnx_sha256: {r['sha256']}"
        )


if __name__ == "__main__":
    main()
