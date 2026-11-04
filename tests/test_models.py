import hashlib
import io
import pickle

import pytest
import torch
from safetensors.torch import save_file

from anaksor import models
from anaksor.models import WeightsError, load_into, load_spec, load_state_dict, resolve_weights


def test_bundled_specs_load():
    det, rec = load_spec("det-repvit-db-v2"), load_spec("rec-svtrv2-v3")
    assert det.kind == "det" and det.weights_file.endswith(".safetensors")
    assert rec.kind == "rec" and rec.config["crop"] == {"pad_y": 0.22, "pad_x": 0.20}
    assert models.data_path("khmer_dict_v3.txt").is_file()


def test_bad_specs_are_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_spec("no-such-model")
    p = tmp_path / "x.yml"
    p.write_text("kind: other\n")
    with pytest.raises(ValueError):
        load_spec(p)
    p.write_text("!!python/object/apply:os.system ['echo pwned']\n")
    with pytest.raises(Exception, match="(?i)constructor|could not determine"):
        load_spec(p)  # yaml.safe_load: no object construction


def test_resolve_order(tmp_path, monkeypatch):
    spec = load_spec("det-repvit-db-v2")
    with pytest.raises(WeightsError):
        resolve_weights(spec, tmp_path / "missing.safetensors")
    with pytest.raises(WeightsError, match="downloads are off"):
        resolve_weights(spec, download=False)
    local = tmp_path / "w"
    local.mkdir()
    (local / spec.weights_file).write_bytes(b"x")
    monkeypatch.setenv("ANAKSOR_WEIGHTS_DIR", str(local))
    assert resolve_weights(spec) == local / spec.weights_file


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_download_verifies_checksum_and_is_atomic(tmp_path, monkeypatch):
    payload = b"weights" * 1000
    monkeypatch.setattr(models.urllib.request, "urlopen", lambda req, timeout: _Resp(payload))
    dest = tmp_path / "a.safetensors"
    models._download("https://example.org/a", dest, hashlib.sha256(payload).hexdigest())
    assert dest.read_bytes() == payload
    bad = tmp_path / "b.safetensors"
    with pytest.raises(WeightsError, match="SHA-256"):
        models._download("https://example.org/b", bad, "0" * 64)
    assert not bad.exists() and not list(tmp_path.glob(".b.safetensors.*"))  # no partial file left
    with pytest.raises(WeightsError, match="non-HTTPS"):
        models._download("http://example.org/a", tmp_path / "c", None)


class Evil:
    def __reduce__(self):
        return (print, ("code ran",))


def test_pickled_code_is_never_executed(tmp_path, capsys):
    p = tmp_path / "evil.pth"
    with open(p, "wb") as f:
        torch.save({"state_dict": {"w": torch.zeros(1)}, "x": Evil()}, f, pickle_module=pickle)
    with pytest.raises(WeightsError, match="safely"):
        load_state_dict(p)
    assert "code ran" not in capsys.readouterr().out


def test_load_into_requires_every_tensor(tmp_path):
    model = torch.nn.Sequential(torch.nn.Linear(2, 3), torch.nn.Linear(3, 1))
    full = tmp_path / "full.safetensors"
    save_file({k: v.contiguous() for k, v in model.state_dict().items()}, str(full))
    load_into(model, full)
    part = tmp_path / "part.safetensors"
    save_file({"0.weight": torch.zeros(3, 2)}, str(part))
    with pytest.raises(WeightsError, match="lacks"):
        load_into(model, part)
    wrong = tmp_path / "wrong.pt"
    torch.save({"state_dict": {k: torch.zeros(7) for k in model.state_dict()}}, wrong)
    with pytest.raises(WeightsError):
        load_into(model, wrong)


def test_defaults_are_the_published_release():
    """rec v4 / mobile DBNet++ from Sokheng/anaksor-ocr, every file pinned by its SHA-256."""
    assert (models.DET_DEFAULT, models.REC_DEFAULT) == ("det-repvit-dbpp-v1", "rec-svtrv2-v4")
    assert models.HF_REPO == "Sokheng/anaksor-ocr"
    assert load_spec(models.DET_DEFAULT).architecture["Neck"]["use_asf"] is True
    for name in (models.DET_DEFAULT, models.REC_DEFAULT):
        spec = load_spec(name)
        for file, sha in ((spec.weights_file, spec.sha256), (spec.onnx_file, spec.onnx_sha256)):
            assert file and sha and len(sha) == 64 and int(sha, 16) >= 0, (name, file)
    rec = load_spec(models.REC_DEFAULT)
    assert rec.config["architecture"]["Encoder"]["dims"] == [128, 256, 384]  # SVTRv2-B
    assert rec.config["charset"]["dict"] == "khmer_dict_v3.txt"


def test_unverified_weights_are_not_downloaded(tmp_path, monkeypatch):
    """A spec without a SHA-256 (the unpublished v2 / v3) never reaches the network."""
    monkeypatch.setenv("ANAKSOR_HOME", str(tmp_path))
    monkeypatch.delenv("ANAKSOR_WEIGHTS_DIR", raising=False)
    monkeypatch.delenv("ANAKSOR_ALLOW_UNVERIFIED", raising=False)
    called = []
    monkeypatch.setattr(models, "_download", lambda url, dest, sha: called.append(url))
    with pytest.raises(WeightsError, match="no SHA-256"):
        resolve_weights(load_spec("rec-svtrv2-v3"))
    assert not called
    monkeypatch.setenv("ANAKSOR_ALLOW_UNVERIFIED", "1")
    resolve_weights(load_spec("rec-svtrv2-v3"))
    assert called == [
        "https://huggingface.co/Sokheng/anaksor-ocr/resolve/7b88e650814bb93a7a1b78524f980631d5806df8/khmer_rec_svtrv2_v3.safetensors"
    ]


def test_published_weights_download_from_the_release(tmp_path, monkeypatch):
    monkeypatch.setenv("ANAKSOR_HOME", str(tmp_path))
    monkeypatch.delenv("ANAKSOR_WEIGHTS_DIR", raising=False)
    monkeypatch.delenv("ANAKSOR_HF_REVISION", raising=False)
    seen = []
    monkeypatch.setattr(models, "_download", lambda url, dest, sha: seen.append((url, sha)))
    spec = load_spec("rec-svtrv2-v4")
    resolve_weights(spec, fmt="onnx")
    assert seen == [
        (
            "https://huggingface.co/Sokheng/anaksor-ocr/resolve/7b88e650814bb93a7a1b78524f980631d5806df8/khmer_rec_svtrv2_latest.onnx",
            spec.onnx_sha256,
        )
    ]


@pytest.mark.parametrize("env", [None, "rec-v4-det-dbpp-v1"])
def test_det_v3_downloads_from_its_own_commit(tmp_path, monkeypatch, env):
    monkeypatch.setenv("ANAKSOR_HOME", str(tmp_path))
    monkeypatch.delenv("ANAKSOR_WEIGHTS_DIR", raising=False)
    if env:
        monkeypatch.setenv("ANAKSOR_HF_REVISION", env)
    else:
        monkeypatch.delenv("ANAKSOR_HF_REVISION", raising=False)
    seen = []
    monkeypatch.setattr(models, "_download", lambda url, dest, sha: seen.append(url))
    path = resolve_weights(load_spec("det-repvit-db-v3"))
    assert seen == [
        "https://huggingface.co/Sokheng/anaksor-ocr/resolve/5c9f76c7ff6b5dd51c9e83c7ec69c63be5f5611d/khmer_det_repvit_db_latest.safetensors"
    ]
    assert path.parent.name == "5c9f76c7ff6b5dd51c9e83c7ec69c63be5f5611d"
