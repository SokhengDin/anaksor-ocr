import type { ReactNode } from "react";

import { battambang, moul } from "../../fonts";
import "../../globals.css";

export default function EnglishLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${battambang.variable} ${moul.variable}`}>
      <body>{children}</body>
    </html>
  );
}
