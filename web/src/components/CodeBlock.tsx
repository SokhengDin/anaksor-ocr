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
  className,
}: {
  code: string;
  lang: CodeLang;
  caption?: string;
  copyLabel: string;
  copiedLabel: string;
  className?: string;
}) {
  const { html, text } = await highlight(code, lang);
  return (
    <figure className={`code${className ? ` ${className}` : ""}`}>
      {caption ? <figcaption>{caption}</figcaption> : null}
      <div dangerouslySetInnerHTML={{ __html: html }} />
      <CopyButton text={text} copyLabel={copyLabel} copiedLabel={copiedLabel} />
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
