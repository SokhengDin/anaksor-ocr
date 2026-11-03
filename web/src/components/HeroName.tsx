"use client";

import { useEffect, useRef } from "react";

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
    el.closest(".hero")?.setAttribute("data-ready", "");
    return () => ro.disconnect();
  }, []);

  return (
    <h1 className="name" lang="km">
      <span className="detected">
        <svg ref={svg} className="quad" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <rect x="0" y="0" width="100" height="100" rx="1.5" pathLength={1} />
        </svg>
        <span className="marker" aria-hidden="true">
          ១
        </span>
        អានអក្សរ
      </span>
    </h1>
  );
}
