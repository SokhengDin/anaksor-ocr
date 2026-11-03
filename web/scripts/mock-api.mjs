// A stand-in for the OCR API, for working on the demo without the real server:
//
//   bun run mock                         # http://127.0.0.1:8090
//   bun run dev:mock                     # the dev server, calling the mock
//
// It answers every upload with the recorded sample result (a real response of the API for
// public/sample/khmer-notice.png), streams PDFs as two pages with a pause between them, and
// returns a placeholder file for exports. MOCK_FAIL=network|413|429|503 makes /ocr fail that way.
// MOCK_SITE=out also serves the built site on the same origin, as ocr.sokhengdin.dev does:
//   bun run build && bun run preview     # then open http://127.0.0.1:8090
// Runs on Bun (node:http is all it uses).
import { createServer, request } from "node:http";
import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const sample = JSON.parse(readFileSync(join(here, "../public/sample/khmer-notice.json"), "utf8"));
const image = readFileSync(join(here, "../public/sample/khmer-notice.png")).toString("base64");
const port = Number(process.env.PORT ?? 8090);
const fail = process.env.MOCK_FAIL ?? "";
const site = process.env.MOCK_SITE ? resolve(process.env.MOCK_SITE) : null;
const upstream = process.env.MOCK_UPSTREAM ?? null;
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8" };

function serveSite(req, res, pathname) {
  let file = normalize(join(site, decodeURIComponent(pathname)));
  if (!file.startsWith(site)) return json(res, 404, { detail: "Not Found" });
  if (existsSync(file) && statSync(file).isDirectory()) file = join(file, "index.html");
  if (!existsSync(file)) file = join(site, "404.html");
  res.writeHead(file.endsWith("404.html") ? 404 : 200, { "Content-Type": TYPES[extname(file)] ?? "application/octet-stream" });
  res.end(req.method === "HEAD" ? undefined : readFileSync(file)); // Next probes links with HEAD
}

// Page requests go to a running Next server (the standalone build), so site and API share one origin.
function proxySite(req, res) {
  const out = request(new URL(req.url ?? "/", upstream), { method: req.method, headers: req.headers }, (up) => {
    res.writeHead(up.statusCode ?? 502, up.headers);
    up.pipe(res);
  });
  out.on("error", () => json(res, 502, { detail: "site upstream unreachable" }));
  req.pipe(out);
}

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "*",
};

function json(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json", ...cors });
  res.end(JSON.stringify(body));
}

async function drain(req) {
  // read the upload so the client sees a normal exchange
  req.resume();
  await new Promise((resolve) => req.on("end", resolve));
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", `http://${req.headers.host}`);
  if (req.method === "OPTIONS") {
    res.writeHead(204, cors);
    return res.end();
  }
  if (url.pathname === "/health") return json(res, 200, { status: "ok", device: "mock", models_loaded: true });
  if ((req.method === "GET" || req.method === "HEAD") && upstream) return proxySite(req, res);
  if ((req.method === "GET" || req.method === "HEAD") && site) return serveSite(req, res, url.pathname);
  if (req.method !== "POST") return json(res, 404, { detail: "Not Found" });
  await drain(req);

  if (url.pathname === "/ocr") {
    if (fail === "network") return req.socket.destroy();
    if (fail) return json(res, Number(fail), { detail: `mock failure ${fail}` });
    await sleep(600);
    // the real API sends the page back as JPEG; the PNG sample is fine for an <img> data: URL too
    return json(res, 200, { ...sample, image });
  }
  if (url.pathname === "/ocr/pdf") {
    res.writeHead(200, { "Content-Type": "application/x-ndjson", "Cache-Control": "no-store", ...cors });
    res.write(JSON.stringify({ type: "meta", pages: 2, first: 1, last: 2, total_pages: 2, truncated: false }) + "\n");
    for (const page of [1, 2]) {
      await sleep(900);
      res.write(JSON.stringify({ type: "page", page, ...sample, image }) + "\n");
    }
    res.end(JSON.stringify({ type: "done", pages: 2, time: 1.8 }) + "\n");
    return;
  }
  if (url.pathname === "/export") {
    const docx = url.searchParams.get("format") === "docx";
    res.writeHead(200, {
      "Content-Type": docx ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document" : "application/pdf",
      ...cors,
    });
    return res.end("mock export");
  }
  json(res, 404, { detail: "Not Found" });
}).listen(port, "127.0.0.1", () => console.log(`mock OCR API on http://127.0.0.1:${port}`));
