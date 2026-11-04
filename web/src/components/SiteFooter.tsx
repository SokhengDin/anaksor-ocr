import Link from "next/link";

import { type Dict, localePath } from "@/i18n";
import { asset, REPO_URL, WEIGHTS_URL } from "@/lib/config";
import { brand, wordmark, wrap } from "@/lib/ui";
import { Icon } from "./Icon";

const LINK = "inline-flex items-center gap-[.4rem] text-ink no-underline text-[.95rem] hover:text-jade-deep";

export function SiteFooter({ t }: { t: Dict }) {
  return (
    <footer className="border-t border-hairline">
      <div className={`${wrap} pt-9 pb-12 text-ink-soft text-[.9rem]`}>
        <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-4 pb-5 mb-5 border-b border-hairline">
          <Link className={brand} href={localePath(t.lang)}>
            {/* eslint-disable-next-line @next/next/no-img-element -- static export: plain files */}
            <img src={asset("/favicon.svg")} alt="" width={30} height={30} />
            <span className={wordmark}>
              anaksor<span>-ocr</span>
            </span>
          </Link>
          <nav className="flex flex-wrap gap-x-6 gap-y-2" aria-label={t.nav.source}>
            <Link className={LINK} href={localePath(t.lang, "/docs/")}>
              <Icon name="file" />
              {t.nav.docs}
            </Link>
            <a className={LINK} href={REPO_URL}>
              <Icon name="code" />
              {t.nav.source}
            </a>
            <a className={LINK} href={WEIGHTS_URL}>
              <Icon name="download" />
              {t.footer.weights}
            </a>
          </nav>
        </div>
        <p className="mb-[.4rem] max-w-[70ch]">{t.footer.licence}</p>
        <p className="mb-[.4rem] max-w-[70ch]">{t.footer.fonts}</p>
      </div>
    </footer>
  );
}
