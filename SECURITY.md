# Security

## Reporting

Report vulnerabilities privately through GitHub's
[security advisories](https://github.com/SokhengDin/anaksor-ocr/security/advisories/new),
not in public issues.

## What the package does to stay safe

- **Weights never run code.** Release weights are `.safetensors`. Other checkpoints are read
  with `torch.load(weights_only=True)`; anything that needs a full unpickle is refused.
- **Downloads are checked.** Weights come over HTTPS only, are written atomically, and are
  compared with the SHA-256 in the model spec when one is set.
- **Untrusted images hit few decoders.** `anaksor.load_image` (used for every path and byte
  input) opens only JPEG, PNG, WEBP, BMP and TIFF, so Pillow's rarer decoders (PSD, MSP,
  MIC, FITS...) never see your users' files. Pillow's decompression-bomb limit stays on.
- **Configs are data.** Model specs are read with `yaml.safe_load`.
- **Dependencies.** Version floors in `pyproject.toml` are set so that even the oldest
  allowed versions have no known vulnerability (Pillow 13.0.0 for the 2026 decoder fixes,
  torch 2.13 for the 2025-2026 torch advisories). CI audits both the locked set and the
  lowest allowed versions with `pip-audit` (PyPI and OSV databases) and fails on any known
  vulnerability; a weekly scheduled run catches advisories published after a release.

## If you serve anaksor to the public

- Limit upload sizes and the number of PDF pages read per request.
- PDFs are rendered by PDFium (pypdfium2); keep it updated.
- Run inference in a process without access to secrets.
