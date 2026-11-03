import type { MetadataRoute } from "next";

import { BASE_PATH, SITE_URL } from "@/lib/config";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: `${SITE_URL}${BASE_PATH}/sitemap.xml`,
    host: SITE_URL,
  };
}
