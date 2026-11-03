import { docsContent } from "@/content/docs";
import type { Dict } from "@/i18n";
import { SiteFooter } from "./SiteFooter";
import { SiteHeader } from "./SiteHeader";
import { Toc } from "./Toc";

export interface DocSection {
  id: string;
  title: string;
  body: React.ReactNode;
}

export function Docs({ t }: { t: Dict }) {
  const { title, intro, sections } = docsContent(t);
  const toc = sections.map(({ id, title }) => ({ id, title }));
  return (
    <>
      <SiteHeader t={t} page="docs" />
      <div className="wrap doc-hero">
        <h1 lang={t.htmlLang}>{title}</h1>
        <p>{intro}</p>
      </div>
      <div className="wrap layout">
        <Toc items={toc} label={t.docs.onThisPage} />
        <main id="content" className="doc">
          <details className="toc-mobile">
            <summary>{t.docs.onThisPage}</summary>
            <ol>
              {toc.map((s) => (
                <li key={s.id}>
                  <a href={`#${s.id}`}>{s.title}</a>
                </li>
              ))}
            </ol>
          </details>
          {sections.map((s) => (
            <section key={s.id} id={s.id} aria-labelledby={`h-${s.id}`}>
              <h2 id={`h-${s.id}`}>{s.title}</h2>
              {s.body}
            </section>
          ))}
        </main>
      </div>
      <SiteFooter t={t} />
    </>
  );
}
