import { type Dict, localePath } from "@/i18n";
import { BASE_PATH, REPO_URL, SITE_URL, WEIGHTS_URL } from "@/lib/config";

export function StructuredData({ t }: { t: Dict }) {
  const url = `${SITE_URL}${BASE_PATH}${localePath(t.lang, "/")}`;
  const data = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "SoftwareApplication",
        name: "anaksor-ocr",
        alternateName: ["អានអក្សរ", "anaksor"],
        description: t.meta.description,
        url,
        applicationCategory: "DeveloperApplication",
        applicationSubCategory: "OCR",
        operatingSystem: "Windows, macOS, Linux",
        softwareRequirements: "Python 3.11+",
        inLanguage: ["km", "en"],
        license: "https://www.apache.org/licenses/LICENSE-2.0",
        image: `${SITE_URL}${BASE_PATH}/og.jpg`,
        downloadUrl: "https://pypi.org/project/anaksor-ocr/",
        installUrl: "https://pypi.org/project/anaksor-ocr/",
        codeRepository: REPO_URL,
        sameAs: [REPO_URL, "https://pypi.org/project/anaksor-ocr/", WEIGHTS_URL],
        offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
        author: { "@type": "Person", name: "Sokheng Din", url: "https://github.com/SokhengDin" },
      },
      {
        "@type": "WebSite",
        name: "anaksor-ocr",
        alternateName: "អានអក្សរ",
        url: `${SITE_URL}${BASE_PATH}/`,
        inLanguage: t.lang,
      },
    ],
  };
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, "\\u003c") }}
    />
  );
}
