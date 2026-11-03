# Changelog

## 0.1.1 (2026-11-03)

No code changes: the package is the same as 0.1.0.

- README: badges, a quick start, examples of real pages read by the released models (line
  boxes drawn on each photo, the text of a road sign), and image credits.
- Release steps in the README match the release workflow: bump, tag, then approve the `pypi`
  environment.

## 0.1.0 (2026-11-03)

First release, extracted from the Alpha-OCR project that serves https://ocr.sokhengdin.dev.

- `anaksor.OCR`: detection (DBNet, RepViT) and recognition (SVTRv2, CTC) of Khmer text,
  reading order with columns, receipts and paragraphs, long lines read in stitched windows.
- PDF input (`anaksor-ocr[pdf]`), searchable PDF and Word export (`anaksor-ocr[docx]`).
- `anaksor` command line.
- Weights as `.safetensors`, downloaded on first use and checksum-verified.
- Line crop margin 0.22 / 0.20 of the line height for the v3 recogniser.
- Default models: recognition v4 (SVTRv2-B, crop margin 0.16 / 0.10) and detection v3,
  published at https://huggingface.co/Sokheng/anaksor-ocr (tag `rec-v4-det-v3`). The v2 / v3
  specs stay bundled (`"det-repvit-db-v2"`, `"rec-svtrv2-v3"`); their weights aren't published.
- Weights are only downloaded when the spec pins their SHA-256 (`ANAKSOR_ALLOW_UNVERIFIED=1`
  for your own unhashed uploads). They come from the release's Hub commit (`5c9f76c`, the
  repo's `_latest` files there), not `main`; `ANAKSOR_HF_REVISION` picks another.
- Own implementation of the networks (`anaksor.nets`: RepViT + DBNet, SVTRv2 with RCTC and
  SMTR heads), the DB box extraction and the CTC / SMTR decoding; no vendored OpenOCR code.
- `[export]` needs `onnx>=1.22` (earlier releases have the external-data path traversal and
  shape-inference advisories fixed in 1.21 / 1.22).
  Checkpoints trained in Alpha-OCR (`.pth` or converted `.safetensors`) load unchanged, and
  the outputs match the training-time implementation (golden tests in `tests/data`).
- CPPD recognisers (`CPPDDecoder`); long lines without CTC positions are joined on the
  overlap of their windows' texts.
- `tools/spec_from_config.py`: a spec from any Alpha-OCR training config (rec v2/v3/v4,
  CPPD, det v2/v3), so its `best.pth` loads directly.
- Two backends: ONNX Runtime (default install, no PyTorch) and PyTorch (`[torch]`), chosen
  with `backend=` / `--backend`; same boxes and text. `tools/export_onnx.py` exports the
  detector and the CTC / CPPD recognisers with dynamic shapes, checked against PyTorch.
  Specs name the graph in `weights.onnx` (+ `onnx_sha256`).
- Batch norms and RepViT's re-parameterisable branches are folded into single convolutions
  when a model loads (`fuse=True`): same output, detection about 2.5x faster on CPU.
