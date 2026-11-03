import type { DocSection } from "@/components/Docs";
import type { Dict } from "@/i18n";
import * as en from "./docs-en";
import * as km from "./docs-km";

export function docsContent(t: Dict): { title: string; intro: string; sections: DocSection[] } {
  return t.lang === "km" ? km : en;
}
