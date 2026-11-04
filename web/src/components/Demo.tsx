"use client";

import { type DragEvent, useCallback, useEffect, useRef, useState } from "react";

import { ApiError, exportResult, getHealth, readImage, readPdf } from "@/lib/api";
import { asset, LOW_SCORE, MAX_IMAGE_MB, MAX_PDF_MB } from "@/lib/config";
import { type RecordedPage, SHOW_PAGE_EVENT } from "@/lib/showcase";
import type { ExportFormat, OcrPage } from "@/lib/types";
import { btn, btnQuiet, btnSmall, btnToggle, hint, meta, notice, noticeError, panelHead, wrap } from "@/lib/ui";
import { dicts, kh, type Lang } from "@/i18n";
import { Icon } from "./Icon";
import { PageViewer } from "./PageViewer";

const SAMPLE: RecordedPage = { json: "/sample/khmer-notice.json", image: "/sample/khmer-notice.png", name: "khmer-notice.png", type: "image/png" };
const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"];

type Health = "checking" | "ok" | "loading" | "offline";
type Slot = { page: number; result?: OcrPage; failed?: boolean };
/** What is on screen: a recorded page (the sample, a showcase print), or a file the visitor gave. */
type Source = { kind: "sample"; sample: RecordedPage } | { kind: "file"; file: File; isPdf: boolean };

function isPdf(f: File) {
  return f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf");
}

async function fetchRecorded(sample: RecordedPage, signal?: AbortSignal): Promise<OcrPage> {
  return (await (await fetch(asset(sample.json), { signal })).json()) as OcrPage;
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
  const [source, setSource] = useState<Source>({ kind: "sample", sample: SAMPLE });
  const [slots, setSlots] = useState<Slot[]>([]);
  const [current, setCurrent] = useState(0);
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [truncated, setTruncated] = useState<string | null>(null);
  const [active, setActive] = useState<number | null>(null);
  const [fresh, setFresh] = useState(false);
  const [view, setView] = useState<"lines" | "text">("text");
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [over, setOver] = useState(false);
  const inflight = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);


  const showRecorded = useCallback((sample: RecordedPage, page: OcrPage, draw: boolean) => {
    inflight.current?.abort();
    setSource({ kind: "sample", sample });
    setSlots([{ page: 1, result: page }]);
    setCurrent(0);
    setTotal(1);
    setError(null);
    setTruncated(null);
    setActive(null);
    setFresh(draw);
  }, []);


  useEffect(() => {
    const ctl = new AbortController();
    fetchRecorded(SAMPLE, ctl.signal)
      .then((page) => showRecorded(SAMPLE, page, false))
      .catch(() => {});
    getHealth(ctl.signal)
      .then((h) => setHealth(h.status === "ok" ? "ok" : h.status === "loading" ? "loading" : "offline"))
      .catch((e) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) setHealth("offline");
      });
    return () => ctl.abort();
  }, [showRecorded]);

  useEffect(() => {
    const onShow = (e: Event) => {
      const sample = (e as CustomEvent<RecordedPage>).detail;
      fetchRecorded(sample)
        .then((page) => showRecorded(sample, page, true))
        .catch(() => {});
    };
    window.addEventListener(SHOW_PAGE_EVENT, onShow);
    return () => window.removeEventListener(SHOW_PAGE_EVENT, onShow);
  }, [showRecorded]);

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
  const imageSrc = page?.image ? `data:image/jpeg;base64,${page.image}` : source.kind === "sample" ? asset(source.sample.image) : "";
  const fullText = page?.text ?? "";
  const baseName = (source.kind === "file" ? source.file.name : source.sample.name).replace(/\.[^.]+$/, "");

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
        source.kind === "file"
          ? source.file
          : new File([await (await fetch(asset(source.sample.image))).blob()], source.sample.name, { type: source.sample.type });
      const blob = await exportResult(file, file.name, source.kind === "file" && source.isPdf ? pages : pages.slice(0, 1), format);
      download(blob, `${baseName}.${format}`);
    } catch (e) {
      setError(d.errors.exportFailed(explain(e)));
    } finally {
      setExporting(null);
    }
  }

  const status = d.status[health];

  // Beside the result once there is one (above the page it read), on its own before that.
  // One row: icon, what to do, the button. The limits sit in small print under the box.
  const dropZone = (
    <div className={page ? "m-0" : "mb-5"}>
      <label
        className="relative flex items-center gap-[.85rem] py-[.7rem] pl-[.7rem] pr-[.75rem] cursor-pointer border-[1.5px] border-dashed border-[color-mix(in_srgb,var(--color-jade)_40%,var(--color-hairline))] rounded-lg bg-paper transition-colors duration-150 hover:border-jade hover:bg-[color-mix(in_srgb,var(--color-jade)_6%,var(--color-paper))] data-[over]:border-jade data-[over]:bg-[color-mix(in_srgb,var(--color-jade)_6%,var(--color-paper))] focus-within:outline-2 focus-within:outline-jade focus-within:outline-offset-3 max-xs:flex-wrap"
        data-over={over ? "" : undefined}
        onDragEnter={() => setOver(true)}
        onDragLeave={() => setOver(false)}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDrop={onDrop}
      >
        <span
          className="grid place-items-center flex-none size-10 rounded-lg bg-[color-mix(in_srgb,var(--color-jade)_12%,var(--color-paper))] text-jade-deep [&_svg]:size-5"
          aria-hidden="true"
        >
          <Icon name="upload" />
        </span>
        <span className="flex flex-col min-w-0 flex-1 leading-[1.35]">
          <strong className="text-[1rem]">{d.drop}</strong>
          <span className="text-[.85rem] text-ink-soft">{d.paste}</span>
        </span>
        <span
          className="inline-flex flex-none items-center gap-[.45rem] min-h-9 px-[.9rem] py-1 border border-jade-deep rounded-lg bg-jade-deep text-white font-text text-[.9rem]/[1.4] font-bold cursor-pointer hover:border-jade hover:bg-jade max-xs:w-full max-xs:justify-center"
          aria-hidden="true"
        >
          {d.choose}
        </span>
        <input
          ref={input}
          className="absolute size-px opacity-0"
          type="file"
          accept={[...IMAGE_TYPES, "application/pdf", ".pdf"].join(",")}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void read(f);
            e.target.value = "";
          }}
          aria-label={d.choose}
        />
      </label>
      <p className="mt-[.4rem] mx-[.15rem] mb-0 text-[.78rem]/[1.5] text-ink-soft">{d.limits}</p>
    </div>
  );

  return (
    <section id="demo" className={`${wrap} pt-0 pb-16`} aria-labelledby="h-demo" onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 mb-2">
        <h2 id="h-demo" className="m-0">
          {d.title}
        </h2>
        <span
          className="inline-flex items-center gap-2 text-[.9rem] text-ink-soft before:content-[''] before:size-[.6rem] before:rounded-full before:bg-hairline data-[state=ok]:before:bg-jade data-[state=loading]:before:bg-saffron data-[state=offline]:before:bg-danger"
          data-state={health}
          role="status"
        >
          {status}
        </span>
      </div>
      <p className="mb-3 text-[.875rem] text-ink-soft">{d.intro}</p>

      {page ? null : dropZone}

      {error ? (
        <p className={noticeError} role="alert">
          {error}
        </p>
      ) : null}
      {truncated ? <p className={notice}>{truncated}</p> : null}

      {source.kind === "sample" && page ? (
        <p className="mb-3 text-[.925rem] text-ink-soft" data-testid="sample-note">
          {d.sample}
        </p>
      ) : null}

      {busy || slots.length > 1 || total > 1 ? (
        <div className={`${panelHead} mb-2`}>
          {total > 1 || slots.length > 1 ? (
            <ul className="flex flex-wrap gap-[.4rem] mb-3 p-0 list-none" data-testid="pages" aria-label={d.pagesOf(done, total || slots.length)}>
              {slots.map((s, i) => (
                <li key={s.page}>
                  <button
                    type="button"
                    className="min-w-[2.4rem] px-[.6rem] py-[.2rem] border border-hairline rounded-md bg-paper text-ink font-text text-[.9rem]/[1.6] cursor-pointer aria-pressed:border-jade-deep aria-pressed:bg-jade-deep aria-pressed:text-white data-[failed]:border-danger data-[failed]:text-danger"
                    aria-pressed={i === current}
                    data-failed={s.failed ? "" : undefined}
                    onClick={() => setCurrent(i)}
                  >
                    {num(s.page)}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <span />
          )}
          {busy ? (
            <span className={meta} aria-live="polite">
              <span
                className="inline-block size-[.9em] mr-[.45em] align-[-.1em] border-2 border-hairline border-t-jade rounded-full animate-[spin_.8s_linear_infinite] motion-reduce:animate-[spin_2.4s_linear_infinite]"
                aria-hidden="true"
              />
              {source.kind === "file" && source.isPdf && total ? d.readingPage(Math.min(done + 1, total), total) : d.reading}{" "}
              <button type="button" className={btnSmall} onClick={() => inflight.current?.abort()}>
                {d.cancel}
              </button>
            </span>
          ) : null}
        </div>
      ) : null}

      {slot?.failed ? <p className={noticeError}>{d.pageFailed(slot.page)}</p> : null}

      {page ? (
        <div className="grid grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] gap-6 items-start max-lg:grid-cols-[minmax(0,1fr)]">
          <div className="sticky top-[4.5rem] flex flex-col gap-4 min-w-0 max-lg:static">
            {dropZone}
            <div className="p-[clamp(.6rem,2vw,1.25rem)] bg-paper-deep border border-hairline rounded-lg">
              <PageViewer page={page} src={imageSrc} active={active} onActive={setActive} fresh={fresh} numbered={view === "lines"} number={num} label={d.pageImage} />
            </div>
          </div>

          <div className="flex flex-col gap-4 min-w-0">
            <div className={panelHead}>
              <div className="flex flex-wrap gap-2" role="group" aria-label={`${d.lines} / ${d.text}`}>
                <button type="button" className={btnToggle} aria-pressed={view === "lines"} onClick={() => setView("lines")}>
                  {d.lines}
                </button>
                <button type="button" className={btnToggle} aria-pressed={view === "text"} onClick={() => setView("text")}>
                  {d.text}
                </button>
              </div>
              <span className={meta}>
                {d.linesCount(page.lines.length)}, {d.seconds(page.time)}
              </span>
            </div>

            {view === "lines" ? (
              <>
                <ol className="m-0 p-0 list-none border border-hairline rounded-lg bg-paper" data-testid="lines" lang="km">
                  {page.lines.map((line, i) => {
                    const low = line.rec_score < LOW_SCORE;
                    const blockStart = i > 0 && page.lines[i - 1]?.block !== line.block;
                    return (
                      <li key={i} className={`m-0 border-b border-hairline last:border-b-0 ${blockStart ? "border-t-2 border-t-paper-deep" : ""}`}>
                        <div
                          className="group/row grid grid-cols-[2rem_minmax(0,1fr)] gap-3 py-[.35rem] px-[.8rem] cursor-default data-[active]:bg-[color-mix(in_srgb,var(--color-saffron)_14%,var(--color-paper))] focus-visible:[outline-offset:-2px]"
                          data-testid="line-row"
                          tabIndex={0}
                          data-active={active === i ? "" : undefined}
                          onMouseEnter={() => setActive(i)}
                          onMouseLeave={() => setActive(null)}
                          onFocus={() => setActive(i)}
                          onBlur={() => setActive(null)}
                        >
                          <span
                            className="grid place-items-center size-[1.7rem] mt-[.35rem] rounded-full bg-paper-deep font-text text-[.8rem]/none font-bold group-data-[active]/row:bg-saffron"
                            data-testid="line-num"
                            aria-hidden="true"
                          >
                            {num(i + 1)}
                          </span>
                          <span>
                            <span className="text-[1.1rem]/[1.85] [overflow-wrap:anywhere]">{line.text}</span>
                            <span className="block text-[.8rem]/[1.4] text-ink-soft" lang={t.htmlLang}>
                              {d.confidence} {num(Math.round(line.rec_score * 100))}%
                              {low ? (
                                <>
                                  {", "}
                                  <span className="text-saffron-ink font-bold">{d.check}</span>
                                </>
                              ) : null}
                            </span>
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ol>
                <p className={hint}>{d.linesHint}</p>
              </>
            ) : (
              <pre
                className="max-h-[22rem] overflow-auto m-0 py-[.9rem] px-4 whitespace-pre-wrap bg-sheet border border-hairline rounded-lg font-text text-[1.05rem]/[1.95]"
                data-testid="fulltext"
                lang="km"
                tabIndex={0}
              >
                {fullText}
              </pre>
            )}

            <div className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,11.5rem),1fr))] gap-2 [&>button]:justify-center">
              <button type="button" className={btn} onClick={copyText}>
                <Icon name={copied ? "check" : "copy"} />
                {copied ? d.copied : d.copy}
              </button>
              <button type="button" className={btnQuiet} onClick={() => download(new Blob([pages.map((p) => p.text).join("\n\n")], { type: "text/plain;charset=utf-8" }), `${baseName}.txt`)}>
                <Icon name="download" />
                {d.download}
              </button>
              <button type="button" className={btnQuiet} onClick={() => exportAs("docx")} disabled={busy || exporting !== null}>
                <Icon name="file" />
                {exporting === "docx" ? d.exporting : d.exportDocx}
              </button>
              <button type="button" className={btnQuiet} onClick={() => exportAs("pdf")} disabled={busy || exporting !== null}>
                <Icon name="file" />
                {exporting === "pdf" ? d.exporting : d.exportPdf}
              </button>
            </div>
            <p className={hint}>{d.exportPdfHint}</p>
            {source.kind === "file" && !busy ? (
              <p className={hint}>
                <button type="button" className={btnQuiet} onClick={() => input.current?.click()}>
                  {d.readAnother}
                </button>
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
