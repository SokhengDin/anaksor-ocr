import type { Metadata } from "next";

import { type Dict, type Lang, localePath } from "@/i18n";
import { asset, BASE_PATH, REPO_URL, SITE_URL } from "./config";

const KEYWORDS: Record<Lang, string[]> = {
  km: [
    "អានអក្សរ",
    "អានអក្សរខ្មែរ",
    "OCR ខ្មែរ",
    "បំលែងរូបភាពទៅជាអក្សរ",
    "ស្កេនឯកសារខ្មែរ",
    "អក្សរខ្មែរពីរូបថត",
    "PDF ខ្មែរ",
    "Khmer OCR",
    "anaksor",
  ],
  en: [
    "Khmer OCR",
    "Khmer text recognition",
    "Cambodian OCR",
    "Khmer image to text",
    "Khmer PDF OCR",
    "Khmer searchable PDF",
    "Khmer document scanner",
    "Python OCR library",
    "anaksor-ocr",
  ],
};

export const SITE_NAME = "anaksor-ocr";
export const OG_IMAGE = { url: asset("/og.jpg"), width: 1200, height: 630, alt: "anaksor-ocr: Khmer OCR for photos, scans and PDFs" };

export function pageMetadata(t: Dict, page: "home" | "docs"): Metadata {
  const path = page === "docs" ? "/docs/" : "/";
  const title = page === "docs" ? t.meta.docsTitle : t.meta.title;
  const description = page === "docs" ? t.meta.docsDescription : t.meta.description;
  const abs = (lang: Lang) => `${SITE_URL}${BASE_PATH}${localePath(lang, path)}`;
  const url = abs(t.lang);
  return {
    metadataBase: new URL(`${SITE_URL}/`),
    title,
    description,
    applicationName: SITE_NAME,
    keywords: KEYWORDS[t.lang],
    authors: [{ name: "Sokheng Din", url: REPO_URL }],
    creator: "Sokheng Din",
    category: "technology",
    icons: { icon: asset("/favicon.svg") },
    alternates: {
      canonical: url,
      languages: { km: abs("km"), en: abs("en"), "x-default": abs("km") },
    },
    openGraph: {
      title,
      description,
      url,
      siteName: SITE_NAME,
      type: "website",
      locale: t.lang === "km" ? "km_KH" : "en_US",
      alternateLocale: t.lang === "km" ? ["en_US"] : ["km_KH"],
      images: [OG_IMAGE],
    },
    twitter: { card: "summary_large_image", title, description, images: [OG_IMAGE.url] },
    robots: { index: true, follow: true, googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 } },
  };
}
