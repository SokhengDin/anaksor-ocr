import { existsSync } from "node:fs";
import { join } from "node:path";

import { type Dict, kh } from "@/i18n";
import type { ShowcaseId } from "@/i18n/types";
import { asset } from "@/lib/config";
import { Icon } from "./Icon";

const IDS: ShowcaseId[]  = ["document", "receipt", "sign"];
const EXTENSIONS         = [".jpg", ".jpeg", ".png", ".webp"];
const DIR                = join(process.cwd(), "public", "showcase");

/** The photo for a slot, looked up at build time: public/showcase/<id>.<ext>, or null. */
function photo(id: ShowcaseId): string | null {
  const ext = EXTENSIONS.find((e) => existsSync(join(DIR, `${id}${e}`)));
  return ext ? asset(`/showcase/${id}${ext}`) : null;
}

/**
 * The hero's pile of real pages the models were tested on, numbered on from the name's "1"
 * like detected lines. A slot without its photo yet shows a placeholder print.
 */
export function HeroShots({ t }: { t: Dict }) {
  const dev = process.env.NODE_ENV !== "production";
  return (
    <ul className="hero-shots" aria-label={t.showcase.title}>
      {IDS.map((id, i) => {
        const src  = photo(id);
        const item = t.showcase.items[id];
        const n    = t.lang === "km" ? kh(i + 2) : String(i + 2);
        return (
          <li key={id} className={`shot shot-${id}`} tabIndex={0}>
            <figure>
              {src ? (
                // eslint-disable-next-line @next/next/no-img-element -- static export: plain files
                <img src={src} alt={item.text} decoding="async" />
              ) : (
                <div className="shot-placeholder">
                  <Icon name="image" />
                  <span>{t.showcase.placeholder}</span>
                  {dev ? <code>public/showcase/{id}.jpg</code> : null}
                </div>
              )}
              <figcaption>{item.title}</figcaption>
            </figure>
            <span className="marker" aria-hidden="true">
              {n}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
