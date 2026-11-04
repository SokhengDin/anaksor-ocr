import Link from "next/link";

import { type Dict, localePath } from "@/i18n";
import { hint, tableWrap, wrap } from "@/lib/ui";
import { CodeBlock, dedent } from "./CodeBlock";
import { Demo } from "./Demo";
import { HeroName } from "./HeroName";
import { Icon } from "./Icon";
import { HeroShots } from "./HeroShots";
import { SiteFooter } from "./SiteFooter";
import { SiteHeader } from "./SiteHeader";
import { StructuredData } from "./StructuredData";

const band = "py-12 border-t border-hairline";

export function Home({ t }: { t: Dict }) {
  const copy = { copyLabel: t.copyCode, copiedLabel: t.copiedCode };
  return (
    <>
      <StructuredData t={t} />
      <SiteHeader t={t} page="home" />
      <main id="content">
        <div
          data-hero=""
          className={`${wrap} group/hero grid grid-cols-[minmax(0,1fr)_minmax(0,26rem)] gap-10 items-start pt-7 pb-6 max-lg:grid-cols-[minmax(0,1fr)] max-lg:gap-6 max-md:pt-11`}
        >
          <div>
            <HeroName />
            <p className="mt-[.6rem] mb-0 text-ink-soft text-[.95rem]">{t.hero.reading}</p>
            <p className="max-w-[42ch] mt-[.9rem] mb-5 text-[clamp(1.05rem,1.8vw,1.25rem)]/[1.6] km:leading-[1.85] km:max-w-[38ch]">{t.hero.lead}</p>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
              <CodeBlock lang="bash" slim {...copy} code="$ pip install anaksor-ocr" />
              <Link className="inline-flex items-center gap-[.45rem] text-[.95rem]" href={localePath(t.lang, "/docs/")}>
                <Icon name="file" />
                {t.hero.readDocs}
              </Link>
            </div>
          </div>
          <HeroShots t={t} />
        </div>

        {/* The upload comes right after the hero: most visitors come to read a page. */}
        <Demo lang={t.lang} />

        <section className={band} data-testid="band" aria-labelledby="h-features">
          <div className={wrap}>
            <h2 id="h-features">{t.features.title}</h2>
            <dl className="grid grid-cols-2 gap-x-12 gap-y-6 m-0 max-md:grid-cols-1">
              {t.features.items.map((f) => (
                <div key={f.term} className="pl-4 border-l-2 border-jade">
                  <dt className="font-bold text-[1.1rem] mb-[.2rem]">{f.term}</dt>
                  <dd className="m-0 text-ink-soft">{f.text}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section className={band} data-testid="band" aria-labelledby="h-quickstart">
          <div className={`${wrap} grid grid-cols-2 gap-10 items-start max-lg:grid-cols-1 max-lg:gap-4`}>
            {t.accuracy ? <Accuracy accuracy={t.accuracy} /> : <QuickstartText t={t} />}
            <div>
              {t.accuracy ? <QuickstartText t={t} /> : null}
              <CodeBlock lang="python" caption="Python" {...copy} code={dedent`
                import anaksor

                ocr = anaksor.OCR()
                result = ocr("letter.jpg")
                print(result["text"])
              `} />
              <CodeBlock lang="bash" caption="CLI" {...copy} code={dedent`
                $ anaksor scan.pdf -o scan.docx
                # searchable PDF
                $ anaksor scan.pdf -o scan-searchable.pdf
              `} />
              {t.accuracy ? <DocsLink t={t} /> : null}
            </div>
          </div>
        </section>
      </main>
      <SiteFooter t={t} />
    </>
  );
}

function QuickstartText({ t }: { t: Dict }) {
  return (
    <div>
      <h2 id="h-quickstart">{t.quickstart.title}</h2>
      <p>{t.quickstart.text}</p>
      {t.accuracy ? null : <DocsLink t={t} />}
    </div>
  );
}

function DocsLink({ t }: { t: Dict }) {
  return (
    <p>
      <Link href={localePath(t.lang, "/docs/")}>{t.quickstart.docsLink}</Link>
    </p>
  );
}

function Accuracy({ accuracy }: { accuracy: NonNullable<Dict["accuracy"]> }) {
  return (
    <div>
      <h2>{accuracy.title}</h2>
      <div className={tableWrap}>
        <table>
          <thead>
            <tr>
              <th>{accuracy.part}</th>
              <th>{accuracy.set}</th>
              <th>{accuracy.result}</th>
            </tr>
          </thead>
          <tbody>
            {accuracy.rows.map(([part, set, result]) => (
              <tr key={`${part} ${set}`}>
                <td>{part}</td>
                <td>{set}</td>
                <td>{result}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={hint}>{accuracy.note}</p>
    </div>
  );
}
