"use client";

import { useEffect, useRef } from "react";

import { marker } from "@/lib/ui";

/** អានអក្សរ in Moul Light with a detection box drawn around it, numbered 1: the page's
 * one orchestrated moment. The box is sized in pixels so its stroke stays even. */
export function HeroName() {
  const svg = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const el = svg.current;
    if (!el) return;
    const fit = () => {
      const { width, height } = el.getBoundingClientRect();
      const sw = 2.5;
      el.setAttribute("viewBox", `0 0 ${width} ${height}`);
      const r = el.querySelector("rect");
      if (!r) return;
      r.setAttribute("x", String(sw / 2));
      r.setAttribute("y", String(sw / 2));
      r.setAttribute("width", String(Math.max(width - sw, 0)));
      r.setAttribute("height", String(Math.max(height - sw, 0)));
      r.setAttribute("rx", "6");
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    el.closest("[data-hero]")?.setAttribute("data-ready", "");
    return () => ro.disconnect();
  }, []);

  return (
    <h1 className="m-0 font-display font-normal text-[clamp(2.6rem,6vw,4.75rem)]/[1.55] tracking-[.01em]" lang="km">
      <span className="relative inline-block px-[.22em]">
        <svg
          ref={svg}
          className="absolute left-[-.02em] top-[.1em] w-[calc(100%+.04em)] h-[calc(100%-.02em)] overflow-visible -rotate-[1.2deg]"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <rect
            className="fill-jade/6 stroke-jade [stroke-width:2.5] motion-safe:group-data-[ready]/hero:[stroke-dasharray:1] motion-safe:group-data-[ready]/hero:[stroke-dashoffset:1] motion-safe:group-data-[ready]/hero:animate-name-box"
            x="0"
            y="0"
            width="100"
            height="100"
            rx="1.5"
            pathLength={1}
          />
        </svg>
        <span
          className={`${marker} -left-[.9rem] -top-[.2rem] max-sm:-left-[.6rem] motion-safe:group-data-[ready]/hero:opacity-0 motion-safe:group-data-[ready]/hero:[transform:scale(.4)] motion-safe:group-data-[ready]/hero:animate-marker`}
          aria-hidden="true"
        >
          ១
        </span>
        អានអក្សរ
      </span>
    </h1>
  );
}
