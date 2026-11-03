"use client";

import { type DragEvent, useCallback, useEffect, useRef, useState } from "react";

import { ApiError, exportResult, getHealth, readImage, readPdf } from "@/lib/api";
import { asset, LOW_SCORE, MAX_IMAGE_MB, MAX_PDF_MB } from "@/lib/config";
import type { ExportFormat, OcrPage } from "@/lib/types";
import { dicts, kh, type Lang } from "@/i18n";
import { Icon } from "./Icon";
import { PageViewer } from "./PageViewer";

const SAMPLE = { json: "/sample/khmer-notice.json", image: "/sample/khmer-notice.png", name: "khmer-notice.png" };
const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"];

type Health = "checking" | "ok" | "loading" | "offline";
type Slot = { page: number; result?: OcrPage; failed?: boolean };
/** What is on screen: the sample, or a file the visitor gave. */
type Source = { kind: "sample" } | { kind: "file"; file: File; isPdf: boolean };

function isPdf(f: File) {
  return f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf");
}

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Client component: gets the language code (the dictionary holds functions, which can't
 * be passed from the server) and looks the texts up itself. */
export function Demo({ lang }: { lang: Lang }) {
  const t = dicts[lang];
  const d = t.demo;
  const num = useCallback((n: number) => (t.lang === "km" ? kh(n) : String(n)), [t.lang]);

  const [health, setHealth] = useState<Health>("checking");
  const [source, setSource] = useState<Source>({ kind: "sample" });
  const [slots, setSlots] = useState<Slot[]>([]);
  const [current, setCurrent] = useState(0);
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [truncated, setTruncated] = useState<string | null>(null);
  const [active, setActive] = useState<number | null>(null);
  const [fresh, setFresh] = useState(false);
  const [view, setView] = useState<"lines" | "text">("lines");
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [over, setOver] = useState(false);
  const inflight = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);

  // the sample: a real result recorded from the API, shown until the visitor reads their own file
  useEffect(() => {
    const ctl = new AbortController();
    fetch(asset(SAMPLE.json), { signal: ctl.signal })
      .then((r) => r.json() as Promise<OcrPage>)
      .then((page) => {
        setSlots([{ page: 1, result: page }]);
        setTotal(1);
      })
      .catch(() => {});
    getHealth(ctl.signal)
      .then((h) => setHealth(h.status === "ok" ? "ok" : h.status === "loading" ? "loading" : "offline"))
      .catch((e) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) setHealth("offline");
      });
    return () => ctl.abort();
  }, []);

  const explain = useCallback(
    (e: unknown): string => {
      if (e instanceof ApiError) {
        if (e.kind === "rejected") return d.errors.rejected(e.message);
        return d.errors[e.kind];
      }
      return d.errors.server;
    },
    [d],
  );

  const read = useCallback(
    async (file: File) => {
      setError(null);
      const pdf = isPdf(file);
      if (!pdf && !IMAGE_TYPES.includes(file.type)) return setError(d.errors.unsupported);
      const limit = pdf ? MAX_PDF_MB : MAX_IMAGE_MB;
      if (file.size > limit * 1024 * 1024) return setError(d.errors.fileTooBig(limit));

      inflight.current?.abort();
      const ctl = new AbortController();
      inflight.current = ctl;
      setSource({ kind: "file", file, isPdf: pdf });
      setSlots([]);
      setCurrent(0);
      setTotal(pdf ? 0 : 1);
      setTruncated(null);
      setActive(null);
      setBusy(true);
      try {
        if (!pdf) {
          const page = await readImage(file, ctl.signal);
          setSlots([{ page: 1, result: page }]);
          setFresh(true);
        } else {
          await readPdf(
            file,
            (ev) => {
              if (ev.type === "meta") {
                setTotal(ev.pages);
                if (ev.truncated) setTruncated(d.truncated(ev.pages, ev.total_pages - ev.first + 1));
              } else if (ev.type === "page") {
                setSlots((s) => [...s, { page: ev.page, result: ev }]);
                setFresh(true);
              } else if (ev.type === "error") {
                setSlots((s) => [...s, { page: ev.page, failed: true }]);
                if (ev.fatal) setError(ev.detail);
              }
            },
            ctl.signal,
          );
        }
        setHealth("ok");
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError(explain(e));
        if (e instanceof ApiError && e.kind === "network") setHealth("offline");
      } finally {
        if (inflight.current === ctl) {
          inflight.current = null;
          setBusy(false);
        }
      }
    },
    [d, explain],
  );

  // paste an image anywhere on the page
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const file = Array.from(e.clipboardData?.files ?? []).find((f) => f.type.startsWith("image/") || isPdf(f));
      if (file) {
        e.preventDefault();
        void read(file);
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [read]);

  useEffect(() => () => inflight.current?.abort(), []);

  // the line drawing plays once per new result
  useEffect(() => {
    if (!fresh) return;
    const id = setTimeout(() => setFresh(false), 3000);
    return () => clearTimeout(id);
  }, [fresh]);

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const file = e.dataTransfer.files[0];
    if (file) void read(file);
  };

  const slot = slots[current];
  const page = slot?.result;
  const done = slots.filter((s) => s.result).length;
  const pages = slots.map((s) => s.result).filter((p): p is OcrPage => Boolean(p));
  const imageSrc = page?.image ? `data:image/jpeg;base64,${page.image}` : source.kind === "sample" ? asset(SAMPLE.image) : "";
  const fullText = page?.text ?? "";
  const baseName = source.kind === "file" ? source.file.name.replace(/\.[^.]+$/, "") : "khmer-notice";

  async function copyText() {
    try {
      await navigator.clipboard.writeText(fullText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // clipboard blocked: nothing to undo
    }
  }

  async function exportAs(format: ExportFormat) {
    setExporting(format);
    setError(null);
    try {
      const file =
        source.kind === "file" ? source.file : new File([await (await fetch(asset(SAMPLE.image))).blob()], SAMPLE.name, { type: "image/png" });
      const blob = await exportResult(file, file.name, source.kind === "file" && source.isPdf ? pages : pages.slice(0, 1), format);
      download(blob, `${baseName}.${format}`);
    } catch (e) {
      setError(d.errors.exportFailed(explain(e)));
    } finally {
      setExporting(null);
    }
  }

  const status = d.status[health];

  return (
    <section id="demo" className="wrap demo" aria-labelledby="h-demo" onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
      <div className="demo-head">
        <h2 id="h-demo">{d.title}</h2>
        <span className="status" data-state={health} role="status">
          {status}
        </span>
      </div>
      <p className="hint" style={{ marginBottom: "1rem" }}>
        {d.intro}
      </p>

      <label
        className="drop"
        data-over={over ? "" : undefined}
        onDragEnter={() => setOver(true)}
        onDragLeave={() => setOver(false)}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDrop={onDrop}
      >
        <Icon name="upload" />
        <strong>{d.drop}</strong>
        <span className="btn quiet" aria-hidden="true">
          {d.choose}
        </span>
        <span className="hint">{d.paste}</span>
        <input
          ref={input}
          type="file"
          accept={[...IMAGE_TYPES, "application/pdf", ".pdf"].join(",")}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void read(f);
            e.target.value = "";
          }}
          aria-label={d.choose}
        />
        <p className="limits">{d.limits}</p>
      </label>

      {error ? (
        <p className="notice error" role="alert">
          {error}
        </p>
      ) : null}
      {truncated ? <p className="notice">{truncated}</p> : null}

      {source.kind === "sample" && page ? <p className="sample-note">{d.sample}</p> : null}

      {busy || slots.length > 1 || total > 1 ? (
        <div className="panel-head" style={{ marginBottom: ".5rem" }}>
          {total > 1 || slots.length > 1 ? (
            <ul className="pages" aria-label={d.pagesOf(done, total || slots.length)}>
              {slots.map((s, i) => (
                <li key={s.page}>
                  <button type="button" aria-pressed={i === current} data-failed={s.failed ? "" : undefined} onClick={() => setCurrent(i)}>
                    {num(s.page)}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <span />
          )}
          {busy ? (
            <span className="meta" aria-live="polite">
              {source.kind === "file" && source.isPdf && total ? d.readingPage(Math.min(done + 1, total), total) : d.reading}{" "}
              <button type="button" className="btn quiet" onClick={() => inflight.current?.abort()} style={{ minHeight: "2rem" }}>
                {d.cancel}
              </button>
            </span>
          ) : null}
        </div>
      ) : null}

      {slot?.failed ? <p className="notice error">{d.pageFailed(slot.page)}</p> : null}

      {page ? (
        <div className="reader">
          <div className="mat">
            <PageViewer page={page} src={imageSrc} active={active} onActive={setActive} fresh={fresh} number={num} label={d.pageImage} />
          </div>

          <div className="panel">
            <div className="panel-head">
              <div className="tools" role="group" aria-label={`${d.lines} / ${d.text}`}>
                <button type="button" className="btn quiet" aria-pressed={view === "lines"} onClick={() => setView("lines")}>
                  {d.lines}
                </button>
                <button type="button" className="btn quiet" aria-pressed={view === "text"} onClick={() => setView("text")}>
                  {d.text}
                </button>
              </div>
              <span className="meta">
                {d.linesCount(page.lines.length)}, {d.seconds(page.time)}
              </span>
            </div>

            {view === "lines" ? (
              <>
                <ol className="lines" lang="km">
                  {page.lines.map((line, i) => {
                    const low = line.rec_score < LOW_SCORE;
                    const blockStart = i > 0 && page.lines[i - 1]?.block !== line.block;
                    return (
                      <li key={i} className={blockStart ? "block-start" : undefined}>
                        <div
                          className="line-row"
                          tabIndex={0}
                          data-active={active === i ? "" : undefined}
                          onMouseEnter={() => setActive(i)}
                          onMouseLeave={() => setActive(null)}
                          onFocus={() => setActive(i)}
                          onBlur={() => setActive(null)}
                        >
                          <span className="line-num" aria-hidden="true">
                            {num(i + 1)}
                          </span>
                          <span>
                            <span className="line-text">{line.text}</span>
                            <span className="line-meta" lang={t.htmlLang}>
                              {d.confidence} {num(Math.round(line.rec_score * 100))}%
                              {low ? (
                                <>
                                  {", "}
                                  <span className="check">{d.check}</span>
                                </>
                              ) : null}
                            </span>
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ol>
                <p className="hint">{d.linesHint}</p>
              </>
            ) : (
              <pre className="fulltext" lang="km" tabIndex={0}>
                {fullText}
              </pre>
            )}

            <div className="tools exports">
              <button type="button" className="btn" onClick={copyText}>
                <Icon name={copied ? "check" : "copy"} />
                {copied ? d.copied : d.copy}
              </button>
              <button type="button" className="btn quiet" onClick={() => download(new Blob([pages.map((p) => p.text).join("\n\n")], { type: "text/plain;charset=utf-8" }), `${baseName}.txt`)}>
                <Icon name="download" />
                {d.download}
              </button>
              <button type="button" className="btn quiet" onClick={() => exportAs("docx")} disabled={busy || exporting !== null}>
                <Icon name="file" />
                {exporting === "docx" ? d.exporting : d.exportDocx}
              </button>
              <button type="button" className="btn quiet" onClick={() => exportAs("pdf")} disabled={busy || exporting !== null}>
                <Icon name="file" />
                {exporting === "pdf" ? d.exporting : d.exportPdf}
              </button>
            </div>
            {source.kind === "file" && !busy ? (
              <p className="hint">
                <button type="button" className="btn quiet" onClick={() => input.current?.click()}>
                  {d.readAnother}
                </button>
              </p>
            ) : null}
          </div>
        </div>
      ) : busy ? (
        <p className="hint" aria-live="polite">
          {d.reading}
        </p>
      ) : null}
    </section>
  );
}
