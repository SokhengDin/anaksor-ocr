/** A page with a result recorded from the real models: the demo's sample, or a showcase print. */
export interface RecordedPage {
  /** The result (an OcrPage), as a path under public/. */
  json: string;
  /** The page image, as a path under public/. */
  image: string;
  /** File name for downloads and exports. */
  name: string;
  /** The image's media type, for exports. */
  type: string;
}

/** Fired by a showcase print, heard by the demo: show this recorded page. */
export const SHOW_PAGE_EVENT = "anaksor:show-page";

export function showRecordedPage(page: RecordedPage) {
  window.dispatchEvent(new CustomEvent<RecordedPage>(SHOW_PAGE_EVENT, { detail: page }));
}
