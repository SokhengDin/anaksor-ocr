# anaksor-ocr website

The landing page with the live demo, and the documentation, in Khmer (at `/`) and English
(at `/en`). Next.js with TypeScript, exported as a static site. It runs at
**[ocr.sokhengdin.dev](https://ocr.sokhengdin.dev)**; its demo reads files with the OCR API at
`ocr-api.sokhengdin.dev`, which answers this site only.

Everything runs on [Bun](https://bun.sh) (1.3 or newer); Node.js is not needed.

```bash
cd web
bun install
bun run mock            # terminal 1: stand-in API on http://127.0.0.1:8090
bun run dev:mock        # terminal 2: dev server on http://localhost:3000, calling the mock
```

The mock answers every upload with a recorded result of the real API, streams any PDF as
two pages and returns a placeholder for exports. `MOCK_FAIL=429 bun run mock` (or
`network`, `413`, `503`) shows how errors are explained.

## Testing

```bash
bun run lint && bun run typecheck
bun run build:local                             # out/, calling the API on its own origin (the mock)
bun run preview                                 # out/ + the mock on one origin: http://127.0.0.1:8090
bunx playwright install chromium-headless-shell # once: the browser for the smoke test
bun run e2e                                     # 24 browser checks against out/ + the mock
```

`bun run build` makes the site for production, calling `https://ocr-api.sokhengdin.dev`;
that API only answers pages served from `https://ocr.sokhengdin.dev`, so test with
`build:local` and the mock, or with a local API (below).

`bun run e2e` starts its own mock with `out/` on a free port. To test something already
running, give its address:

| What is running | Command |
|---|---|
| the dev server and the mock (`bun run mock`, `bun run dev:mock`) | `BASE=http://localhost:3000 API=http://127.0.0.1:8090 bun run e2e` |
| `out/` built for a local API, with that API running (see below) | `BASE=http://127.0.0.1:8090 API=http://localhost:8089 bun run e2e` |

### With the real OCR server

The OCR server is Alpha-OCR's `app.py` (it needs its model weights in `weights/`). It only
answers the origins in its `ALLOWED_ORIGINS`, so let it answer the local site:

```bash
# in Alpha-OCR
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:8090 uv run uvicorn app:app --port 8089

# here: the dev server, with hot reload
NEXT_PUBLIC_API_URL=http://localhost:8089 bun run dev

# or the built site (served by `bun run preview` on :8090), and the smoke test against it
NEXT_PUBLIC_API_URL=http://localhost:8089 bun run build && bun run preview
BASE=http://127.0.0.1:8090 API=http://localhost:8089 bun run e2e
```

## Real pages on the home page

The hero shows a pile of three real pages the models were tested on: a letter (portrait),
a receipt (tall) and a shop sign (landscape), numbered ២ ៣ ៤ on from the name's ១. Put
the photos in `public/showcase/` as `document.jpg`, `receipt.jpg` and `sign.jpg` (`.png`,
`.webp` work too) and rebuild; a print without its photo shows a placeholder. Titles and alt
texts are `showcase` in `src/i18n/km.ts` and `en.ts`.

## Code blocks

Code is highlighted at build time with [Shiki](https://shiki.style), in the site's own
colours (`src/lib/highlight.ts`), so pages ship no highlighter. Write a block as

```tsx
<CodeBlock lang="bash" {...cb} code={dedent`
  # a comment, in Khmer or English
  $ anaksor letter.jpg
`} />
```

`lang` is `python`, `bash` or `json`. In `bash`, lines starting with `$ ` are commands: the
prompt is shown but not copied. Khmer in code is set in Battambang.

## Settings (build time)

| Variable | Default | |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://ocr-api.sokhengdin.dev` | the OCR API the demo calls; empty: the site's own origin |
| `NEXT_PUBLIC_BASE_PATH` | empty | a sub-path, only if the site isn't served at the root |
| `NEXT_PUBLIC_SITE_URL` | `https://ocr.sokhengdin.dev` | canonical and hreflang links |

The demo uses `GET /health`, `POST /ocr?return_image=true`, `POST /ocr/pdf?preview_px=1400`
(NDJSON stream) and `POST /export?format=pdf|docx`; the types are in `src/lib/types.ts`.

## Deploying

A push to `main` deploys the site: the `web` workflow checks it, then the server builds that commit as the
`anaksor-web` Docker image and swaps the container behind ocr.sokhengdin.dev. Setup, secrets and what keeps it
safe: [`deploy/README.md`](deploy/README.md). To run the production image on your machine:
`docker compose up -d --build` here, then http://127.0.0.1:8088.
The demo calls the OCR API at `https://ocr-api.sokhengdin.dev` (Alpha-OCR's `app.py`), which answers only the
origins in its `ALLOWED_ORIGINS`. A site on another address needs both: `NEXT_PUBLIC_API_URL` here, and its
origin in the API's `ALLOWED_ORIGINS`.

## Where things are

| Path | |
|---|---|
| `src/app/(km)/`, `src/app/(en)/en/` | the pages: Khmer at the root, English under `/en` (each with its own `<html lang>`) |
| `src/i18n/` | interface texts, typed: a text missing in one language is a type error |
| `src/content/docs-km.tsx`, `docs-en.tsx` | the documentation |
| `src/components/Demo.tsx`, `PageViewer.tsx` | the demo: upload, the page with numbered line boxes, text, exports |
| `src/lib/api.ts`, `types.ts` | the API client and its types |
| `src/components/CodeBlock.tsx`, `src/lib/highlight.ts` | code blocks: Shiki at build time, the copy button |
| `src/components/HeroShots.tsx`, `public/showcase/` | the pile of real pages in the hero |
| `Dockerfile`, `docker-compose.yml` | the `anaksor-web` image (Bun build, unprivileged nginx) and its container |
| `deploy/` | the server side of the deploy: gate, installer, the container's nginx config |
| `e2e/smoke.ts`, `scripts/mock-api.mjs` | the browser smoke test and the stand-in API |
| `public/sample/` | the sample page and the API's real result for it, shown before a visitor reads their own file |
| `src/fonts/` | Battambang (OFL) and Khmer OS Muol Light (LGPL), see `src/fonts/README.md` |
