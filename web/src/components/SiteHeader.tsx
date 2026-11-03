import Link from "next/link";

import { asset, REPO_URL } from "@/lib/config";
import { type Dict, localePath } from "@/i18n";
import { Icon } from "./Icon";

export function SiteHeader({ t, page }: { t: Dict; page: "home" | "docs" }) {
  const other = t.lang === "km" ? "en" : "km";
  const here = page === "docs" ? "/docs/" : "/";
  return (
    <header className="top">
      <a className="skip" href="#content">
        {t.nav.skip}
      </a>
      <div className="wrap top-inner">
        <Link className="brand" href={localePath(t.lang)}>
          {/* eslint-disable-next-line @next/next/no-img-element -- static export: plain files */}
          <img src={asset("/favicon.svg")} alt="" width={30} height={30} />
          <span className="wordmark">
            anaksor<span>-ocr</span>
          </span>
        </Link>
        <nav aria-label={t.nav.docs}>
          <Link href={`${localePath(t.lang)}#demo`}>
            <Icon name="scan" />
            <span className="lbl">{t.nav.demo}</span>
          </Link>
          <Link href={localePath(t.lang, "/docs/")} aria-current={page === "docs" ? "page" : undefined}>
            <Icon name="file" />
            <span className="lbl">{t.nav.docs}</span>
          </Link>
          <a href={REPO_URL}>
            <Icon name="code" />
            <span className="lbl">{t.nav.source}</span>
          </a>
          <Link className="lang" href={localePath(other, here)} hrefLang={other} lang={other} title={t.nav.otherLangName}>
            {t.nav.otherLang}
          </Link>
        </nav>
      </div>
    </header>
  );
}
