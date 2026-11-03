/** Build-time settings (NEXT_PUBLIC_* are inlined into the static site). */

/**
 * The OCR API the demo calls: ocr-api.sokhengdin.dev, which answers this site only.
 * NEXT_PUBLIC_API_URL overrides it; empty means the site's own origin (the mock, the tests).
 */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "https://ocr-api.sokhengdin.dev").replace(/\/+$/, "");
export const BASE_PATH = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/+$/, ""); // "/" means the root
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://ocr.sokhengdin.dev").replace(/\/+$/, "");
export const REPO_URL    = "https://github.com/SokhengDin/anaksor-ocr";
export const WEIGHTS_URL = "https://huggingface.co/Sokheng/anaksor-ocr";

/** Upload limits of the API (MAX_IMAGE_MB / MAX_PDF_MB / MAX_PDF_PAGES on the server). */
export const MAX_IMAGE_MB = 10;
export const MAX_PDF_MB = 30;
export const MAX_PDF_PAGES = 30;

/** Lines read below this confidence are marked for checking. */
export const LOW_SCORE = 0.8;

/** A file in public/, with the base path (plain <img> and fetch() don't add it). */
export function asset(path: string): string {
  return `${BASE_PATH}${path.startsWith("/") ? path : `/${path}`}`;
}
