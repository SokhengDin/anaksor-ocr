import { API_URL } from "./config";
import type { ExportFormat, Health, OcrPage, PdfEvent } from "./types";

/** Why a request failed, in terms the interface can explain. */
export type ApiErrorKind = "network" | "too_large" | "rate_limited" | "unavailable" | "rejected" | "server";

export class ApiError extends Error {
  constructor(
    readonly kind: ApiErrorKind,
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function kindOf(status: number): ApiErrorKind {
  if (status === 413) return "too_large";
  if (status === 429) return "rate_limited";
  if (status === 503) return "unavailable";
  if (status >= 400 && status < 500) return "rejected";
  return "server";
}

async function failure(res: Response): Promise<ApiError> {
  let detail = `${res.status} ${res.statusText}`;
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    // not JSON: keep the status line
  }
  return new ApiError(kindOf(res.status), res.status, detail);
}

async function post(path: string, body: FormData, signal?: AbortSignal): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method: "POST", body, signal });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    // offline, DNS, or the API doesn't allow this site's origin (CORS): the browser hides which
    throw new ApiError("network", 0, e instanceof Error ? e.message : String(e));
  }
  if (!res.ok) throw await failure(res);
  return res;
}

function form(file: Blob, name: string, extra?: Record<string, string>): FormData {
  const f = new FormData();
  f.append("file", file, name);
  for (const [k, v] of Object.entries(extra ?? {})) f.append(k, v);
  return f;
}

export async function getHealth(signal?: AbortSignal): Promise<Health> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/health`, { signal, cache: "no-store" });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError("network", 0, e instanceof Error ? e.message : String(e));
  }
  // 503 while the models load still carries the health JSON
  return (await res.json()) as Health;
}

/** Read one image. */
export async function readImage(file: File, signal?: AbortSignal): Promise<OcrPage> {
  const res = await post("/ocr?return_image=true", form(file, file.name), signal);
  return (await res.json()) as OcrPage;
}

/** Read a PDF; pages arrive one by one as the server finishes them (NDJSON). */
export async function readPdf(file: File, onEvent: (e: PdfEvent) => void, signal?: AbortSignal): Promise<void> {
  const res = await post("/ocr/pdf?preview_px=1400", form(file, file.name), signal);
  if (!res.body) throw new ApiError("server", res.status, "The response has no body.");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    let nl: number;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (line) onEvent(JSON.parse(line) as PdfEvent);
    }
    if (done) break;
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer) as PdfEvent);
}

/** Build a searchable PDF or a Word file from a result: the API re-reads the original file
 * for the page images, so the file goes back with the result. */
export async function exportResult(
  file: Blob,
  fileName: string,
  pages: OcrPage[],
  format: ExportFormat,
  signal?: AbortSignal,
): Promise<Blob> {
  // the page images are not needed (and too large) for the export request
  const slim = pages.map(({ page, width, height, lines, results }) => ({ page, width, height, lines, results }));
  const body = form(file, fileName, { results: JSON.stringify(slim) });
  const res = await post(`/export?format=${format}`, body, signal);
  return res.blob();
}
