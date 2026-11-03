/** Types of the OCR API (the Alpha-OCR deployment: /health, /ocr, /ocr/pdf, /export). */

export type Point = [number, number];
export type Quad = [Point, Point, Point, Point];

/** One text line in reading order. */
export interface OcrLine {
  text: string;
  /** Rectangle around the whole line. */
  box: Quad;
  /** The detected boxes the line was built from (a receipt line: label and price). */
  quads: Quad[];
  /** Text of each quad. */
  parts: string[];
  rec_score: number;
  det_score: number;
  /** Index of the paragraph (block) the line belongs to. */
  block: number;
}

/** A paragraph: consecutive lines that belong together. */
export interface OcrBlock {
  text: string;
  box: Quad;
  boxes: Quad[];
  lines: number[];
  rec_score: number;
  det_score: number;
}

/** Result for one image or one PDF page. Coordinates are pixels of the (rendered) page. */
export interface OcrPage {
  text: string;
  results: OcrBlock[];
  lines: OcrLine[];
  width: number;
  height: number;
  time: number;
  timing: Record<string, number>;
  /** Base64 JPEG of the page as it was read (images: full size; PDF pages: a preview). */
  image?: string;
  /** PDF page number, 1-based. */
  page?: number;
}

export type PdfEvent =
  | { type: "meta"; pages: number; first: number; last: number; total_pages: number; truncated: boolean }
  | ({ type: "page"; page: number } & OcrPage)
  | { type: "error"; page: number; detail: string; fatal?: boolean }
  | { type: "done"; pages: number; time: number };

export interface Health {
  status: "ok" | "loading" | "error";
  device?: string;
  models_loaded?: boolean;
  models?: Record<string, string | number>;
  tables?: boolean;
  error?: string | null;
}

export type ExportFormat = "pdf" | "docx";
