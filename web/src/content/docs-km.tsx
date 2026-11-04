import { BenchCharts } from "@/components/BenchCharts";
import { CodeBlock, dedent } from "@/components/CodeBlock";
import type { DocSection } from "@/components/Docs";
import { REPO_URL } from "@/lib/config";
import { steps, tableWrap, tdNum } from "@/lib/ui";

const cb = { copyLabel: "ចម្លងកូដ", copiedLabel: "បានចម្លង" };

export const title = "ឯកសារណែនាំ";
export const intro = "ដំឡើង anaksor-ocr អានរូបថត ឯកសារស្កេន និង PDF ហើយ export អ្វីដែលវាអានបាន។";

export const sections: DocSection[] = [
  {
    id: "install",
    title: "ការដំឡើង",
    body: (
      <>
        <CodeBlock lang="bash" {...cb} code={dedent`
            # រូបភាព នៅលើ ONNX Runtime (មិនត្រូវការ PyTorch)
            $ pip install anaksor-ocr
            # បន្ថែម PyTorch៖ CUDA, Apple MPS និងក្បាលអាន SMTR
            $ pip install "anaksor-ocr[torch]"
            # PyTorch, ការអាន PDF និង export ជា Word
            $ pip install "anaksor-ocr[all]"
          `} />
        <p>
          ត្រូវការ Python 3.11 ឬថ្មីជាងនេះ។ Weights របស់ម៉ូដែល (ប្រហែល 95 MB សម្រាប់ ONNX Runtime និង 113 MB សម្រាប់ PyTorch) ត្រូវបានទាញយកទៅ{" "}
          <code>~/.cache/anaksor</code> នៅពេលអ្នកអានទំព័រដំបូង។
        </p>
        <div className={tableWrap}>
          <table>
            <thead>
              <tr>
                <th />
                <th>ONNX Runtime (លំនាំដើម)</th>
                <th>
                  PyTorch (<code>[torch]</code>)
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>ការដំឡើង</td>
                <td>មិនត្រូវការ PyTorch</td>
                <td>PyTorch (ច្រើន GB ជាមួយ CUDA)</td>
              </tr>
              <tr>
                <td>ឧបករណ៍</td>
                <td>
                  CPU; CUDA ជាមួយ <code>pip install onnxruntime-gpu</code>
                </td>
                <td>CPU, CUDA, Apple MPS</td>
              </tr>
              <tr>
                <td>ល្បឿនលើ CPU</td>
                <td>យឺតជាង</td>
                <td>លឿនជាងប្រហែលពីរដង</td>
              </tr>
              <tr>
                <td>ក្បាលអាន</td>
                <td>CTC (លំនាំដើម), CPPD</td>
                <td>
                  CTC, CPPD និង SMTR (<code>decoder=&quot;gtc&quot;</code> ឬ <code>&quot;auto&quot;</code>)
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          Backend ទាំងពីរឲ្យលទ្ធផលដូចគ្នាទាំងស្រុង ទាំងប្រអប់បន្ទាត់ (box) និងអត្ថបទ។ ប្រសិនបើអ្នកបាន install PyTorch រួចហើយ anaksor នឹងប្រើ PyTorch។
          បើមិនទាន់មានទេ វានឹងប្រើ ONNX Runtime ជំនួសវិញ។ អ្នកក៏អាចកំណត់ backend ដោយខ្លួនឯងបាន តាមរយៈ <code>backend=&quot;torch&quot;</code> ឬ{" "}
          <code>&quot;onnx&quot;</code> (ឬ <code>--backend</code> នៅក្នុង command line)។
        </p>
      </>
    ),
  },
  {
    id: "read",
    title: "អានមួយទំព័រ",
    body: (
      <>
        <CodeBlock lang="python" caption="Python" {...cb} code={dedent`
            import anaksor

            # អាចប្រើ GPU ប្រសិនបើម៉ាសុីនរបស់អ្នកមាន ឬ យើងអាចប្រើ CPU បាន
            ocr = anaksor.OCR()
            result = ocr("letter.jpg")

            print(result["text"])
            for line in result["lines"]:
                print(round(line["rec_score"], 2), line["text"])
          `} />
        <CodeBlock lang="bash" caption="បន្ទាត់ពាក្យបញ្ជា" {...cb} code={dedent`
            # ជាមួយរូបភាព
            $ anaksor letter.jpg
            # ជាមួយឯកសារ Word
            $ anaksor letter.jpg -o letter.docx
            # ឬ PDF
            $ anaksor contract.pdf -o contract-searchable.pdf
          `} />
        <p>
          <code>ocr(...)</code> ទទួលជាbytes រូបភាព PIL ឬអារេ NumPy ជា RGB។ រូបភាពត្រូវបានអានជា JPEG, PNG, WEBP, BMP ឬ TIFF។
        </p>
      </>
    ),
  },
  {
    id: "results",
    title: "លទ្ធផលដែលទទួលបាន",
    body: (
      <>
        <p>អាច បម្លែងលទ្ធផលជាទិន្នន័យសាមញ្ញ JSON ៖ ចង្កោម កថាខណ្ឌ (blocks) ឬ បន្ទាត់នីមួយៗជាមួយទីតាំង និងភាពជឿជាក់។ ឧទាហរណ៍នេះត្រូវបានកាត់ឱ្យខ្លី។</p>
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
      </>
    ),
  },
  {
    id: "documents",
    title: "PDF និង Export",
    body: (
      <>
        <CodeBlock lang="python" {...cb} code={dedent`
            # លទ្ធផលមួយក្នុងមួយទំព័រ ហើយ export ជា PDF
            pages = ocr.read("report.pdf", pages=[1, 2, 3], keep_images=True)

            from anaksor import export
            open("report-searchable.pdf", "wb").write(export.to_pdf(pages))
            open("report.docx", "wb").write(export.to_docx(pages, highlight_low=True))
          `} />
      </>
    ),
  },
  {
    id: "options",
    title: "ជម្រើស",
    body: (
      <>
        <h3>
          ពេលបង្កើត <code>anaksor.OCR(...)</code>
        </h3>
        <div className={tableWrap}>
          <table>
            <thead>
              <tr>
                <th>ជម្រើស</th>
                <th>លំនាំដើម</th>
                <th>អ្វីដែលវាធ្វើ</th>
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
                  <code>&quot;torch&quot;</code> ឬ <code>&quot;onnx&quot;</code>; auto មានន័យថា PyTorch ប្រសិនបើបានដំឡើង
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
                  <code>&quot;cuda&quot;</code>, <code>&quot;cuda:1&quot;</code>, <code>&quot;mps&quot;</code> (សម្រាប់តែ PyTorch) ឬ <code>&quot;cpu&quot;</code>
                </td>
              </tr>
              <tr>
                <td>
                  <code>pad_y</code>, <code>pad_x</code>
                </td>
                <td className={tdNum}>0.16, 0.10</td>
                <td>គែមដែលបន្ថែមជុំវិញបន្ទាត់ពាក្យនីមួយៗមុនពេលអាន ជាប្រភាគនៃកម្ពស់បន្ទាត់។ តិចពេក នឹងអាចកាត់ជើងអក្សរ។</td>
              </tr>
              <tr>
                <td>
                  <code>min_rec_score</code>
                </td>
                <td className={tdNum}>0.5</td>
                <td>អប្បរមាប្រសិទ្ធភាព</td>
              </tr>
              <tr>
                <td>
                  <code>try_vertical</code>, <code>try_180</code>
                </td>
                <td>
                  <code>True</code>, <code>False</code>
                </td>
                <td>សម្រាប់ បង្វិល ៩០ ដឺក្រេ; ឬបញ្ច្រាសរាល់ប្រអប់ពាក្យ</td>
              </tr>
            </tbody>
          </table>
        </div>
        <h3>
          សម្រាប់ទំព័រមួយ៖ <code>ocr(image, ...)</code>
        </h3>
        <div className={tableWrap}>
          <table>
            <thead>
              <tr>
                <th>ជម្រើស</th>
                <th>លំនាំដើម</th>
                <th>អ្វីដែលវាធ្វើ</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <code>unclip_ratio</code>
                </td>
                <td className={tdNum}>1.5</td>
                <td>ប្រអប់ដែលរកឃើញត្រូវបានពង្រីកប៉ុណ្ណា; តម្លៃធំ អាចភ្ជាប់អត្ថបទច្រើនចូលគ្នា ជាប្រអប់តែមួយ</td>
              </tr>
              <tr>
                <td>
                  <code>box_thresh</code>, <code>thresh</code>
                </td>
                <td className={tdNum}>0.5, 0.3</td>
                <td>ភាពជឿជាក់នៃការរកឃើញ៖ ក្នុងមួយប្រអប់ និងក្នុងមួយភីកសែល</td>
              </tr>
              <tr>
                <td>
                  <code>scales</code>
                </td>
                <td>
                  <code>(1.0,)</code>
                </td>
                <td>
                  ការរកបន្ថែម ដូចជា <code>(1.0, 1.6)</code> សម្រាប់អក្សរតូច;
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          ម៉ូដែលទាំងពីរក៏អាចប្រើដាច់ដោយឡែកបានដែរ៖ <code>anaksor.Detector().detect(image)</code> ផ្តល់ប្រអប់ពាក្យជាបន្ទាត់ ហើយ{" "}
          <code>anaksor.Recognizer().recognize([crop, ...])</code> អានប្រអប់ពាក្យដែលបានកាត់រួច។
        </p>
      </>
    ),
  },
  {
    id: "cli",
    title: "CLI",
    body: (
      <>
        <CodeBlock lang="bash" {...cb} code={dedent`
            $ anaksor scan.pdf --pages 1-3,7 -o scan.docx
            # ឯកសារ JSON មួយក្នុងមួយរូបភាព
            $ anaksor photos/*.jpg -o out/ -f json
            # download weights ទុកជាមុន
            $ anaksor --fetch-models
          `} />
        <div className={tableWrap}>
          <table>
            <thead>
              <tr>
                <th>ជម្រើស</th>
                <th>អ្វីដែលវាធ្វើ</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <code>-o</code>, <code>--output</code>
                </td>
                <td>ឯកសារលទ្ធផល ឬថតសម្រាប់ឯកសារបញ្ចូលច្រើន</td>
              </tr>
              <tr>
                <td>
                  <code>-f</code>, <code>--format</code>
                </td>
                <td>
                  <code>text</code>, <code>json</code>, <code>pdf</code> ឬ <code>docx</code>; តាមលំនាំដើម តាមកន្ទុយឈ្មោះឯកសារលទ្ធផល
                </td>
              </tr>
              <tr>
                <td>
                  <code>--pages</code>, <code>--dpi</code>
                </td>
                <td>ទំព័រ PDF ដែលត្រូវអាន ដូចជា 1-3,7; គុណភាពបង្ហាញ (200)</td>
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
                <td>ជម្រើសដែលមានឈ្មោះដូចគ្នាខាងលើ</td>
              </tr>
              <tr>
                <td>
                  <code>--det-weights</code>, <code>--rec-weights</code>
                </td>
                <td>ប្រើ weights ផ្ទាល់ខ្លួន ឬ weights ដែលអ្នកបាន train ផ្ទាល់</td>
              </tr>
              <tr>
                <td>
                  <code>--highlight-low</code>
                </td>
                <td>លទ្ធផល Word៖ គូសបញ្ជាក់ទៅលើពាក្យដែលមានទំនុកចិត្តទាប (Low Confidence)</td>
              </tr>
            </tbody>
          </table>
        </div>
      </>
    ),
  },
  {
    id: "accuracy",
    title: "ភាពត្រឹមត្រូវ ល្បឿន និងដែនកំណត់",
    body: (
      <>
        <BenchCharts
          alt={[
            "ក្រាហ្វ៖ F1 នៃការរកបន្ទាត់ (detection) របស់ v3, v2 និង Chinese baseline",
            "ក្រាហ្វ៖ ភាពត្រឹមត្រូវនៃការអានបន្ទាត់ (recognition) របស់ v4 និង v3 តាមប្រភេទអក្សរ",
            "ក្រាហ្វ៖ ចំនួនវិនាទីក្នុងមួយរូបភាព សម្រាប់ ONNX Runtime និង PyTorch លើ Apple M4 Max",
          ]}
          accuracyNote="លេខភាពត្រឹមត្រូវទាំងអស់ ត្រូវបានវាស់លើ NVIDIA GeForce RTX 5090 (32 GB)។"
          speedNote="ល្បឿនត្រូវបានវាស់លើ Apple M4 Max បន្ទាប់ពីម៉ូដែលត្រូវបាន load រួច។ ម៉ាស៊ីនរបស់អ្នកអាចខុសពីនេះ។"
        />
        <div className={tableWrap}>
          <table>
            <thead>
              <tr>
                <th>ផ្នែក</th>
                <th>វាស់លើ</th>
                <th>លទ្ធផល</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>ការរកបន្ទាត់ (detection) v3</td>
                <td>រូបថតផ្ទៀងផ្ទាត់ KhmerST</td>
                <td>ភាពច្បាស់លាស់ (precision) ០.៧៥ ការរកឃើញ (recall) ០.៧៩</td>
              </tr>
              <tr>
                <td>ការរកបន្ទាត់ (detection) v3</td>
                <td>អក្សរអង់គ្លេសលើរូបថត (HierText)</td>
                <td>ភាពច្បាស់លាស់ (precision) ០.៧៦ ការរកឃើញ (recall) ០.៦៩</td>
              </tr>
              <tr>
                <td>ការរកបន្ទាត់ (detection) v3</td>
                <td>ទំព័រសំយោគ (synthetic)</td>
                <td>ភាពច្បាស់លាស់ (precision) ០.៩៩៨ ការរកឃើញ (recall) ០.៩៩៨</td>
              </tr>
              <tr>
                <td>ការអានអក្សរ (recognition) v4</td>
                <td>បន្ទាត់ពិត ៣៨៧៨ សម្រាប់ផ្ទៀងផ្ទាត់ (ខ្មែរ ឡាតាំង ចម្រុះ (mixed) និងផ្សេងៗ)</td>
                <td>ត្រឹមត្រូវទាំងស្រុង ៨៦.៧% កំហុសតួអក្សរ ១.៣៨%</td>
              </tr>
              <tr>
                <td>ការអានអក្សរ (recognition) v4</td>
                <td>បន្ទាត់ខ្មែរសុទ្ធ ២៤៩៧ ក្នុងចំណោមនោះ</td>
                <td>ត្រឹមត្រូវទាំងស្រុង ៩០.១% កំហុសតួអក្សរ ០.៧៣%</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          KhmerST ដាក់ label តែលើអត្ថបទមួយចំនួនក្នុងរូបថតនីមួយៗ។ ដូច្នេះ សម្រាប់ detection អត្ថបទដែលគ្មាន label ប៉ុន្តែ detector ផ្សេងរកឃើញ ត្រូវបានរាប់ជា
          &quot;don&apos;t care&quot; ដែលធ្វើឱ្យ precision មើលទៅខ្ពស់ជាងការពិតបន្តិច។
        </p>
        <ul>
          <li>អក្សរខ្មែរបោះពុម្ព (printed) ឯកសារ វិក្កយបត្រ និងផ្លាកសញ្ញា អានបានល្អបំផុត។</li>
          <li>
            អក្សរអង់គ្លេស និងអក្សរ Latin ផ្សេងទៀតលើរូបថតនៅខ្សោយ៖ detector អាចរំលងវានៅលើផ្លាកសញ្ញា ហើយ recognizer បានឃើញអក្សរអង់គ្លេសពិតៗតិចតួចពេល train។
          </li>
          <li>
            អក្សរសរសេរដៃ (handwriting) និងអក្សរតុបតែង (decorative) នៅខ្សោយ។ សូមពិនិត្យ <code>rec_score</code> នៃបន្ទាត់នីមួយៗ ឬប្រើ{" "}
            <code>--highlight-low</code> សម្រាប់ output Word។
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "weights",
    title: "Weights របស់ម៉ូដែល",
    body: (
      <>
        <p>
          ម៉ូដែលនីមួយៗមានឯកសារពីរប្រភេទ៖ ONNX graph (<code>.onnx</code> សម្រាប់ ONNX Runtime) និង PyTorch weights (<code>.safetensors</code>)។
          anaksor ទាញយកតែឯកសារដែល backend របស់អ្នកត្រូវការប៉ុណ្ណោះ ហើយស្វែងរកវាតាមលំដាប់ខាងក្រោម៖
        </p>
        <ol className={steps}>
          <li>
            path ដែលអ្នកបានកំណត់ផ្ទាល់ (<code>det_weights=</code> / <code>rec_weights=</code> ឬ <code>--det-weights</code> /{" "}
            <code>--rec-weights</code>);
          </li>
          <li>
            folder ដែលបានកំណត់ក្នុង <code>ANAKSOR_WEIGHTS_DIR</code>;
          </li>
          <li>
            cache នៅក្នុង <code>~/.cache/anaksor</code> (ឬ <code>ANAKSOR_HOME</code>)។ ឯកសារត្រូវបានទាញយកពី Hugging Face តែម្តងគត់
            ហើយត្រូវបានផ្ទៀងផ្ទាត់ជាមួយ SHA-256 មុនពេលប្រើ។ ឯកសារទាំងនេះមកពី commit ដែល release នេះត្រូវបានបង្កើតឡើង ដូច្នេះការ upload
            ថ្មីៗនៅពេលក្រោយ មិនប្តូរលទ្ធផលរបស់អ្នកឡើយ។
          </li>
        </ol>
        <p>
          Weights ទាំងពីរប្រភេទនេះ មិនអាចដំណើរការកូដណាមួយ ពេលកំពុងផ្ទុក (load) បានឡើយ ដូច្នេះវាមានសុវត្ថិភាព។ សម្រាប់ម៉ាស៊ីនដែលគ្មានអ៊ីនធឺណិត សូមដំណើរការ{" "}
          <code>anaksor --fetch-models</code> នៅលើម៉ាស៊ីនមួយផ្សេងទៀតជាមុនសិន រួចចម្លងឯកសារទាំងពីរសម្រាប់ backend របស់អ្នក ទៅដាក់ក្នុង folder{" "}
          <code>ANAKSOR_WEIGHTS_DIR</code>។
        </p>
      </>
    ),
  },
  {
    id: "own-models",
    title: "ម៉ូដែលផ្ទាល់ខ្លួន",
    body: (
      <>
        <p>
          អ្នកអាច Train ម៉ូដែលដោយខ្លួនឯងបានតាមរយះ config តាមទម្រង់ OpenOCR (ទម្រង់ដែលម៉ូដែលទាំងនេះត្រូវបានបង្ហាត់)។
        </p>
        <CodeBlock lang="bash" {...cb} code={dedent`
            $ git clone ${REPO_URL} && cd anaksor-ocr
            $ python tools/spec_from_config.py path/to/svtrv2_cppd_khmer.yml --out specs/
            # សម្រាប់ backend engine onnx (ត្រូវការ [export])
            $ python tools/export_onnx.py --rec best.pth --rec-spec specs/rec-svtrv2-cppd-khmer.yml --out onnx/
          `} />
        <CodeBlock lang="python" caption="Python" {...cb} code={dedent`
            rec = anaksor.Recognizer("specs/rec-svtrv2-cppd-khmer.yml", weights="best.pth")
            ocr = anaksor.OCR(recognizer=rec)
          `} />
      </>
    ),
  },
  {
    id: "develop",
    title: "ការអភិវឌ្ឍ anaksor",
    body: (
      <>
        <CodeBlock lang="bash" {...cb} code={dedent`
            $ git clone ${REPO_URL} && cd anaksor-ocr
            $ uv venv && uv pip install torch --index-url https://download.pytorch.org/whl/cpu
            $ uv pip install -e ".[all]" pytest ruff pip-audit onnx onnxscript
            # មិនត្រូវការ weights ឬអ៊ីនធឺណិតទេ
            $ pytest
          `} />
        <p>
          សូមមើល <a href={`${REPO_URL}/blob/main/CHANGELOG.md`}>កំណត់ត្រាការផ្លាស់ប្តូរ</a> និង <a href={`${REPO_URL}/tree/main/web`}>កូដប្រភពរបស់គេហទំព័រ</a>។
        </p>
      </>
    ),
  },
];
