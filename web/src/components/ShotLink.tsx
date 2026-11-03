"use client";

import type { ReactNode } from "react";

import { type RecordedPage, showRecordedPage } from "@/lib/showcase";

/** A showcase print as a link to the demo: following it shows the print's recorded result there. */
export function ShotLink({ page, label, children }: { page: RecordedPage | null; label: string; children: ReactNode }) {
  if (!page) return <div className="shot-link">{children}</div>;
  return (
    <a className="shot-link" href="#demo" aria-label={label} onClick={() => showRecordedPage(page)}>
      {children}
    </a>
  );
}
