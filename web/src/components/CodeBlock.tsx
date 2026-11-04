import { type CodeLang, highlight } from "@/lib/highlight";
import { CopyButton } from "./CopyButton";

/**
 * A highlighted code block with a copy button, rendered at build time (Shiki).
 * In `bash`, lines starting with "$ " are commands: the prompt is shown but not copied.
 */
export async function CodeBlock({
  code,
  lang,
  caption,
  copyLabel,
  copiedLabel,
  slim = false,
}: {
  code: string;
  lang: CodeLang;
  caption?: string;
  copyLabel: string;
  copiedLabel: string;
  slim?: boolean;
}) {
  const { html, text } = await highlight(code, lang);
  const place = slim
    ? "right-[.35rem] top-1/2 size-[1.9rem] -translate-y-1/2"
    : `right-2 size-[2.2rem] ${caption ? "top-[2.15rem]" : "top-2"}`;
  return (
    <figure className={`relative ${slim ? "m-0 min-w-[min(100%,17rem)] [&_pre]:text-[.875rem] [&_pre]:py-[.6rem] [&_pre]:pr-11" : "mb-5"}`}>
      {caption ? <figcaption className="text-[.9rem] text-ink-soft mb-[.35rem]">{caption}</figcaption> : null}
      <div dangerouslySetInnerHTML={{ __html: html }} />
      <CopyButton text={text} copyLabel={copyLabel} copiedLabel={copiedLabel} className={place} />
    </figure>
  );
}

/**
 * Code written indented in JSX: drops the first and last empty line and the common indent.
 * Escapes work as in any template string: write \\n for a backslash-n in the code.
 *   code={dedent`
 *     $ pip install anaksor-ocr
 *   `}
 */
export function dedent(strings: TemplateStringsArray, ...values: unknown[]): string {
  // the cooked strings, not String.raw: the compiler may rewrite raw non-ASCII text as \u escapes
  const text   = strings.reduce((out, part, i) => out + part + (i < values.length ? String(values[i]) : ""), "");
  const lines  = text.replace(/^[ \t]*\n/, "").replace(/\n[ \t]*$/, "").split("\n");
  const indent = Math.min(...lines.filter((l) => l.trim()).map((l) => l.match(/^ */)![0].length));
  return lines.map((l) => l.slice(indent)).join("\n");
}
