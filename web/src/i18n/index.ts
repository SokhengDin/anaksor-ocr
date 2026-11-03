import { en } from "./en";
import { km } from "./km";
import type { Dict, Lang } from "./types";

export type { Dict, Lang };
export { kh } from "./km";

export const dicts: Record<Lang, Dict> = { km, en };

/** Path of a page in a language: Khmer at the root, English under /en. */
export function localePath(lang: Lang, path = "/"): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return lang === "km" ? p : `/en${p === "/" ? "/" : p}`;
}
