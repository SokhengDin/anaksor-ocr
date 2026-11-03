import type { MetadataRoute } from "next";

import { localePath } from "@/i18n";
import { BASE_PATH, SITE_URL } from "@/lib/config";

export const dynamic = "force-static";

const url = (lang: "km" | "en", path: string) => `${SITE_URL}${BASE_PATH}${localePath(lang, path)}`;

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  return (["/", "/docs/"] as const).flatMap((path) =>
    (["km", "en"] as const).map((lang) => ({
      url: url(lang, path),
      lastModified,
      changeFrequency: "monthly" as const,
      priority: path === "/" ? (lang === "km" ? 1 : 0.9) : 0.7,
      alternates: { languages: { km: url("km", path), en: url("en", path) } },
    })),
  );
}
