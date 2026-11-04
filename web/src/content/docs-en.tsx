import { CodeBlock, dedent } from "@/components/CodeBlock";
import type { DocSection } from "@/components/Docs";
import { BenchCharts } from "@/components/BenchCharts";
import { Icon } from "@/components/Icon";
import { REPO_URL } from "@/lib/config";

const cb = { copyLabel: "Copy code", copiedLabel: "Copied" };

export const title = "Documentation";
export const intro = "Install anaksor-ocr, read photos, scans and PDFs, and export what it reads.";

export const sections: DocSection[] = [
  {
    id: "install",
    title: "Install",
    body: (
      <>
        <CodeBlock lang="bash" {...cb} code={dedent`
            # images, on ONNX Runtime (no PyTorch)
            $ pip install anaksor-ocr
            # adds the PyTorch backend: CUDA, Apple MPS, the SMTR head
            $ pip install "anaksor-ocr[torch]"
            # PyTorch, PDF input and Word export
            $ pip install "anaksor-ocr[all]"
          `} />
        <p>
          Needs Python 3.11 or newer. The model weights (about 95 MB for ONNX Runtime, 113 MB for PyTorch) download to <code>~/.cache/anaksor</code> the
          first time you read a page.
        </p>
        <div className="table">
          <table>
            <thead>
              <tr>
                <th />
                <th>ONNX Runtime (default)</th>
                <th>
                  PyTorch (<code>[torch]</code>)
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Install</td>
                <td>No PyTorch</td>
                <td>PyTorch (several GB with CUDA)</td>
              </tr>
              <tr>
                <td>Devices</td>
                <td>
                  CPU; CUDA with <code>pip install onnxruntime-gpu</code>
                </td>
                <td>CPU, CUDA, Apple MPS</td>
              </tr>
              <tr>
                <td>Speed on CPU</td>
                <td>slower</td>
                <td>about twice as fast</td>
              </tr>
              <tr>
                <td>Reading heads</td>
                <td>CTC (the default), CPPD</td>
                <td>
                  CTC, CPPD, and SMTR (<code>decoder=&quot;gtc&quot;</code> or <code>&quot;auto&quot;</code>)
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          Both backends give the same boxes and the same text. anaksor uses PyTorch if it is installed, and ONNX Runtime otherwise. To choose, pass{" "}
          <code>backend=&quot;onnx&quot;</code> or <code>backend=&quot;torch&quot;</code> (<code>--backend</code> on the command line).
        </p>
      </>
    ),
  },
  {
    id: "read",
    title: "Read a page",
    body: (
      <>
        <CodeBlock lang="python" caption="Python" {...cb} code={dedent`
            import anaksor

            # uses a GPU when there is one, otherwise the CPU
            ocr = anaksor.OCR()
            result = ocr("letter.jpg")

            # the whole page, in reading order
            print(result["text"])
            for line in result["lines"]:
                print(round(line["rec_score"], 2), line["text"])
          `} />
        <CodeBlock lang="bash" caption="Command line" {...cb} code={dedent`
            # text to the terminal
            $ anaksor letter.jpg
            # Word, with the layout rebuilt
            $ anaksor letter.jpg -o letter.docx
            # searchable PDF
            $ anaksor contract.pdf -o contract-searchable.pdf
          `} />
        <p>
          <code>ocr(...)</code> takes a file path, bytes, a PIL image or an RGB NumPy array. Images are read as JPEG, PNG, WEBP, BMP or TIFF, and phone
          photos are turned upright from their EXIF orientation.
        </p>
      </>
    ),
  },
  {
    id: "results",
    title: "What comes back",
    body: (
      <>
        <p>A result is plain JSON-friendly data: the page text, its paragraphs (blocks), and every line with its position and confidence. This example is shortened.</p>
        <CodeBlock lang="json" {...cb} code={dedent`
            {
              "text": "ព្រះរាជាណាចក្រកម្ពុជា\\nជាតិ សាសនា ព្រះមហាក្សត្រ\\n\\n...",
              "blocks": [{"text": ..., "lines": [0, 1], "box": [[412, 96], ...], "rec_score": 0.981}],
              "lines": [
                {"text": "ជាតិ សាសនា ព្រះមហាក្សត្រ",
                 "parts": [...], "box": [...], "quads": [...],
                 "rec_score": 0.987, "det_score": 0.93, "block": 0}
              ],
              "width": 1654, "height": 2339
            }
          `} />
        <dl className="fields">
          <dt>
            <code>text</code>
          </dt>
          <dd>Lines joined with line breaks, paragraphs with a blank line.</dd>
          <dt>
            <code>blocks</code>
          </dt>
          <dd>Paragraphs in reading order, with their box and the indices of their lines.</dd>
          <dt>
            <code>lines</code>
          </dt>
          <dd>
            Each line: <code>text</code>, its <code>box</code> and the detected <code>quads</code> it was built from, the text of each quad in{" "}
            <code>parts</code>, and the recognition and detection confidence.
          </dd>
          <dt>
            <code>width</code>, <code>height</code>
          </dt>
          <dd>The image size the coordinates refer to (after EXIF rotation).</dd>
        </dl>
        <p>
          Reading order handles text columns, receipts (a price stays on its item&apos;s line), skewed phone photos and tightly spaced Khmer lines whose
          stacked vowels and subscripts make neighbouring boxes overlap. Lines longer than the recogniser&apos;s input are read in overlapping windows and
          joined at whole Khmer clusters.
        </p>
      </>
    ),
  },
  {
    id: "documents",
    title: "PDFs and exports",
    body: (
      <>
        <CodeBlock lang="python" {...cb} code={dedent`
            # one result per page; images are kept for the PDF export
            pages = ocr.read("report.pdf", pages=[1, 2, 3], keep_images=True)

            from anaksor import export
            open("report-searchable.pdf", "wb").write(export.to_pdf(pages))
            open("report.docx", "wb").write(export.to_docx(pages, highlight_low=True))
          `} />
        <ul>
          <li>
            <strong>Searchable PDF</strong> keeps each page exactly as scanned and lays the recognised text over it invisibly, so it can be searched,
            selected and copied.
          </li>
          <li>
            <strong>Word</strong> rebuilds the layout from the geometry: headings, centred and right-aligned blocks, indents, prose reflowed into
            paragraphs, and receipt prices aligned on a right tab stop. <code>highlight_low</code> marks lines read with low confidence.
          </li>
        </ul>
        <div className="note">
          <Icon name="info" />
          <p>
            PDF pages are always rendered and read as images, never taken from the PDF&apos;s own text layer. Khmer PDFs often store text in legacy font
            encodings or in glyph order, so their text layer is unreliable even when it is there.
          </p>
        </div>
      </>
    ),
  },
  {
    id: "options",
    title: "Options",
    body: (
      <>
        <h3>
          When creating <code>anaksor.OCR(...)</code>
        </h3>
        <div className="table">
          <table>
            <thead>
              <tr>
                <th>Option</th>
                <th>Default</th>
                <th>What it does</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <code>backend</code>
                </td>
                <td>
                  <code>&quot;auto&quot;</code>
                </td>
                <td>
                  <code>&quot;torch&quot;</code> or <code>&quot;onnx&quot;</code>; auto means PyTorch if it is installed
                </td>
              </tr>
              <tr>
                <td>
                  <code>device</code>
                </td>
                <td>
                  <code>&quot;auto&quot;</code>
                </td>
                <td>
                  <code>&quot;cuda&quot;</code>, <code>&quot;cuda:1&quot;</code>, <code>&quot;mps&quot;</code> (PyTorch only) or <code>&quot;cpu&quot;</code>
                </td>
              </tr>
              <tr>
                <td>
                  <code>pad_y</code>, <code>pad_x</code>
                </td>
                <td className="num">0.16, 0.10</td>
                <td>Margin added around each line before it is read, as a fraction of the line height. Too little cuts off subscripts.</td>
              </tr>
              <tr>
                <td>
                  <code>min_rec_score</code>
                </td>
                <td className="num">0.5</td>
                <td>Lines read with less confidence are left out</td>
              </tr>
              <tr>
                <td>
                  <code>try_vertical</code>, <code>try_180</code>
                </td>
                <td>
                  <code>True</code>, <code>False</code>
                </td>
                <td>Also read tall boxes turned 90 degrees; also read every box upside down</td>
              </tr>
            </tbody>
          </table>
        </div>
        <h3>
          For one page: <code>ocr(image, ...)</code>
        </h3>
        <div className="table">
          <table>
            <thead>
              <tr>
                <th>Option</th>
                <th>Default</th>
                <th>What it does</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <code>unclip_ratio</code>
                </td>
                <td className="num">1.5</td>
                <td>How far detected boxes are grown; larger values join more text into one box</td>
              </tr>
              <tr>
                <td>
                  <code>box_thresh</code>, <code>thresh</code>
                </td>
                <td className="num">0.5, 0.3</td>
                <td>Detection confidence: per box, and per pixel</td>
              </tr>
              <tr>
                <td>
                  <code>scales</code>
                </td>
                <td>
                  <code>(1.0,)</code>
                </td>
                <td>
                  Extra detection passes, such as <code>(1.0, 1.6)</code> for small print; slower
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          The two models also work on their own: <code>anaksor.Detector().detect(image)</code> returns line boxes, and{" "}
          <code>anaksor.Recognizer().recognize([crop, ...])</code> reads cropped lines.
        </p>
      </>
    ),
  },
  {
    id: "cli",
    title: "Command line",
    body: (
      <>
        <CodeBlock lang="bash" {...cb} code={dedent`
            $ anaksor scan.pdf --pages 1-3,7 -o scan.docx
            # one JSON file per image
            $ anaksor photos/*.jpg -o out/ -f json
            # download the weights ahead of time
            $ anaksor --fetch-models
          `} />
        <div className="table">
          <table>
            <thead>
              <tr>
                <th>Option</th>
                <th>What it does</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <code>-o</code>, <code>--output</code>
                </td>
                <td>Output file, or a folder for several inputs. Without it, text and JSON go to the terminal.</td>
              </tr>
              <tr>
                <td>
                  <code>-f</code>, <code>--format</code>
                </td>
                <td>
                  <code>text</code>, <code>json</code>, <code>pdf</code> or <code>docx</code>; by default from the output file&apos;s extension
                </td>
              </tr>
              <tr>
                <td>
                  <code>--pages</code>, <code>--dpi</code>
                </td>
                <td>PDF pages to read, such as 1-3,7; the resolution they are rendered at (200)</td>
              </tr>
              <tr>
                <td>
                  <code>--backend</code>, <code>--device</code>
                </td>
                <td>
                  <code>auto</code>, <code>torch</code>, <code>onnx</code>; <code>auto</code>, <code>cpu</code>, <code>cuda</code>, <code>mps</code>
                </td>
              </tr>
              <tr>
                <td>
                  <code>--pad-y</code>, <code>--pad-x</code>, <code>--min-score</code>
                </td>
                <td>The options of the same name above</td>
              </tr>
              <tr>
                <td>
                  <code>--det-weights</code>, <code>--rec-weights</code>
                </td>
                <td>Use your own weight files</td>
              </tr>
              <tr>
                <td>
                  <code>--highlight-low</code>
                </td>
                <td>Word output: highlight low-confidence lines</td>
              </tr>
            </tbody>
          </table>
        </div>
      </>
    ),
  },
  {
    id: "accuracy",
    title: "Accuracy, speed and limitations",
    body: (
      <>
        <BenchCharts
          alt={[
            "Bar chart: text-line detection F1 of v3, v2 and a Chinese baseline",
            "Bar chart: text-line recognition accuracy of v4 and v3, by script",
            "Bar chart: seconds per image for ONNX Runtime and PyTorch on an Apple M4 Max",
          ]}
          accuracyNote="All accuracy numbers were measured on an NVIDIA GeForce RTX 5090 (32 GB)."
          speedNote="Speed was measured on an Apple M4 Max, once the models were loaded; your machine will differ."
        />
        <div className="table">
          <table>
            <thead>
              <tr>
                <th>Part</th>
                <th>Measured on</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Detection v3</td>
                <td>KhmerST validation photos</td>
                <td>precision 0.75, recall 0.79</td>
              </tr>
              <tr>
                <td>Detection v3</td>
                <td>HierText validation: English on photos</td>
                <td>precision 0.76, recall 0.69</td>
              </tr>
              <tr>
                <td>Detection v3</td>
                <td>synthetic pages</td>
                <td>precision 0.998, recall 0.998</td>
              </tr>
              <tr>
                <td>Recognition v4</td>
                <td>3,878 real validation lines (Khmer, Latin, mixed and other)</td>
                <td>86.7% exactly right, 1.38% character error</td>
              </tr>
              <tr>
                <td>Recognition v4</td>
                <td>the 2,497 Khmer-only lines among them</td>
                <td>90.1% exactly right, 0.73% character error</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          KhmerST labels only some of the text in each photo. When detection is scored, text that has no label but was found by another detector is ignored
          (&quot;don&apos;t care&quot;), which makes precision look slightly better than it is.
        </p>
        <ul>
          <li>Printed Khmer reads best: documents, receipts and signs.</li>
          <li>
            English and other Latin text on photos is weaker: the detector can miss it on signs, and the recogniser saw little real English during training.
          </li>
          <li>
            Handwriting and decorative lettering are weak. Check each line&apos;s <code>rec_score</code>, or use <code>--highlight-low</code> for Word
            output.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "weights",
    title: "Weights",
    body: (
      <>
        <p>Each model comes as two files. Only the one for your backend is downloaded:</p>
        <div className="table">
          <table>
            <thead>
              <tr>
                <th>Backend</th>
                <th>File</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>ONNX Runtime</td>
                <td>
                  ONNX graph (<code>.onnx</code>)
                </td>
              </tr>
              <tr>
                <td>PyTorch</td>
                <td>
                  PyTorch weights (<code>.safetensors</code>)
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>anaksor looks for them in this order and uses the first it finds:</p>
        <ol className="steps">
          <li>
            a path you pass: <code>det_weights=</code> / <code>rec_weights=</code> (or <code>--det-weights</code> / <code>--rec-weights</code>);
          </li>
          <li>
            the folder in <code>ANAKSOR_WEIGHTS_DIR</code>;
          </li>
          <li>
            the cache, <code>~/.cache/anaksor</code> (or <code>ANAKSOR_HOME</code>), filled on first use from the Hugging Face repo{" "}
            <a href="https://huggingface.co/Sokheng/anaksor-ocr">Sokheng/anaksor-ocr</a>.
          </li>
        </ol>
        <p>Downloads are safe and repeatable:</p>
        <ul>
          <li>each file is checked against the SHA-256 in its model spec before it is used, and a file without one is never downloaded;</li>
          <li>neither format can run code when it is loaded;</li>
          <li>files come from the Hub commit this release was built for, so a later upload never changes your results.</li>
        </ul>
        <p>
          <strong>Offline machines:</strong> run <code>anaksor --fetch-models</code> on a machine with internet, then copy the two files for your backend
          into <code>ANAKSOR_WEIGHTS_DIR</code> on the offline one.
        </p>
      </>
    ),
  },
  {
    id: "own-models",
    title: "Your own models",
    body: (
      <>
        <p>
          You can also run your own models trained with OpenOCR-style configs, the format used to train these models. Make a spec from the training config.
          The tools are in the repository, not the installed package, so run them from a clone:
        </p>
        <CodeBlock lang="bash" {...cb} code={dedent`
            $ git clone ${REPO_URL} && cd anaksor-ocr
            $ python tools/spec_from_config.py path/to/svtrv2_cppd_khmer.yml --out specs/
            # for the onnx backend (needs [export])
            $ python tools/export_onnx.py --rec best.pth --rec-spec specs/rec-svtrv2-cppd-khmer.yml --out onnx/
          `} />
        <CodeBlock lang="python" caption="Python" {...cb} code={dedent`
            rec = anaksor.Recognizer("specs/rec-svtrv2-cppd-khmer.yml", weights="best.pth")
            ocr = anaksor.OCR(recognizer=rec)
          `} />
        <p>
          Supported: detection RepViT + DBNet; recognition SVTRv2 (any size) with RCTC + SMTR heads, RCTC alone, or CPPD. <code>.pth</code> checkpoints load
          as they are, with <code>weights_only</code>, so no code runs.
        </p>
      </>
    ),
  },
  {
    id: "security",
    title: "Security",
    body: (
      <>
        <ul>
          <li>
            <strong>Weights never run code.</strong> ONNX graphs are run by ONNX Runtime; PyTorch weights are read with safetensors, or with{" "}
            <code>torch.load(weights_only=True)</code>, and anything that needs more is refused.
          </li>
          <li>
            <strong>Untrusted images reach few decoders.</strong> Only JPEG, PNG, WEBP, BMP and TIFF are opened, and Pillow&apos;s limit on oversized images
            stays on.
          </li>
          <li>
            <strong>Dependencies are audited.</strong> Even the oldest versions the package allows have no known vulnerabilities.
          </li>
        </ul>
        <p>
          Report a vulnerability privately through <a href={`${REPO_URL}/security/advisories/new`}>GitHub security advisories</a>.
        </p>
      </>
    ),
  },
  {
    id: "develop",
    title: "Working on anaksor",
    body: (
      <>
        <CodeBlock lang="bash" {...cb} code={dedent`
            $ git clone ${REPO_URL} && cd anaksor-ocr
            $ uv venv && uv pip install torch --index-url https://download.pytorch.org/whl/cpu
            $ uv pip install -e ".[all]" pytest ruff pip-audit onnx onnxscript
            # no weights or network needed
            $ pytest
          `} />
        <p>
          See the <a href={`${REPO_URL}/blob/main/CHANGELOG.md`}>changelog</a> and the <a href={`${REPO_URL}/tree/main/web`}>website&apos;s source</a>.
        </p>
      </>
    ),
  },
];
