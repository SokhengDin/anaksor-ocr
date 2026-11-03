"use client";

import { useState } from "react";

import { Icon } from "./Icon";

/** Copies `text` (the code without its "$ " prompts). */
export function CopyButton({ text, copyLabel, copiedLabel }: { text: string; copyLabel: string; copiedLabel: string }) {
  const [done, setDone] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text.trim());
    } catch {
      return;
    }
    setDone(true);
    setTimeout(() => setDone(false), 1600);
  }

  return (
    <button type="button" className="copy" onClick={copy} aria-label={done ? copiedLabel : copyLabel} data-done={done ? "" : undefined}>
      <Icon name={done ? "check" : "copy"} />
    </button>
  );
}
