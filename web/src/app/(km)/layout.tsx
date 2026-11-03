import type { ReactNode } from "react";

import { battambang, moul } from "../fonts";
import "../globals.css";

// Khmer is the default language: it lives at the root of the site.
export default function KhmerLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="km" className={`${battambang.variable} ${moul.variable}`}>
      <body>{children}</body>
    </html>
  );
}
