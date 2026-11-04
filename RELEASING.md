# Releasing

1. New weights only: `python tools/convert_weights.py best.pth` for each model, then
   `python tools/export_onnx.py --det ... --rec ...`, upload the `.safetensors` and `.onnx`
   files to the Hugging Face repo and put the printed SHA-256s into `src/anaksor/data/*.yml`
   (`weights.sha256`, `weights.onnx_sha256`). Update the model card on the Hugging Face repo:
   training data, its licences, and the evaluation results in the README.
2. Bump the version (`uv version --bump patch`), update `CHANGELOG.md`, commit and push.
3. Tag and push: `git tag -a vX.Y.Z -m "anaksor-ocr X.Y.Z" && git push origin vX.Y.Z`.
   The release workflow checks the tag against the version, audits the dependencies, builds,
   then waits for approval of the `pypi` environment before publishing through trusted
   publishing.
