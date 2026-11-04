import { docsContent } from "@/content/docs";
import type { Dict } from "@/i18n";
import { wrap } from "@/lib/ui";
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
      <div className={`${wrap} pt-12 pb-8`}>
        <h1
          lang={t.htmlLang}
          className="m-0 font-display font-normal text-[clamp(2rem,5vw,3rem)]/[1.6] en:font-text en:font-bold en:text-[clamp(2rem,5vw,2.75rem)]/[1.3] en:tracking-[-.01em]"
        >
          {title}
        </h1>
        <p className="max-w-[60ch] text-ink-soft mt-2 mb-0">{intro}</p>
      </div>
      <div className={`${wrap} grid grid-cols-[13rem_minmax(0,1fr)] gap-14 pb-20 max-md:grid-cols-[minmax(0,1fr)] max-md:gap-0`}>
        <Toc items={toc} label={t.docs.onThisPage} />
        <main id="content" className="min-w-0 max-w-[70ch]">
          <details className="hidden max-md:block mb-8 border border-hairline rounded-lg bg-paper">
            <summary className="py-[.7rem] px-4 cursor-pointer font-bold">{t.docs.onThisPage}</summary>
            <ol className="m-0 pt-0 pr-4 pb-[.8rem] pl-[2.2rem]">
              {toc.map((s) => (
                <li key={s.id}>
                  <a href={`#${s.id}`}>{s.title}</a>
                </li>
              ))}
            </ol>
          </details>
          {sections.map((s) => (
            <section key={s.id} id={s.id} className="pt-4 mb-[3.25rem]" data-testid="doc-section" aria-labelledby={`h-${s.id}`}>
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
