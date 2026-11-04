"use client";

import type { ReactNode } from "react";

import { type RecordedPage, showRecordedPage } from "@/lib/showcase";

const LINK = "group/link block text-inherit no-underline outline-none";

/** A showcase print as a link to the demo: following it shows the print's recorded result there. */
export function ShotLink({ page, label, children }: { page: RecordedPage | null; label: string; children: ReactNode }) {
  if (!page) return <div className={LINK}>{children}</div>;
  return (
    <a className={`${LINK} cursor-pointer`} data-testid="shot-link" href="#demo" aria-label={label} onClick={() => showRecordedPage(page)}>
      {children}
    </a>
  );
}
