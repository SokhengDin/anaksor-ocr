import { MAX_IMAGE_MB, MAX_PDF_MB, MAX_PDF_PAGES } from "@/lib/config";
import type { Dict } from "./types";

const DIGITS = "០១២៣៤៥៦៧៨៩";

/** Western digits to Khmer digits (other characters unchanged). */
export function kh(value: number | string): string {
  return String(value).replace(/[0-9]/g, (d) => DIGITS[Number(d)] ?? d);
}

export const km: Dict = {
  lang: "km",
  htmlLang: "km",
  meta: {
    title: "អានអក្សរ: កម្មវិធីអានអក្សរខ្មែរពីរូបថត ឯកសារស្កេន និង PDF",
    description:
      "អានអក្សរខ្មែរពីរូបថត ឯកសារស្កេន និង PDF តាមលំដាប់នៃការអាន។ សាកល្បងក្នុង browser ឬដំឡើងដោយ pip install anaksor-ocr។",
    docsTitle: "ឯកសារណែនាំ: អានអក្សរ",
    docsDescription:
      "របៀបដំឡើង anaksor-ocr អានទំព័រ និង PDF, export ជា searchable PDF ឬឯកសារ Word ហើយ run លើ ONNX Runtime ឬ PyTorch។",
  },
  nav: { demo: "សាកល្បង", docs: "ឯកសារណែនាំ", source: "កូដប្រភព", otherLang: "English", otherLangName: "ភាសាអង់គ្លេស", skip: "រំលងទៅខ្លឹមសារ" },
  hero: {
    reading: "កម្មវិធីអានអក្សរខ្មែរ សម្រាប់ Python",
    lead: "ផ្តល់រូបថត ឯកសារស្កេន ឬ PDF ហើយទទួលបានអត្ថបទខ្មែរវិញ តាមលំដាប់នៃការអាន។",
    install: "ដំឡើង",
    readDocs: "អានឯកសារណែនាំ",
  },
  demo: {
    title: "អានមួយទំព័រ",
    intro: "ទម្លាក់រូបថត ឯកសារស្កេន ឬ PDF។ ប្រអប់នីមួយៗបង្ហាញបន្ទាត់អក្សរដែលរកឃើញ ហើយលេខបង្ហាញលំដាប់នៃការអាន។",
    sample: "ទំព័រគំរូនេះត្រូវបានអានដោយម៉ូដែលពិតប្រាកដ។ សាកល្បងជាមួយឯកសាររបស់អ្នក។",
    drop: "ទម្លាក់រូបថត ឬ PDF នៅទីនេះ",
    choose: "ជ្រើសរើសឯកសារ",
    paste: "ឬបិទភ្ជាប់រូបភាព",
    limits: `រូបភាពមិនលើស ${kh(MAX_IMAGE_MB)} MB ហើយ PDF មិនលើស ${kh(MAX_PDF_MB)} MB (${kh(MAX_PDF_PAGES)} ទំព័រ)។ ឯកសារត្រូវបានផ្ញើទៅ API OCR ដើម្បីអាន។`,
    reading: "កំពុងអាន…",
    readingPage: (page, total) => `កំពុងអានទំព័រ ${kh(page)} នៃ ${kh(total)}…`,
    pageLabel: (page) => `ទំព័រ ${kh(page)}`,
    pagesOf: (done, total) => `${kh(done)} នៃ ${kh(total)} ទំព័រ`,
    truncated: (shown, total) => `នៅទីនេះ អានតែ ${kh(shown)} ទំព័រដំបូង ក្នុងចំណោម ${kh(total)} ទំព័រ។`,
    pageFailed: (page) => `មិនអាចអានទំព័រ ${kh(page)} បានទេ។`,
    readAnother: "អានឯកសារផ្សេងទៀត",
    cancel: "បញ្ឈប់",
    status: {
      checking: "កំពុងភ្ជាប់ទៅ API OCR",
      ok: "API OCR រួចរាល់",
      loading: "API OCR កំពុងចាប់ផ្តើម",
      offline: "មិនអាចភ្ជាប់ API OCR បានទេ",
    },
    text: "អត្ថបទ",
    lines: "បន្ទាត់",
    linesHint: "ដាក់ទស្សន៍ទ្រនិចលើបន្ទាត់ ដើម្បីមើលទីតាំងរបស់វានៅលើទំព័រ។",
    check: "គួរពិនិត្យ",
    confidence: "ភាពជឿជាក់",
    copy: "ចម្លងអត្ថបទ",
    copied: "បានចម្លង",
    download: "ទាញយក .txt",
    exportDocx: "ឯកសារ Word",
    exportPdf: "Searchable PDF",
    exportPdfHint: "Searchable PDF មើលទៅដូចឯកសារដើម ប៉ុន្តែមាន text layer ដែលមើលមិនឃើញនៅពីក្រោយ ដូច្នេះអ្នកអាច search, select និង copy អត្ថបទបាន។ បើចង់ edit អត្ថបទ សូម export ជាឯកសារ Word។",
    exporting: "កំពុងរៀបចំ…",
    seconds: (s) => `${kh(s.toFixed(2))} វិនាទី`,
    linesCount: (n) => `${kh(n)} បន្ទាត់`,
    pageImage: "ទំព័រ និងបន្ទាត់អក្សរដែលរកឃើញ",
    errors: {
      network: "មិនអាចភ្ជាប់ទៅ API OCR បានទេ។ សូមពិនិត្យការតភ្ជាប់អ៊ីនធឺណិត ហើយព្យាយាមម្តងទៀត។",
      too_large: `ឯកសារធំពេក៖ រូបភាពមិនលើស ${kh(MAX_IMAGE_MB)} MB ហើយ PDF មិនលើស ${kh(MAX_PDF_MB)} MB។`,
      rate_limited: "មានសំណើច្រើនពេកក្នុងពេលខ្លី។ សូមរង់ចាំមួយនាទី ហើយព្យាយាមម្តងទៀត។",
      unavailable: "API OCR កំពុងចាប់ផ្តើម។ សូមព្យាយាមម្តងទៀតបន្តិចទៀត។",
      rejected: (detail) => `API មិនអាចអានឯកសារនេះបានទេ៖ ${detail}`,
      server: "API OCR មានបញ្ហាជាមួយឯកសារនេះ។ សូមព្យាយាមម្តងទៀត ឬសាកល្បងឯកសារផ្សេង។",
      unsupported: "សូមជ្រើសរើសរូបភាព (JPEG, PNG, WEBP, BMP, TIFF) ឬ PDF។",
      fileTooBig: (mb) => `ឯកសារធំជាង ${kh(mb)} MB។`,
      exportFailed: (detail) => `Export មិនបានសម្រេចទេ៖ ${detail}`,
    },
  },
  features: {
    title: "អ្វីដែលម៉ូដែលអាចធ្វើបាន",
    items: [
      {
        term: "តាមលំដាប់នៃការអាន",
        text: "ជួរឈរ វិក្កយបត្រ និងរូបថតទូរស័ព្ទដែលទ្រេត ចេញមកតាមលំដាប់ដែលមនុស្សអាន។ តម្លៃនៅជាមួយបន្ទាត់មុខទំនិញរបស់វា។",
      },
      {
        term: "ចង្កោមអក្សរខ្មែរពេញលេញ",
        text: "ជើង ស្រៈ និងសញ្ញា នៅជាមួយព្យញ្ជនៈរបស់វា ទោះបីបន្ទាត់វែងត្រូវបានអានជាផ្នែកៗ ហើយភ្ជាប់គ្នាវិញក៏ដោយ។",
      },
      {
        term: "Export",
        text: "អត្ថបទធម្មតា, JSON ដែលមាន box និង confidence score នៃបន្ទាត់នីមួយៗ, searchable PDF ឬឯកសារ Word។",
      },
      {
        term: "នៅលើកុំព្យូទ័ររបស់អ្នក",
        text: "pip install anaksor-ocr run លើ ONNX Runtime ដោយមិនត្រូវការ PyTorch។ បន្ថែម PyTorch ដើម្បីប្រើ CUDA ឬ Apple GPU (MPS)។",
      },
    ],
  },
  showcase: {
    title: "ឧទាហរណ៍ពិត ដែលម៉ូដែលបានសាកល្បង",
    placeholder: "រូបភាពនឹងដាក់ឆាប់ៗ",
    open: "មើលអត្ថបទដែលបានអាន",
    lines: (n) => `${kh(n)} បន្ទាត់`,
    credit:
      "លិខិតនេះជាឯកសាររដ្ឋាភិបាលសាធារណៈ។ រូបថតវិក្កយបត្រ និងផ្លាកសញ្ញា ត្រូវបានរកឃើញតាមរយៈការស្វែងរកលើអ៊ីនធឺណិត ហើយជាកម្មសិទ្ធិរបស់ម្ចាស់ពួកវា ដាក់បង្ហាញតែដើម្បីបង្ហាញលទ្ធផល OCR ប៉ុណ្ណោះ។",
    creditLink: "ជារបស់អ្នក? ស្នើសុំដាក់ឈ្មោះ ឬដកចេញ",
    items: {
      document: { title: "លិខិត", text: "លិខិតស្កេន អានតាមលំដាប់។" },
      receipt:  { title: "វិក្កយបត្រ", text: "តម្លៃនីមួយៗនៅជាមួយមុខទំនិញរបស់វា។" },
      sign:     { title: "ផ្លាកសញ្ញា", text: "ផ្លាកសញ្ញាតាមផ្លូវ ថតដោយទូរស័ព្ទ។" },
    },
  },
  accuracy: null,
  quickstart: {
    title: "ប្រើពី Python",
    text: "ម៉ូដែលដដែលនេះ run ក្នុង Python package នៅលើម៉ាស៊ីនរបស់អ្នកផ្ទាល់។",
    docsLink: "ព័ត៌មានផ្សេងទៀតមាននៅក្នុងឯកសារណែនាំ",
  },
  footer: {
    licence:
      "anaksor-ocr ចេញផ្សាយក្រោម license Apache 2.0។ ម៉ូដែលត្រូវបាន implement ដោយខ្លួនឯងពី papers៖ RepViT + DBNet សម្រាប់ detection និង SVTRv2 សម្រាប់ recognition។",
    fonts: "ប្រើពុម្ពអក្សរ Battambang (SIL Open Font License) និង Khmer OS Muol Light (GNU LGPL)។",
    weights: "Weights របស់ម៉ូដែល",
  },
  docs: { onThisPage: "នៅលើទំព័រនេះ", backHome: "ទំព័រដើម" },
  copyCode: "ចម្លងកូដ",
  copiedCode: "បានចម្លង",
};
