"use client";

import { useState } from "react";

import { Icon } from "./Icon";

/** Copies `text` (the code without its "$ " prompts). */
export function CopyButton({ text, copyLabel, copiedLabel, className }: { text: string; copyLabel: string; copiedLabel: string; className: string }) {
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
    <button
      type="button"
      className={`absolute grid place-items-center border border-hairline rounded-md bg-paper text-ink cursor-pointer hover:border-jade hover:text-jade-deep data-[done]:border-jade data-[done]:text-jade-deep ${className}`}
      data-testid="copy"
      onClick={copy}
      aria-label={done ? copiedLabel : copyLabel}
      data-done={done ? "" : undefined}
    >
      <Icon name={done ? "check" : "copy"} />
    </button>
  );
}
