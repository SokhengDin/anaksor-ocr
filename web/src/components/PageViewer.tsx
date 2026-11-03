"use client";

import type { CSSProperties } from "react";

import { LOW_SCORE } from "@/lib/config";
import type { OcrPage, Quad } from "@/lib/types";

const pts = (q: Quad) => q.map(([x, y]) => `${x},${y}`).join(" ");

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
    <div className="viewer" data-fresh={fresh ? "" : undefined}>
      {/* eslint-disable-next-line @next/next/no-img-element -- data: URLs from the API, static export */}
      <img src={src} alt={label} width={w} height={h} />
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden="true">
        {page.lines.map((line, i) => {
          const cls = ["line", line.rec_score < LOW_SCORE ? "low" : "", active === i ? "active" : ""].join(" ").trim();
          return (
            <g
              key={i}
              className={cls}
              style={{ "--i": i } as CSSProperties}
              onMouseEnter={() => onActive(i)}
              onMouseLeave={() => onActive(null)}
            >
              {line.quads.map((q, k) => (
                <polygon key={k} points={pts(q)} pathLength={1} />
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
                <g key={i} className="num" style={{ "--i": i } as CSSProperties}>
                  <circle cx={cx} cy={cy} r={r} />
                  <text x={cx} y={cy} fontSize={r * 1.05}>
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
