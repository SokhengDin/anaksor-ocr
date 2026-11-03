import Link from "next/link";

import { type Dict, localePath } from "@/i18n";
import { asset, REPO_URL, WEIGHTS_URL } from "@/lib/config";
import { Icon } from "./Icon";

export function SiteFooter({ t }: { t: Dict }) {
  return (
    <footer>
      <div className="wrap foot">
        <div className="foot-top">
          <Link className="brand" href={localePath(t.lang)}>
            {/* eslint-disable-next-line @next/next/no-img-element -- static export: plain files */}
            <img src={asset("/favicon.svg")} alt="" width={30} height={30} />
            <span className="wordmark">
              anaksor<span>-ocr</span>
            </span>
          </Link>
          <nav className="foot-links" aria-label={t.nav.source}>
            <Link href={localePath(t.lang, "/docs/")}>
              <Icon name="file" />
              {t.nav.docs}
            </Link>
            <a href={REPO_URL}>
              <Icon name="code" />
              {t.nav.source}
            </a>
            <a href={WEIGHTS_URL}>
              <Icon name="download" />
              {t.footer.weights}
            </a>
          </nav>
        </div>
        <p>{t.footer.licence}</p>
        <p>{t.footer.fonts}</p>
      </div>
    </footer>
  );
}
