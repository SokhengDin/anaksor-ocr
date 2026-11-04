import Link from "next/link";

import { asset, REPO_URL } from "@/lib/config";
import { type Dict, localePath } from "@/i18n";
import { brand, wordmark, wrap } from "@/lib/ui";
import { Icon } from "./Icon";

const LINK =
  "inline-flex items-center gap-[.4rem] text-ink no-underline text-[.95rem] km:text-[1rem] hover:text-jade-deep aria-[current=page]:text-jade-deep aria-[current=page]:font-bold aria-[current=page]:shadow-[inset_0_-2px_0_var(--color-jade)]";
const PAD = "py-[.2rem] max-sm:p-[.35rem]";

export function SiteHeader({ t, page }: { t: Dict; page: "home" | "docs" }) {
  const other = t.lang === "km" ? "en" : "km";
  const here = page === "docs" ? "/docs/" : "/";
  return (
    <header className="sticky top-0 z-5 bg-paper/92 backdrop-blur-[8px] border-b border-hairline">
      <a className="absolute -left-[9999px] focus:left-4 focus:top-4 focus:z-10 focus:bg-ink focus:text-paper focus:px-4 focus:py-2" href="#content">
        {t.nav.skip}
      </a>
      <div className={`${wrap} flex items-center gap-6 py-[.65rem] max-sm:gap-3`}>
        <Link className={brand} href={localePath(t.lang)}>
          {/* eslint-disable-next-line @next/next/no-img-element -- static export: plain files */}
          <img src={asset("/favicon.svg")} alt="" width={30} height={30} />
          <span className={wordmark}>
            anaksor<span>-ocr</span>
          </span>
        </Link>
        <nav className="ml-auto flex items-center gap-5 max-sm:gap-2" aria-label={t.nav.docs}>
          <Link className={`${LINK} ${PAD}`} href={`${localePath(t.lang)}#demo`}>
            <Icon name="scan" />
            <span className="max-sm:hidden">{t.nav.demo}</span>
          </Link>
          <Link className={`${LINK} ${PAD}`} href={localePath(t.lang, "/docs/")} aria-current={page === "docs" ? "page" : undefined}>
            <Icon name="file" />
            <span className="max-sm:hidden">{t.nav.docs}</span>
          </Link>
          <a className={`${LINK} ${PAD}`} href={REPO_URL}>
            <Icon name="code" />
            <span className="max-sm:hidden">{t.nav.source}</span>
          </a>
          <Link
            className={`${LINK} px-3 py-[.1rem] border border-hairline rounded-full hover:border-jade`}
            href={localePath(other, here)}
            hrefLang={other}
            lang={other}
            title={t.nav.otherLangName}
          >
            {t.nav.otherLang}
          </Link>
        </nav>
      </div>
    </header>
  );
}
