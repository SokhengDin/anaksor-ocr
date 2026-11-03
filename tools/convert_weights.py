"""Convert a training checkpoint (.pth) to .safetensors and print its SHA-256.

    python tools/convert_weights.py khmer_rec_svtrv2_v3.pth [--out khmer_rec_svtrv2_v3.safetensors]

The release weights are published as .safetensors (no pickle, so loading them can't run
code). The checkpoint is first read with ``torch.load(weights_only=True)``; ``--trust``
falls back to a full unpickle, which runs code from the file: use it only on checkpoints
you produced yourself. Put the printed SHA-256 into the model spec (src/anaksor/data/*.yml).
"""

import argparse
import hashlib
from pathlib import Path

import torch
from safetensors.torch import save_file


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("checkpoint", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--trust", action="store_true", help="allow a full unpickle (your own files only)")
    a = ap.parse_args()
    try:
        ckpt = torch.load(a.checkpoint, map_location="cpu", weights_only=True)
    except Exception as e:
        if not a.trust:
            raise SystemExit(
                f"{a.checkpoint} is not a plain tensor checkpoint ({e}); re-run with --trust if you produced it yourself"
            ) from e
        ckpt = torch.load(a.checkpoint, map_location="cpu", weights_only=False)  # noqa: S614
    state = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else ckpt
    tensors = {k: v.detach().contiguous().clone() for k, v in state.items() if isinstance(v, torch.Tensor)}
    out = a.out or a.checkpoint.with_suffix(".safetensors")
    save_file(tensors, str(out), metadata={"source": a.checkpoint.name})
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"{out}  {len(tensors)} tensors  {out.stat().st_size / 1e6:.1f} MB\nsha256: {digest}")


if __name__ == "__main__":
    main()
