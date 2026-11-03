// Syntax highlighting with Shiki, at build time only: pages ship the coloured HTML, no
// highlighter in the browser. The theme uses the site's own palette (globals.css).
import type { Element, ElementContent } from "hast";
import { createHighlighterCore, type HighlighterCore, type ShikiTransformer, type ThemeRegistration } from "shiki/core";
import { createJavaScriptRegexEngine } from "shiki/engine/javascript";

export type CodeLang = "python" | "bash" | "json";

const INK      = "#16232e";
const INK_SOFT = "#4d5c66";
const JADE     = "#0a5f51";
const SAFFRON  = "#8a5d00";
const BLUE     = "#1f5f8b";
const RUST     = "#a3361f";

const theme: ThemeRegistration = {
  name:   "anaksor",
  type:   "light",
  colors: { "editor.background": "#e7ece8", "editor.foreground": INK },
  tokenColors: [
    { scope: ["comment", "punctuation.definition.comment"],                                   settings: { foreground: INK_SOFT } },
    { scope: ["string", "punctuation.definition.string"],                                     settings: { foreground: JADE } },
    { scope: ["keyword", "storage", "keyword.operator.logical", "keyword.control"],           settings: { foreground: SAFFRON } },
    { scope: ["constant.numeric", "constant.language", "support.constant"],                   settings: { foreground: RUST } },
    { scope: ["entity.name.function", "support.function", "entity.name.command"],             settings: { foreground: BLUE } },
    { scope: ["constant.other.option", "variable.parameter", "variable.other.normal.shell"],  settings: { foreground: SAFFRON } },
    { scope: ["support.type.property-name.json"],                                             settings: { foreground: BLUE } },
  ],
};

let highlighter: Promise<HighlighterCore> | null = null;

function getHighlighter() {
  highlighter ??= createHighlighterCore({
    themes: [theme],
    langs:  [import("shiki/langs/python.mjs"), import("shiki/langs/bash.mjs"), import("shiki/langs/json.mjs")],
    engine: createJavaScriptRegexEngine(),
  });
  return highlighter;
}

/** Khmer letters, signs and digits, with the spaces between Khmer words. */
const KHMER_RUN = /([ក-៿᧠-᧿]+(?:\s+[ក-៿᧠-᧿]+)*)/;

/** Khmer runs get the Battambang font: a monospace font has no Khmer, and a browser's own fallback shapes it badly. */
const khmer: ShikiTransformer = {
  name: "anaksor:khmer",
  span(node) {
    node.children = node.children.flatMap((child): ElementContent[] => {
      if (child.type !== "text" || !KHMER_RUN.test(child.value)) return [child];
      // split() with a capture group alternates: text, Khmer, text, Khmer, ...
      return child.value.split(KHMER_RUN).flatMap((part, i): ElementContent[] => {
        if (!part)     return [];
        if (i % 2 === 0) return [{ type: "text", value: part }];
        return [{ type: "element", tagName: "span", properties: { className: ["km"], lang: "km" }, children: [{ type: "text", value: part }] }];
      });
    });
  },
};

/** "$ " prompts: shown, not part of the code (they are left out when copying and selecting). */
function prompts(lines: Set<number>): ShikiTransformer {
  return {
    name: "anaksor:prompts",
    line(node: Element, line: number) {
      if (lines.has(line)) {
        node.children.unshift({ type: "element", tagName: "span", properties: { className: ["p"], ariaHidden: "true" }, children: [{ type: "text", value: "$ " }] });
      }
    },
  };
}

/** The page's own styles set the block's colours and spacing. */
const plainPre: ShikiTransformer = {
  name: "anaksor:plain-pre",
  pre(node) {
    delete node.properties.style;
    delete node.properties.tabindex;
  },
};

/** Code as highlighted HTML (a <pre>), and the text a copy button should copy. */
export async function highlight(code: string, lang: CodeLang): Promise<{ html: string; text: string }> {
  const marked = new Set<number>();
  const text   = code
    .split("\n")
    .map((line, i) => {
      if (!line.startsWith("$ ")) return line;
      marked.add(i + 1);
      return line.slice(2);
    })
    .join("\n");
  const html = (await getHighlighter()).codeToHtml(text, { lang, theme: "anaksor", transformers: [prompts(marked), khmer, plainPre] });
  return { html, text };
}
