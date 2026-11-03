import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { type Dict, kh } from "@/i18n";
import type { ShowcaseId } from "@/i18n/types";
import { asset, REPO_URL } from "@/lib/config";
import type { RecordedPage } from "@/lib/showcase";
import type { OcrPage, Quad } from "@/lib/types";
import { Icon } from "./Icon";
import { ShotLink } from "./ShotLink";

const IDS: ShowcaseId[]  = ["document", "receipt", "sign"];
const EXTENSIONS         = [".jpg", ".jpeg", ".png", ".webp"];
const TYPES: Record<string, string> = { ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp" };
const DIR                = join(process.cwd(), "public", "showcase");

/** The boxes start after the name's own box and markers (globals.css), and all finish within this time. */
const DRAW_START = 1.7;
const DRAW_SPAN  = 1.6;

interface Shot {
  src: string;
  /** Its recorded result (scripts/showcase-results.py), for the boxes and the demo. */
  page: RecordedPage | null;
  width: number;
  height: number;
  /** The detected boxes, in reading order (a line can have several). */
  quads: Quad[];
  /** Lines read. */
  lines: number;
}

/** Looked up at build time: public/showcase/<id>.<ext>, and <id>.json when it has been read. */
function versioned(file: string, bytes: Buffer): string {
  return `/showcase/${file}?v=${createHash("sha256").update(bytes).digest("hex").slice(0, 12)}`;
}

function shot(id: ShowcaseId): Shot | null {
  const ext = EXTENSIONS.find((e) => existsSync(join(DIR, `${id}${e}`)));
  if (!ext) return null;
  const image = versioned(`${id}${ext}`, readFileSync(join(DIR, `${id}${ext}`)));
  const src = asset(image);
  const jsonPath = join(DIR, `${id}.json`);
  if (!existsSync(jsonPath)) return { src, page: null, width: 0, height: 0, quads: [], lines: 0 };
  const raw = readFileSync(jsonPath);
  const result = JSON.parse(raw.toString("utf8")) as OcrPage;
  return {
    src,
    page:   { json: versioned(`${id}.json`, raw), image, name: `${id}${ext}`, type: TYPES[ext] ?? "image/jpeg" },
    width:  result.width,
    height: result.height,
    quads:  result.lines.flatMap((l) => l.quads),
    lines:  result.lines.length,
  };
}

const points = (q: Quad) => q.map(([x, y]) => `${x},${y}`).join(" ");

/**
 * The hero's pile of real pages the models were tested on, numbered on from the name's "1"
 * like detected lines. Each print draws the lines the models found on it, and opens in the demo
 * with its result. A slot without its photo yet shows a placeholder print.
 */
export function HeroShots({ t }: { t: Dict }) {
  const dev = process.env.NODE_ENV !== "production";
  return (
    <div className="hero-side">
    <ul className="hero-shots" aria-label={t.showcase.title}>
      {IDS.map((id, i) => {
        const s    = shot(id);
        const item = t.showcase.items[id];
        const n    = t.lang === "km" ? kh(i + 2) : String(i + 2);
        return (
          <li key={id} className={`shot shot-${id}`}>
            <ShotLink page={s?.page ?? null} label={`${item.title}: ${t.showcase.open}`}>
              <figure>
                {s ? (
                  <div className="shot-photo">
                    {/* eslint-disable-next-line @next/next/no-img-element -- plain files from public/ */}
                    <img src={s.src} alt={item.text} decoding="async" />
                    {s.quads.length ? (
                      // the same crop as the photo's object-fit: cover
                      <svg viewBox={`0 0 ${s.width} ${s.height}`} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
                        {s.quads.map((q, k) => (
                          <polygon
                            key={k}
                            points={points(q)}
                            pathLength={1}
                            style={{ animationDelay: `${(DRAW_START + i * 0.25 + (k / s.quads.length) * DRAW_SPAN).toFixed(2)}s` }}
                          />
                        ))}
                      </svg>
                    ) : null}
                  </div>
                ) : (
                  <div className="shot-placeholder">
                    <Icon name="image" />
                    <span>{t.showcase.placeholder}</span>
                    {dev ? <code>public/showcase/{id}.jpg</code> : null}
                  </div>
                )}
                <figcaption>
                  {item.title}
                  {s?.page ? <span className="shot-meta">{t.showcase.lines(s.lines)}</span> : null}
                </figcaption>
              </figure>
            </ShotLink>
            <span className="marker" aria-hidden="true">
              {n}
            </span>
          </li>
        );
      })}
    </ul>
    <p className="shot-credit">
      {t.showcase.credit} <a href={`${REPO_URL}/issues`}>{t.showcase.creditLink}</a>
    </p>
    </div>
  );
}

