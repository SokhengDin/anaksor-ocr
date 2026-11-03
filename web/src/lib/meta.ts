import type { Metadata } from "next";

import { type Dict, localePath } from "@/i18n";
import { asset, SITE_URL } from "./config";

/** Title, description, canonical and hreflang links for a page in one language. */
export function pageMetadata(t: Dict, page: "home" | "docs"): Metadata {
  const path = page === "docs" ? "/docs/" : "/";
  const title = page === "docs" ? t.meta.docsTitle : t.meta.title;
  const description = page === "docs" ? t.meta.docsDescription : t.meta.description;
  return {
    metadataBase: new URL(`${SITE_URL}/`),
    title,
    description,
    icons: { icon: asset("/favicon.svg") },
    alternates: {
      canonical: `.${localePath(t.lang, path)}`,
      languages: { km: `.${localePath("km", path)}`, en: `.${localePath("en", path)}`, "x-default": `.${localePath("km", path)}` },
    },
    openGraph: { title, description, type: "website", locale: t.lang === "km" ? "km_KH" : "en_US" },
  };
}
