"use client";

import type { CSSProperties } from "react";

import { LOW_SCORE } from "@/lib/config";
import type { OcrPage, Quad } from "@/lib/types";

const pts = (q: Quad) => q.map(([x, y]) => `${x},${y}`).join(" ");
const DRAW_LINE = "motion-safe:[stroke-dasharray:1] motion-safe:[stroke-dashoffset:1] motion-safe:opacity-0 motion-safe:animate-line";

export function PageViewer({
  page,
  src,
  active,
  onActive,
  fresh,
  numbered,
  number,
  label,
}: {
  page: OcrPage;
  src: string;
  active: number | null;
  onActive: (i: number | null) => void;
  fresh: boolean;
  numbered: boolean;
  number: (n: number) => string;
  label: string;
}) {
  const { width: w, height: h } = page;
  const r = Math.max(w, h) * 0.019; // marker radius in page pixels: readable at any page size
  return (
    <div
      className="relative leading-[0] bg-sheet shadow-[0_1px_0_var(--color-hairline),0_12px_28px_-18px_rgba(22,35,46,.45)]"
      data-testid="viewer"
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- data: URLs from the API, static export */}
      <img className="block w-full h-auto" src={src} alt={label} width={w} height={h} />
      <svg className="absolute inset-0 size-full overflow-visible" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden="true">
        {page.lines.map((line, i) => {
          const look =
            active === i
              ? "fill-saffron/24 stroke-saffron-ink [stroke-width:3]"
              : `fill-jade/9 [stroke-width:2] ${line.rec_score < LOW_SCORE ? "stroke-saffron" : "stroke-jade"}`;
          return (
            <g
              key={i}
              data-testid="line"
              data-active={active === i ? "" : undefined}
              style={{ "--i": i } as CSSProperties}
              onMouseEnter={() => onActive(i)}
              onMouseLeave={() => onActive(null)}
            >
              {line.quads.map((q, k) => (
                <polygon key={k} className={`[vector-effect:non-scaling-stroke] ${look} ${fresh ? DRAW_LINE : ""}`} points={pts(q)} pathLength={1} />
              ))}
            </g>
          );
        })}
        {numbered
          ? page.lines.map((line, i) => {
              const [x, y] = line.box[0];
              const cx = Math.max(x - r * 0.9, r + 2);
              const cy = Math.max(y + r * 0.2, r + 2);
              return (
                <g
                  key={i}
                  className={`pointer-events-none ${fresh ? "motion-safe:opacity-0 motion-safe:animate-num" : ""}`}
                  data-testid="line-marker"
                  style={{ "--i": i } as CSSProperties}
                >
                  <circle className="fill-saffron stroke-sheet [stroke-width:2] [vector-effect:non-scaling-stroke]" cx={cx} cy={cy} r={r} />
                  <text className="fill-ink font-text font-bold [text-anchor:middle] [dominant-baseline:central]" x={cx} y={cy} fontSize={r * 1.05}>
                    {number(i + 1)}
                  </text>
                </g>
              );
            })
          : null}
      </svg>
    </div>
  );
}
