/** The real pages shown on the home page; each one is public/showcase/<id>.jpg (or .png, .webp). */
export type ShowcaseId = "document" | "receipt" | "sign";

export type Lang = "km" | "en";

/** Every piece of interface text, in one language. Missing a key in either language is a type error. */
export interface Dict {
  lang: Lang;
  htmlLang: string;
  meta: { title: string; description: string; docsTitle: string; docsDescription: string };
  nav: { demo: string; docs: string; source: string; otherLang: string; otherLangName: string; skip: string };
  hero: { reading: string; lead: string; install: string; readDocs: string };
  demo: {
    title: string;
    intro: string;
    sample: string;
    drop: string;
    choose: string;
    paste: string;
    limits: string;
    reading: string;
    readingPage: (page: number, total: number) => string;
    pageLabel: (page: number) => string;
    pagesOf: (done: number, total: number) => string;
    truncated: (shown: number, total: number) => string;
    pageFailed: (page: number) => string;
    readAnother: string;
    cancel: string;
    status: { checking: string; ok: string; loading: string; offline: string };
    text: string;
    lines: string;
    linesHint: string;
    check: string;
    confidence: string;
    copy: string;
    copied: string;
    download: string;
    exportDocx: string;
    exportPdf: string;
    exporting: string;
    seconds: (s: number) => string;
    linesCount: (n: number) => string;
    pageImage: string;
    errors: {
      network: string;
      too_large: string;
      rate_limited: string;
      unavailable: string;
      rejected: (detail: string) => string;
      server: string;
      unsupported: string;
      fileTooBig: (mb: number) => string;
      exportFailed: (detail: string) => string;
    };
  };
  features: { title: string; items: { term: string; text: string }[] };
  /** The pile of real pages in the hero: a title on each print, `text` is the photo's alt text. */
  showcase: {
    title: string;
    /** Shown on a print until its photo is added (public/showcase/). */
    placeholder: string;
    /** Label of a print's link: it opens the print and its result in the demo. */
    open: string;
    /** Under a print's title: how many lines the models read on it. */
    lines: (n: number) => string;
    credit: string;
    creditLink: string;
    items: Record<ShowcaseId, { title: string; text: string }>;
  };
  /** null: the page has no accuracy table (the Khmer page leaves it to the docs). */
  accuracy: { title: string; part: string; set: string; result: string; rows: [string, string, string][]; note: string } | null;
  quickstart: { title: string; text: string; docsLink: string };
  footer: { licence: string; fonts: string; weights: string };
  docs: { onThisPage: string; backHome: string };
  copyCode: string;
  copiedCode: string;
}
