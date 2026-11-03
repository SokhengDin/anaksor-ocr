# CI and release workflows (to activate)

These are the repository's workflows. They live here because the app that pushed this
branch may not write to `.github/workflows/`. To turn them on:

```bash
git mv .github/workflows-pending .github/workflows
git rm .github/workflows/README.md
git commit -m "ci: enable workflows" && git push
```

- `ci.yml`: tests (Python 3.11 to 3.13, CPU torch), ruff, lock check, pip-audit of the
  locked and of the lowest allowed dependencies (weekly as well), wheel build and a clean
  install of it.
- `release.yml`: on a `vX.Y.Z` tag, audit, build, and publish to PyPI with trusted publishing.
- `web.yml`: lint, typecheck, build, browser smoke test and dependency scan of the website
  (`web/`, on Bun); on `main`, the deploy to the server behind ocr.sokhengdin.dev
  (`web/deploy/README.md`: the `production` environment and its secrets).
