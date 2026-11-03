import Link from "next/link";

import { type Dict, localePath } from "@/i18n";
import { CodeBlock, dedent } from "./CodeBlock";
import { Demo } from "./Demo";
import { HeroName } from "./HeroName";
import { Icon } from "./Icon";
import { HeroShots } from "./HeroShots";
import { SiteFooter } from "./SiteFooter";
import { SiteHeader } from "./SiteHeader";
import { StructuredData } from "./StructuredData";

export function Home({ t }: { t: Dict }) {
  const copy = { copyLabel: t.copyCode, copiedLabel: t.copiedCode };
  return (
    <>
      <StructuredData t={t} />
      <SiteHeader t={t} page="home" />
      <main id="content">
        <div className="wrap hero">
          <div className="hero-text">
            <HeroName />
            <p className="reading">{t.hero.reading}</p>
            <p className="lead">{t.hero.lead}</p>
            <div className="actions">
              <CodeBlock lang="bash" className="install" {...copy} code="$ pip install anaksor-ocr" />
              <Link href={localePath(t.lang, "/docs/")}>
                <Icon name="file" />
                {t.hero.readDocs}
              </Link>
            </div>
          </div>
          <HeroShots t={t} />
        </div>

        {/* The upload comes right after the hero: most visitors come to read a page. */}
        <Demo lang={t.lang} />

        <section className="band" aria-labelledby="h-features">
          <div className="wrap">
            <h2 id="h-features">{t.features.title}</h2>
            <dl className="features">
              {t.features.items.map((f) => (
                <div key={f.term}>
                  <dt>{f.term}</dt>
                  <dd>{f.text}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section className="band" aria-labelledby="h-quickstart">
          <div className="wrap two">
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
                # ${t.lang === "km" ? "ឬ PDF" : "searchable PDF"}
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
      <div className="table">
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
      <p className="hint">{accuracy.note}</p>
    </div>
  );
}
