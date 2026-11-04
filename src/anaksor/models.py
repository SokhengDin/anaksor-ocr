"""Model specs and weights: where they come from and how they are loaded.

Weights are resolved in this order:

1. an explicit path (``OCR(det_weights=..., rec_weights=...)``);
2. ``$ANAKSOR_WEIGHTS_DIR/<file>``;
3. the cache, ``$ANAKSOR_HOME`` (default ``~/.cache/anaksor``), filled on first use by a
   download from the Hugging Face repo ``$ANAKSOR_HF_REPO`` at ``$ANAKSOR_HF_REVISION``
   (a spec's ``weights.revision``, when it has one, wins).

A spec names a PyTorch weights file (``weights.file``) and, optionally, the exported ONNX
graph (``weights.onnx``) for the onnx backend, each with its SHA-256. A file is only
downloaded when its spec gives a SHA-256 to check it against (``ANAKSOR_ALLOW_UNVERIFIED=1``
lifts that, for weights you publish yourself and haven't hashed yet).

Loading never unpickles code: ``.safetensors`` files are read with safetensors, and
``.pth`` / ``.pt`` checkpoints with ``torch.load(weights_only=True)``. Downloads are
HTTPS only, written atomically, and checked against the spec's SHA-256 before they are used.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

import yaml

DET_DEFAULT = "det-repvit-dbpp-v1"
REC_DEFAULT = "rec-svtrv2-v4"
_BUNDLED = {
    DET_DEFAULT: "det_repvit_dbpp_v1.yml",
    REC_DEFAULT: "rec_svtrv2_v4.yml",
    "det-repvit-db-v3": "det_repvit_db_v3.yml",  # pinned to its own Hub commit (weights.revision)
    "det-repvit-db-v2": "det_repvit_db_v2.yml",  # earlier models: their weights aren't published
    "rec-svtrv2-v3": "rec_svtrv2_v3.yml",
}

HF_ENDPOINT = "https://huggingface.co"
HF_REPO = "Sokheng/anaksor-ocr"
# The Hub commit of the rec v4 + mobile DBNet++ release: its _latest files, never main's moving ones.
HF_REVISION = "7b88e650814bb93a7a1b78524f980631d5806df8"


def _hub() -> tuple[str, str, str]:
    """(endpoint, repo, revision), read from the environment on every call."""
    return (
        os.getenv("ANAKSOR_HF_ENDPOINT", HF_ENDPOINT).rstrip("/"),
        os.getenv("ANAKSOR_HF_REPO", HF_REPO),
        os.getenv("ANAKSOR_HF_REVISION", HF_REVISION),
    )


class WeightsError(RuntimeError):
    """Weights are missing, failed to download, or don't match their checksum."""


@dataclass(frozen=True)
class ModelSpec:
    name: str
    kind: str  # "det" or "rec"
    weights_file: str
    sha256: str | None
    config: dict = field(repr=False)
    source: str = ""  # file the spec was read from
    onnx_file: str = ""  # exported graph for the onnx backend
    onnx_sha256: str | None = None
    revision: str | None = None  # Hub commit of its files, when not the release's

    @property
    def architecture(self) -> dict:
        return self.config["architecture"]


def data_path(name: str) -> Path:
    """Path of a file shipped in anaksor/data."""
    return Path(str(resources.files("anaksor") / "data" / name))


def load_spec(name_or_path: str | os.PathLike | ModelSpec) -> ModelSpec:
    """A bundled spec by name (``det-repvit-dbpp-v1``, ``rec-svtrv2-v4``, or the earlier ones) or a spec YAML file."""
    if isinstance(name_or_path, ModelSpec):
        return name_or_path
    key = str(name_or_path)
    path = data_path(_BUNDLED[key]) if key in _BUNDLED else Path(key)
    if not path.is_file():
        raise FileNotFoundError(f"unknown model {key!r}: not one of {list(_BUNDLED)} and not a file")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict) or cfg.get("kind") not in ("det", "rec") or "architecture" not in cfg:
        raise ValueError(f"{path}: not an anaksor model spec (needs kind: det|rec and architecture)")
    w = cfg.get("weights") or {}
    return ModelSpec(
        name=cfg.get("name", path.stem),
        kind=cfg["kind"],
        weights_file=w.get("file", ""),
        sha256=w.get("sha256"),
        config=cfg,
        source=str(path),
        onnx_file=w.get("onnx", "") or "",
        onnx_sha256=w.get("onnx_sha256"),
        revision=w.get("revision"),
    )


def cache_dir() -> Path:
    home = os.getenv("ANAKSOR_HOME")
    if home:
        return Path(home).expanduser()
    base = os.getenv("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "anaksor"


def resolve_weights(spec: ModelSpec, weights: str | os.PathLike | None = None, download: bool = True, fmt: str = "torch") -> Path:
    """Local path of the spec's weights (see the module docstring for the order); ``fmt``
    "torch" for the PyTorch weights, "onnx" for the exported graph."""
    if fmt not in ("torch", "onnx"):
        raise ValueError(f"fmt must be torch or onnx, not {fmt!r}")
    if weights is not None:
        p = Path(weights).expanduser()
        if not p.is_file():
            raise WeightsError(f"weights not found: {p}")
        if (p.suffix == ".onnx") != (fmt == "onnx"):
            want = "an exported .onnx graph" if fmt == "onnx" else ".safetensors or .pth weights"
            raise WeightsError(f"the {fmt} backend needs {want}, not {p.name}")
        return p
    name, sha = (spec.onnx_file, spec.onnx_sha256) if fmt == "onnx" else (spec.weights_file, spec.sha256)
    if not name:
        hint = " (export one with tools/export_onnx.py, or use the torch backend)" if fmt == "onnx" else ""
        raise WeightsError(f"model {spec.name} names no {fmt} weights file{hint}; pass the weights path")
    local = os.getenv("ANAKSOR_WEIGHTS_DIR")
    if local and (Path(local).expanduser() / name).is_file():
        return Path(local).expanduser() / name
    endpoint, repo, revision = _hub()
    revision = spec.revision or revision
    cached = cache_dir() / revision / name
    if cached.is_file():
        return cached
    if not download:
        raise WeightsError(f"{name} is not in {cached.parent} and downloads are off")
    if not sha and os.getenv("ANAKSOR_ALLOW_UNVERIFIED", "") != "1":
        raise WeightsError(
            f"model {spec.name} gives no SHA-256 for {name}, so it isn't downloaded (an unchecked file could be "
            f"anything). Pass the weights path, or set ANAKSOR_ALLOW_UNVERIFIED=1 for weights you published yourself."
        )
    url = f"{endpoint}/{repo}/resolve/{urllib.parse.quote(revision)}/{name}"
    _download(url, cached, sha)
    return cached


def _download(url: str, dest: Path, sha256: str | None) -> None:
    if urllib.parse.urlparse(url).scheme != "https":
        raise WeightsError(f"refusing to download weights over a non-HTTPS URL: {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "anaksor-ocr"}
    token = os.getenv("HF_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    print(f"anaksor: downloading {dest.name} to {dest.parent}", file=sys.stderr)
    digest = hashlib.sha256()
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=".part")
    try:
        req = urllib.request.Request(url, headers=headers)  # noqa: S310 (scheme checked above)
        with os.fdopen(fd, "wb") as out, urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            while chunk := resp.read(1 << 20):
                digest.update(chunk)
                out.write(chunk)
        if sha256 and digest.hexdigest() != sha256.lower():
            raise WeightsError(f"{dest.name}: SHA-256 {digest.hexdigest()} does not match the expected {sha256}")
        shutil.move(tmp, dest)
    except WeightsError:
        raise
    except Exception as e:
        raise WeightsError(
            f"could not download {url}: {e}. Download it yourself and pass its path, or put it in $ANAKSOR_WEIGHTS_DIR."
        ) from e
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def sha256_file(path: str | os.PathLike) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def pick_device(device: str = "auto"):
    """torch.device for "auto" (CUDA, then Apple MPS, then CPU) or an explicit name."""
    import torch

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    return torch.device(device)


def load_state_dict(path: str | os.PathLike) -> dict:
    """Tensors of a weights file, without executing any code from it."""
    import torch

    path = Path(path)
    if path.suffix == ".safetensors":
        from safetensors.torch import load_file

        return load_file(str(path), device="cpu")
    try:
        ckpt = torch.load(str(path), map_location="cpu", weights_only=True)
    except Exception as e:
        raise WeightsError(
            f"{path.name} can't be loaded safely ({type(e).__name__}: {e}). Convert it with "
            f"`python tools/convert_weights.py {path.name}` in a trusted environment."
        ) from e
    state = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else None
    if not isinstance(state, dict):
        raise WeightsError(f"{path.name}: no state dict inside")
    if state and all(k.startswith("module.") for k in state):  # saved from a DistributedDataParallel wrapper
        state = {k.removeprefix("module."): v for k, v in state.items()}
    return state


def load_into(model, path: str | os.PathLike) -> None:
    """Load weights into a model. Every tensor of the model must be present with the
    right shape; anything else means the weights belong to another architecture."""
    state = load_state_dict(path)
    own = model.state_dict()
    ok = {k: v for k, v in state.items() if k in own and tuple(v.shape) == tuple(own[k].shape)}
    missing = [k for k in own if k not in ok and not k.endswith("num_batches_tracked")]
    if missing:
        raise WeightsError(
            f"{Path(path).name} lacks {len(missing)} of the model's {len(own)} tensors "
            f"(e.g. {missing[:3]}): weights for another model?"
        )
    model.load_state_dict(ok, strict=False)
