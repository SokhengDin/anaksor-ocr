# Workflows

- `ci.yml`: on pushes to `master` and on pull requests (weekly as well), Python tests (3.11 to 3.13, CPU torch),
  ruff, lock check, pip-audit, wheel build and a clean install of it; the website's lint, typecheck, build and
  browser smoke test; the osv-scanner scan of `uv.lock` and `web/bun.lock` (CVSS >= 5 blocks). On a push to
  `master`, the deploy to the server behind ocr.sokhengdin.dev (`deploy/README.md`: the `production`
  environment and its secrets).
- `release.yml`: on a `vX.Y.Z` tag, audit, build, and publish to PyPI with trusted publishing.
