// Browser smoke test of the built site: the demo (sample, upload, text view, downloads, PDF
// streaming, error messages), the English page and both docs pages.
//
//   bun run build:local && bun run e2e           # starts the standalone server + the mock API on free ports
//   BASE=http://localhost:8089 bun run e2e       # or test a running server (Alpha-OCR app.py)
//   BASE=http://localhost:3000 API=http://127.0.0.1:8090 bun run e2e   # dev server + separate API
//
// Needs a browser once: bunx playwright install chromium-headless-shell
import { spawn, type ChildProcess } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const web    = join(dirname(fileURLToPath(import.meta.url)), "..");
const SAMPLE = join(web, "public/sample/khmer-notice.png");

/** A valid PDF of `pages` blank A4 pages: enough for the page stream, no fixture file needed. */
function blankPdf(pages: number): Buffer {
  const kids = Array.from({ length: pages }, (_, i) => `${i + 3} 0 R`).join(" ");
  const objs = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    `<< /Type /Pages /Kids [${kids}] /Count ${pages} >>`,
    ...Array.from({ length: pages }, () => "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>"),
  ];
  let out       = "%PDF-1.4\n";
  const offsets = objs.map((obj, i) => {
    const at = out.length;
    out += `${i + 1} 0 obj\n${obj}\nendobj\n`;
    return at;
  });
  const xref = out.length;
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`;
  out += offsets.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("");
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, "latin1");
}

async function waitFor(url: string, procs: ChildProcess[]) {
  for (let i = 0; i < 150; i++) {
    try {
      if ((await fetch(url)).ok) return;
    } catch {
      // not listening yet
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  procs.forEach((p) => p.kill());
  throw new Error(`nothing answered on ${url}`);
}

/** The standalone Next server on one port, and the mock API in front of it on another (one origin). */
async function startMock(): Promise<{ base: string; procs: ChildProcess[] }> {
  const server = join(web, ".next/standalone/server.js");
  if (!existsSync(server)) {
    console.error("No build in .next/standalone: run `bun run build` first (or set BASE to a running server).");
    process.exit(2);
  }
  const port     = 8090 + Math.floor(Math.random() * 800);
  const sitePort = port + 1000;
  const site = spawn("node", [server], {
    env:   { ...process.env, PORT: String(sitePort), HOSTNAME: "127.0.0.1" },
    stdio: "ignore",
  });
  const api = spawn(process.execPath, [join(web, "scripts/mock-api.mjs")], {
    env:   { ...process.env, PORT: String(port), MOCK_UPSTREAM: `http://127.0.0.1:${sitePort}` },
    stdio: "ignore",
  });
  const procs = [site, api];
  const base  = `http://127.0.0.1:${port}`;
  await waitFor(`http://127.0.0.1:${sitePort}/`, procs);
  await waitFor(`${base}/health`, procs);
  return { base, procs };
}

const mock = process.env.BASE ? null : await startMock();
const BASE = (process.env.BASE ?? mock!.base).replace(/\/+$/, "");
const API  = new URL(process.env.API ?? BASE).origin;      // where the demo should send its requests
console.log(`Testing ${BASE}${mock ? " (mock API + standalone server)" : ""}\n`);

const results: boolean[] = [];
function check(name: string, ok: boolean | undefined, extra = "") {
  results.push(Boolean(ok));
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? `  (${extra})` : ""}`);
}

const browser = await chromium.launch();
try {
  const ctx           = await browser.newContext({ acceptDownloads: true, viewport: { width: 1360, height: 1000 } });
  await ctx.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE });
  const page          = await ctx.newPage();
  const consoleErrors : string[] = [];
  const apiOrigins    = new Set<string>();
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
  page.on("pageerror", (e) => consoleErrors.push(String(e)));
  page.on("request", (r) => {
    const u = new URL(r.url());
    if (/^\/(health|ocr|export)/.test(u.pathname)) apiOrigins.add(u.origin);
  });

  // Khmer landing page with the sample result
  await page.goto(`${BASE}/`);
  await page.waitForSelector(".viewer .line polygon");
  check("html lang is km", (await page.getAttribute("html", "lang")) === "km");
  check("result opens as text, page without numbers",
    (await page.locator(".fulltext").count()) === 1 && (await page.locator(".viewer .num").count()) === 0);
  await page.click('button[aria-pressed]:has-text("បន្ទាត់")');
  check("sample: 11 boxes and 11 rows",
    (await page.locator(".viewer g.line").count()) === 11 && (await page.locator(".lines li").count()) === 11);
  await page.waitForSelector('.status[data-state="ok"]', { timeout: 10000 });
  check("API status: ready", (await page.textContent(".status"))?.includes("រួចរាល់"));
  check("line numbers in Khmer digits", (await page.textContent(".lines li:nth-child(11) .line-num"))?.trim() === "១១");

  await page.hover(".lines li:nth-child(3) .line-row");
  check("hovering row 3 highlights box 3",
    await page.locator(".viewer g.line").nth(2).evaluate((g) => g.classList.contains("active")));
  await page.locator(".viewer g.line").nth(6).locator("polygon").first().hover({ force: true });
  check("hovering box 7 highlights row 7",
    (await page.locator(".lines li:nth-child(7) .line-row").getAttribute("data-active")) === "");

  // the rest of the Khmer page: real pages, no accuracy table, highlighted code
  check("hero: 3 real-page prints", (await page.locator(".hero-shots > li").count()) === 3);
  check("hero: the prints show their detected lines", (await page.locator(".shot-photo polygon").count()) > 50);
  // a print opens in the demo with its recorded result (no API call)
  const receiptLines = (JSON.parse(readFileSync(join(web, "public/showcase/receipt.json"), "utf8")) as { lines: unknown[] }).lines.length;
  await page.click(".shot-receipt a.shot-link");
  await page.waitForFunction((n) => document.querySelectorAll(".lines li").length === n, receiptLines, { timeout: 5000 });
  check(`print opens in the demo: receipt, ${receiptLines} rows`, /\/showcase\/receipt\.jpg\?v=[0-9a-f]{12}$/.test((await page.locator(".viewer img").getAttribute("src")) ?? ""));
  check("Khmer page has no accuracy table", (await page.locator("#h-features ~ * table, .band table").count()) === 0);
  check("code is highlighted", (await page.locator("pre.shiki span[style*=color]").count()) > 5);

  // reading an image, then its text and downloads
  await page.setInputFiles('input[type="file"]', SAMPLE);
  await page.waitForSelector(".sample-note", { state: "detached", timeout: 10000 });
  await page.waitForSelector(".viewer .line polygon", { timeout: 60000 });
  check("uploaded image: result shown", (await page.locator(".lines li").count()) > 0);

  await page.click('button[aria-pressed]:has-text("អត្ថបទ")');
  check("text view shows the page text", (await page.textContent(".fulltext"))?.includes("ព្រះរាជាណាចក្រកម្ពុជា"));
  await page.click('button[aria-pressed]:has-text("បន្ទាត់")');

  const [txt] = await Promise.all([page.waitForEvent("download"), page.click('button:has-text("ទាញយក .txt")')]);
  check(".txt download has the text", readFileSync((await txt.path())!, "utf8").includes("ព្រះរាជាណាចក្រកម្ពុជា"));
  const [docx] = await Promise.all([page.waitForEvent("download", { timeout: 60000 }), page.click('button:has-text("ឯកសារ Word")')]);
  check("Word export downloads", docx.suggestedFilename() === "khmer-notice.docx", docx.suggestedFilename());

  // a PDF streams page by page
  await page.setInputFiles('input[type="file"]', { name: "two-pages.pdf", mimeType: "application/pdf", buffer: blankPdf(2) });
  await page.waitForFunction(() => document.querySelectorAll(".pages button").length === 2, null, { timeout: 60000 });
  await page.waitForSelector('button:has-text("បញ្ឈប់")', { state: "detached", timeout: 60000 });
  check("PDF: two streamed pages", (await page.locator(".pages button").count()) === 2);

  // errors are explained
  await page.setInputFiles('input[type="file"]', { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("hello") });
  check("unsupported file explained", (await page.textContent(".notice.error"))?.includes("សូមជ្រើសរើសរូបភាព"));
  await page.route("**/ocr?**", (r) => r.fulfill({ status: 429, contentType: "application/json", body: '{"detail":"Too many"}' }));
  await page.setInputFiles('input[type="file"]', SAMPLE);
  await page.waitForSelector(".notice.error", { timeout: 10000 });
  check("429 explained", (await page.textContent(".notice.error"))?.includes("សំណើច្រើនពេក"));
  await page.unroute("**/ocr?**");

  // English and the docs
  await page.goto(`${BASE}/en/`);
  await page.waitForSelector(".viewer .line polygon");
  check("English page", (await page.getAttribute("html", "lang")) === "en" && (await page.textContent("#h-demo")) === "Read a page");
  check("English page has the accuracy table", (await page.locator(".band table").count()) === 1);
  for (const [path, h1] of [["/docs/", "ឯកសារណែនាំ"], ["/en/docs/", "Documentation"]] as const) {
    await page.goto(`${BASE}${path}`);
    check(`docs ${path}`, (await page.textContent("h1")) === h1 && (await page.locator(".doc section").count()) > 0);
  }
  check("Khmer in code is set in Battambang",
    await page.locator("pre .km").first().evaluate((el) => getComputedStyle(el).fontFamily.toLowerCase().includes("battambang")));
  await page.locator("#install .copy").first().click();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  check("copy leaves out the $ prompts", copied.includes("pip install anaksor-ocr") && !copied.includes("$ "), JSON.stringify(copied.slice(0, 60)));

  check(`API called on ${API} only`, apiOrigins.size === 1 && apiOrigins.has(API), [...apiOrigins].join(", "));
  const appErrors = consoleErrors.filter((e) => !/status of 429/.test(e));
  check("no console errors", appErrors.length === 0, appErrors.slice(0, 3).join(" | "));
} finally {
  await browser.close();
  mock?.procs.forEach((p) => p.kill());
}

const failed = results.filter((ok) => !ok).length;
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
