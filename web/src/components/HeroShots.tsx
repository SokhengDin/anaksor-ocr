import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { type Dict, kh } from "@/i18n";
import type { ShowcaseId } from "@/i18n/types";
import { asset, REPO_URL } from "@/lib/config";
import type { RecordedPage } from "@/lib/showcase";
import type { OcrPage, Quad } from "@/lib/types";
import { marker } from "@/lib/ui";
import { Icon } from "./Icon";
import { ShotLink } from "./ShotLink";

const IDS: ShowcaseId[]  = ["document", "receipt", "sign"];
const EXTENSIONS         = [".jpg", ".jpeg", ".png", ".webp"];
const TYPES: Record<string, string> = { ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp" };
const DIR                = join(process.cwd(), "public", "showcase");
const PLACE: Record<ShowcaseId, string> = {
  document: "left-0 top-[6%] w-[56%] -rotate-5 z-1",
  receipt:  "right-[1%] top-0 w-[39%] rotate-4 z-2",
  sign:     "left-[17%] bottom-0 w-[64%] -rotate-[1.5deg] z-3",
};
const ASPECT: Record<ShowcaseId, string> = {
  document: "aspect-[3/4]",
  receipt:  "aspect-[9/16]",
  sign:     "aspect-[16/10]",
};

/** The boxes start after the name's own box and markers (HeroName), and all finish within this time. */
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
    <div className="min-w-0">
    <ul
      className="relative aspect-[1/.9] m-0 p-0 list-none max-lg:flex max-lg:gap-5 max-lg:aspect-auto max-lg:overflow-x-auto max-lg:pt-4 max-lg:pb-5 max-lg:px-3 max-lg:-mx-3 max-lg:snap-x max-lg:snap-mandatory max-lg:[scroll-padding-inline:.75rem] max-lg:items-start"
      data-testid="shots"
      aria-label={t.showcase.title}
    >
      {IDS.map((id, i) => {
        const s    = shot(id);
        const item = t.showcase.items[id];
        const n    = t.lang === "km" ? kh(i + 2) : String(i + 2);
        return (
          <li
            key={id}
            className={`group/shot absolute outline-none transition-[translate,rotate] duration-250 ease-[cubic-bezier(.3,0,.2,1)] motion-reduce:transition-none hover:z-5 hover:rotate-0 hover:-translate-y-1.5 focus-within:z-5 focus-within:rotate-0 focus-within:-translate-y-1.5 max-lg:relative max-lg:inset-auto max-lg:flex-[0_0_min(15rem,62%)] max-lg:rotate-0 max-lg:snap-start max-lg:hover:translate-y-0 max-lg:focus-within:translate-y-0 ${PLACE[id]}`}
            data-testid={`shot-${id}`}
          >
            <ShotLink page={s?.page ?? null} label={`${item.title}: ${t.showcase.open}`}>
              <figure className="m-0 pt-[.45rem] px-[.45rem] pb-[.15rem] bg-sheet border border-hairline rounded-md shadow-[0_14px_30px_-16px_rgb(22_35_46/.45),0_2px_5px_rgb(22_35_46/.08)] group-focus-visible/link:outline-3 group-focus-visible/link:outline-jade group-focus-visible/link:outline-offset-3">
                {s ? (
                  <div className="relative">
                    {/* eslint-disable-next-line @next/next/no-img-element -- plain files from public/ */}
                    <img className={`block w-full rounded-[3px] object-cover ${ASPECT[id]}`} src={s.src} alt={item.text} decoding="async" />
                    {s.quads.length ? (
                      // the same crop as the photo's object-fit: cover
                      <svg
                        className="absolute inset-0 size-full rounded-[3px] pointer-events-none"
                        viewBox={`0 0 ${s.width} ${s.height}`}
                        preserveAspectRatio="xMidYMid slice"
                        aria-hidden="true"
                      >
                        {s.quads.map((q, k) => (
                          <polygon
                            key={k}
                            className="fill-jade/14 stroke-jade [stroke-width:1.5] [vector-effect:non-scaling-stroke] [stroke-linejoin:round] transition-[fill] duration-200 group-hover/shot:fill-saffron/30 group-hover/shot:stroke-saffron-ink group-focus-within/shot:fill-saffron/30 group-focus-within/shot:stroke-saffron-ink motion-safe:[stroke-dasharray:1] motion-safe:[stroke-dashoffset:1] motion-safe:[fill-opacity:0] motion-safe:group-data-[ready]/hero:animate-shot-box"
                            points={points(q)}
                            pathLength={1}
                            style={{ animationDelay: `${(DRAW_START + i * 0.25 + (k / s.quads.length) * DRAW_SPAN).toFixed(2)}s` }}
                          />
                        ))}
                      </svg>
                    ) : null}
                  </div>
                ) : (
                  <div
                    className={`grid place-content-center justify-items-center gap-[.4rem] w-full p-3 text-center rounded-[3px] border border-dashed border-[color-mix(in_srgb,var(--color-ink-soft)_45%,transparent)] text-ink-soft bg-paper-deep text-[.85rem]/[1.5] [&_svg]:size-7 [&_code]:text-[.7rem] [&_code]:bg-transparent [&_code]:break-all ${ASPECT[id]}`}
                  >
                    <Icon name="image" />
                    <span>{t.showcase.placeholder}</span>
                    {dev ? <code>public/showcase/{id}.jpg</code> : null}
                  </div>
                )}
                <figcaption className="flex justify-between items-baseline gap-2 pt-[.35rem] px-[.15rem] pb-[.25rem] text-[.85rem] text-ink-soft">
                  {item.title}
                  {s?.page ? <span className="text-[.75rem] text-jade-deep whitespace-nowrap group-hover/link:underline">{t.showcase.lines(s.lines)}</span> : null}
                </figcaption>
              </figure>
            </ShotLink>
            <span
              className={`${marker} -left-[.7rem] -top-[.7rem] motion-safe:group-data-[ready]/hero:opacity-0 motion-safe:group-data-[ready]/hero:[transform:scale(.4)] motion-safe:group-data-[ready]/hero:animate-marker`}
              style={{ animationDelay: `${(1.3 + i * 0.12).toFixed(2)}s` }}
              aria-hidden="true"
            >
              {n}
            </span>
          </li>
        );
      })}
    </ul>
    <p className="mt-5 mb-0 text-[.72rem]/[1.55] km:leading-[1.8] text-ink-soft">
      {t.showcase.credit} <a href={`${REPO_URL}/issues`}>{t.showcase.creditLink}</a>
    </p>
    </div>
  );
}

