"use client";

import { useEffect, useState } from "react";

/** Side table of contents; marks the section being read. */
export function Toc({ items, label }: { items: { id: string; title: string }[]; label: string }) {
  const [current, setCurrent] = useState(items[0]?.id);

  useEffect(() => {
    const seen = new Map<string, boolean>();
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) seen.set(e.target.id, e.isIntersecting);
        const first = items.find((i) => seen.get(i.id));
        if (first) setCurrent(first.id);
      },
      { rootMargin: "-80px 0px -60% 0px" },
    );
    for (const i of items) {
      const el = document.getElementById(i.id);
      if (el) io.observe(el);
    }
    return () => io.disconnect();
  }, [items]);

  return (
    <nav className="toc" aria-label={label}>
      <p>{label}</p>
      <ol>
        {items.map((i) => (
          <li key={i.id}>
            <a href={`#${i.id}`} aria-current={current === i.id ? "true" : undefined}>
              {i.title}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
