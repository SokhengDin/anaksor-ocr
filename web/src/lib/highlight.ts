// Syntax highlighting with Shiki, at build time only: pages ship the coloured HTML, no
// highlighter in the browser. The theme uses the site's own palette (globals.css).
import type { Element, ElementContent } from "hast";
import { createHighlighterCore, type HighlighterCore, type ShikiTransformer, type ThemeRegistration } from "shiki/core";
import { createJavaScriptRegexEngine } from "shiki/engine/javascript";

export type CodeLang = "python" | "bash" | "json";

// One clearly different hue per kind of token, each at least 4.5:1 on the code background (#e7ece8).
const INK      = "#16232e";   // plain text, file names, values      13.4:1
const INK_SOFT = "#55636c";   // comments, && and |                   5.2:1
const STRING   = "#137a3c";   // green: quoted strings                4.5:1
const KEYWORD  = "#a0168a";   // magenta: import, def, return         5.9:1
const BLUE     = "#0b4fc4";   // blue: commands, functions            6.0:1
const PURPLE   = "#7b2fbf";   // purple: subcommands, JSON keys       5.9:1
const OPTION   = "#b04800";   // orange: -o, --pages                  4.7:1
const RED      = "#c0182c";   // red: numbers, constants, wildcards   5.2:1

const theme: ThemeRegistration = {
  name:   "anaksor",
  type:   "light",
  colors: { "editor.background": "#e7ece8", "editor.foreground": INK },
  tokenColors: [
    { scope: ["comment", "punctuation.definition.comment"],                                   settings: { foreground: INK_SOFT, fontStyle: "italic" } },
    { scope: ["string", "punctuation.definition.string"],                                     settings: { foreground: STRING } },
    { scope: ["keyword", "storage", "keyword.operator.logical", "keyword.control"],           settings: { foreground: KEYWORD } },
    { scope: ["constant.numeric", "constant.language", "support.constant"],                   settings: { foreground: RED } },
    { scope: ["entity.name.function", "support.function", "entity.name.command"],             settings: { foreground: BLUE } },
    { scope: ["constant.other.option", "variable.parameter", "variable.other.normal.shell"],  settings: { foreground: OPTION } },
    { scope: ["support.type.property-name.json"],                                             settings: { foreground: PURPLE } },
    // Shell: bare arguments (file names, values) stay plain ink, so commands, options and quoted strings stand out.
    { scope: ["string.unquoted.argument.shell"],                                              settings: { foreground: INK } },
    { scope: ["entity.name.command.shell", "support.function.builtin.shell"],                 settings: { foreground: BLUE, fontStyle: "bold" } },
    { scope: ["variable.language.special.wildcard.shell"],                                    settings: { foreground: RED } },
    { scope: ["punctuation.separator.statement.and.shell", "keyword.operator.pipe.shell",
              "keyword.operator.redirect.shell", "punctuation.separator.statement.semicolon.shell"], settings: { foreground: INK_SOFT } },
  ],
};

const SUBCOMMAND = /^[a-z][a-z0-9-]*$/;
/** Subcommands that take a subcommand of their own: `uv pip install`. */
const GROUPS = new Set(["pip", "tool", "remote", "stash"]);

/**
 * Shell subcommands (`git clone`, `uv pip install`) in their own colour: the grammar sees them as
 * plain arguments. Only bare words right after the command, before any option, path or value.
 */
const subcommands: ShikiTransformer = {
  name: "anaksor:subcommands",
  tokens(lines) {
    for (const line of lines) {
      let left = 0;   // subcommand words still allowed: one (`pip install`), two after a group (`uv pip install`)
      for (const token of line) {
        const scopes = token.explanation?.flatMap((e) => e.scopes.map((s) => s.scopeName)) ?? [];
        // builtins (cd, echo) take paths and values, never subcommands
        if (scopes.includes("entity.name.command.shell")) { left = scopes.includes("support.function.builtin.shell") ? 0 : 1; continue; }
        if (!left || !token.content.trim()) continue;
        if (scopes.includes("string.unquoted.argument.shell") && SUBCOMMAND.test(token.content.trim())) {
          token.color     = PURPLE;
          token.fontStyle = 0;
          left = GROUPS.has(token.content.trim()) ? left : left - 1;
        } else {
          left = 0;
        }
      }
    }
  },
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
  const html = (await getHighlighter()).codeToHtml(text, {
    lang,
    theme:              "anaksor",
    includeExplanation: lang === "bash" ? "scopeName" : false,   // the subcommand pass needs the scopes
    transformers:       [prompts(marked), subcommands, khmer, plainPre],
  });
  return { html, text };
}
