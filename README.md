# anaksor-ocr

**អានអក្សរ**: Khmer OCR for photos, scans and PDFs. It finds the text lines, reads them,
puts them in reading order (columns, receipts, paragraphs) and exports plain text, JSON, a
searchable PDF or a Word file.

Website, with a live demo and the documentation in Khmer and English:
**[ocr.sokhengdin.dev](https://ocr.sokhengdin.dev)**.

| | |
|---|---|
| Detection | DBNet with a RepViT backbone, trained on KhmerST photos and synthetic pages |
| Recognition | SVTRv2 with a CTC head, trained on public Khmer datasets and synthetic lines |
| Layout | deskew, column detection, line growing, paragraphs, long lines read in stitched windows |
| Runs on | ONNX Runtime (CPU, CUDA) by default; PyTorch (CPU, CUDA, Apple MPS) with `[torch]` |

## Install

```bash
pip install anaksor-ocr             # images, ONNX Runtime backend (no PyTorch)
pip install "anaksor-ocr[torch]"    # + PyTorch backend: CUDA / Apple MPS, SMTR head, .pth weights
pip install "anaksor-ocr[all]"      # PyTorch + PDF input + Word export
```

Python 3.11+. For a specific CUDA build of PyTorch, install `torch` from
[pytorch.org](https://pytorch.org/get-started/locally/) first; for ONNX Runtime on CUDA,
`pip install onnxruntime-gpu`. The weights (about 95 MB for ONNX Runtime, 113 MB for PyTorch) download to `~/.cache/anaksor`
on first use.

### Backends

| | `onnx` (default install) | `torch` (`[torch]`) |
|---|---|---|
| Install | no PyTorch (with CUDA, PyTorch is several GB) | PyTorch |
| Devices | CPU; CUDA with `onnxruntime-gpu` | CPU, CUDA, Apple MPS |
| Weights | exported `.onnx` graphs | `.safetensors`, `.pth` checkpoints |
| Heads | CTC, CPPD | CTC, SMTR (`decoder="gtc"` / `"auto"`), CPPD |

`backend="auto"` (also `--backend` on the command line) uses PyTorch when it is installed,
else ONNX Runtime; an `.onnx` weights file always runs in ONNX Runtime. Both give the same
boxes and text. On PyTorch the batch norms are folded into the convolutions when a model
loads (`fuse=True`): same output, detection about 2.5x faster on CPU.

On CPU the two are close; PyTorch is a little faster (6 bench pages, rec v3: 79 s and
0.7 GB peak memory on PyTorch, 99 s and 0.9 GB on ONNX Runtime). ONNX Runtime's gain is the
install. Wide crops are recognised in smaller batches on both, as attention memory grows
with the square of the width.

## Command line

```bash
anaksor photo.jpg                       # text to stdout
anaksor scan.pdf -o scan.docx           # Word, layout rebuilt
anaksor scan.pdf -o scan-searchable.pdf # page images + selectable text
anaksor *.jpg -o out/ -f json           # one JSON per image
anaksor scan.pdf --pages 1-3,7 --device cuda
anaksor --fetch-models                  # download the weights ahead of time
```

## Python

```python
import anaksor

ocr = anaksor.OCR()                       # backend and device picked automatically, see Backends
result = ocr("page.jpg")
print(result["text"])                     # reading order; paragraphs split by blank lines

for line in result["lines"]:              # text, box, quads, parts, rec_score, det_score, block
    print(line["rec_score"], line["text"])

pages = ocr.read("scan.pdf", keep_images=True)        # one result per page
open("scan.pdf", "wb").write(anaksor.export.to_pdf(pages))
open("scan.docx", "wb").write(anaksor.export.to_docx(pages))
```

`ocr(image)` takes a path, bytes, a PIL image or an RGB numpy array. Useful options:

| Option | Default | Effect |
|---|---|---|
| `pad_y`, `pad_x` | 0.16, 0.10 | margin around each line before reading, as a fraction of its height |
| `min_rec_score` | 0.5 | drop lines read with less confidence |
| `unclip_ratio` | 1.5 | how much detected boxes are grown (bigger joins more) |
| `scales` | `(1.0,)` | extra detection scales, e.g. `(1.0, 1.6)` for small text |

The detector and recogniser can be used on their own: `anaksor.Detector().detect(img)` and
`anaksor.Recognizer().recognize([crop, ...])`.

## Accuracy and limitations

| Part | Evaluated on | Result |
|---|---|---|
| Detection v3 | KhmerST validation photos | precision 0.75, recall 0.79 |
| Detection v3 | HierText validation: English on photos | precision 0.76, recall 0.69 |
| Detection v3 | synthetic pages | precision 0.998, recall 0.998 |
| Recognition v4 | 3,878 real validation lines: Khmer, Latin and mixed | 86.7% exactly right, 1.38% character error |
| Recognition v4 | the 2,497 Khmer-only lines among them | 90.1% exactly right, 0.73% character error |

KhmerST labels only some of the text in each photo; for detection, unlabelled text found by
another detector counts as "don't care", which flatters precision a little.

- Printed Khmer, documents, receipts and signs read best.
- English and other Latin text on photos is weaker: the detector can miss it on signs, and the
  recogniser has seen little real English.
- Handwriting and decorative lettering are weak. Check each line's `rec_score`, or use
  `--highlight-low` for Word output.

Training data and its licences are listed in the model card on
[Hugging Face](https://huggingface.co/Sokheng/anaksor-ocr).

## Weights

Each model has two files: an ONNX graph (`.onnx`, used by the onnx backend) and PyTorch
weights (`.safetensors`, used by the torch backend). Only the files the chosen backend needs
are fetched, from the first of: an explicit `det_weights=` / `rec_weights=` path,
`$ANAKSOR_WEIGHTS_DIR`, then the cache (`$ANAKSOR_HOME`, default `~/.cache/anaksor`), which
is filled from the Hugging Face repo `Sokheng/anaksor-ocr` and checked against the
SHA-256 in the model spec before it is used; a file whose spec has no SHA-256 is not
downloaded at all. Neither format can run code when loaded. Files come from the Hub commit
of the release the package was built for (rec v4 + det v3, `5c9f76c`), not from `main`,
where the `_latest` files move on with each release; `ANAKSOR_HF_REVISION` picks another. Offline machines: copy
the two files for your backend into `$ANAKSOR_WEIGHTS_DIR` (`anaksor --fetch-models`
downloads them ahead of time).

### Other models

Models trained with OpenOCR-style configs (the format these models were trained with) run
with a spec made from the training config. The tools are in the repository, not the
installed package, so run them from a clone:

```bash
git clone https://github.com/SokhengDin/anaksor-ocr && cd anaksor-ocr
python tools/spec_from_config.py path/to/svtrv2_cppd_khmer.yml --out specs/
```

```python
rec = anaksor.Recognizer("specs/rec-svtrv2-cppd-khmer.yml", weights="best.pth")
ocr = anaksor.OCR(recognizer=rec)
```

For the onnx backend, export the weights (needs `[export]`); the spec already names the
`.onnx` file, so only the printed SHA-256 goes into `weights.onnx_sha256`:

```bash
python tools/export_onnx.py --rec best.pth --rec-spec specs/rec-svtrv2-cppd-khmer.yml --out onnx/
```

Supported: detection RepViT + DBNet; recognition SVTRv2 (any size) with RCTC + SMTR heads
(`GTCDecoder`, also with the training-only count head), RCTC alone, or CPPD. The `.pth`
checkpoints load as they are (no code runs: `weights_only`); `tools/convert_weights.py`
turns them into `.safetensors`. A CPPD head has no per-column output, so lines wider than
its input are read in overlapping windows joined where their texts overlap, instead of by
CTC character positions.

## Security

Image inputs are decoded only as JPEG, PNG, WEBP, BMP or TIFF, weights are loaded without
running code, and dependency floors exclude versions with known vulnerabilities (checked with
`pip-audit` in CI). See [SECURITY.md](SECURITY.md).

## Development

```bash
uv venv && uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -e ".[all]" pytest ruff pip-audit onnx onnxscript
pytest                                    # no weights or network needed
ANAKSOR_TEST_WEIGHTS=/path/to/weights pytest -m weights
ruff check src tests tools && ruff format --check src tests tools
```

The website (landing page, demo, documentation) is a Next.js app in `web/`, see
[web/README.md](web/README.md).

Layout of the package:

| Module | Role |
|---|---|
| `ocr.py` | `OCR`: detect, crop, recognise, lay out |
| `detector.py`, `recognizer.py` | the two models |
| `layout.py` | reading order: XY-cut columns, lines, paragraphs |
| `longline.py` | lines wider than the recogniser's input: windows stitched by CTC positions (CPPD: by text overlap) |
| `geometry.py` | box maths and crops |
| `text.py` | Khmer normalisation and the recognition charset |
| `inputs.py` | images (format allowlist) and PDF pages |
| `export/` | searchable PDF and Word |
| `models.py` | model specs, weights download, checksum and safe loading |
| `runtime.py` | where the networks run: PyTorch or ONNX Runtime |
| `onnx_export.py` | ONNX export (fused, dynamic shapes, checked against PyTorch) |
| `nets/` | the networks: RepViT + DBNet, SVTRv2 with RCTC, SMTR or CPPD heads; `fuse.py` folds batch norms |
| `db_boxes.py` | text boxes from the detector's probability map |
| `decoding.py` | charsets, CTC, SMTR and CPPD decoding |

### Releasing

1. CI: move `.github/workflows-pending/` to `.github/workflows/` (see the README there).
2. Weights: `python tools/convert_weights.py best.pth` for each model, then
   `python tools/export_onnx.py --det ... --rec ...`; upload the `.safetensors` and `.onnx`
   files to the Hugging Face repo and put the printed SHA-256s into `src/anaksor/data/*.yml`
   (`weights.sha256`, `weights.onnx_sha256`). Add a model card to the Hugging Face repo:
   training data, its licences, and the evaluation results above.
3. Bump `version` in `pyproject.toml`, update `CHANGELOG.md`, then tag `vX.Y.Z`.
   The release workflow audits the dependencies, builds, and publishes to PyPI through
   trusted publishing.

## Credits and licence

Apache-2.0. The networks are implemented from their papers, with the layer layout and
tensor names of the [OpenOCR](https://github.com/Topdu/OpenOCR) implementations the models
were trained with (see [NOTICE](NOTICE)).

- DBNet: Liao et al., *Real-time Scene Text Detection with Differentiable Binarization*, AAAI 2020
- RepViT: Wang et al., *RepViT: Revisiting Mobile CNN From ViT Perspective*, CVPR 2024
- SVTRv2: Du et al., *SVTRv2: CTC Beats Encoder-Decoder Models in Scene Text Recognition*, ICCV 2025
- SMTR: Du et al., *Out of Length Text Recognition with Sub-String Matching*, AAAI 2025
- CPPD: Du et al., *Context Perception Parallel Decoder for Scene Text Recognition*, TPAMI 2025
