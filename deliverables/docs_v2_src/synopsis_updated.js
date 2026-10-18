// Updated project synopsis (structure of the group's original synopsis, rewritten and brought up to date).
// Citations are written as {key} or {key1,key2}; numbers are assigned in order of first appearance.
// Usage: node synopsis_updated.js <out.docx>
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType, WidthType, BorderStyle,
  Footer, ShadingType, VerticalAlign, ImageRun, PageNumber, LevelFormat,
  PositionalTab, PositionalTabAlignment, PositionalTabRelativeTo, PositionalTabLeader,
} = require("docx");

const OUT = process.argv[2];
const HERE = __dirname;
const F = "Times New Roman";
const TITLE = "Satya-Score: An AI Hallucination Detection & Scoring Framework";
const TW = 8162;
const PAGES_FILE = path.join(HERE, "pages_synopsis.json");
const PAGES = fs.existsSync(PAGES_FILE) ? JSON.parse(fs.readFileSync(PAGES_FILE, "utf8").replace(/^﻿/, "")) : {};
// index rows: [Sr. No., title, text of the heading in the body (searched to find its page), kind]
const INDEX = [
  ["1", "Abstract", "Abstract:", "main"],
  ["2", "I. Introduction", "I. Introduction:", "main"],
  ["", "a. Motivation", "a. Motivation:", "sub"],
  ["", "b. Problem Statement", "b. Problem Statement:", "sub"],
  ["3", "II. Feasibility Study", "II. Feasibility Study:", "main"],
  ["4", "III. Literature Survey", "III. Literature Survey:", "main"],
  ["5", "IV. Objective & Scope of the Project", "IV. Objective & Scope of the Project:", "main"],
  ["6", "V. Proposed System", "V. Proposed System:", "main"],
  ["7", "VI. Implementation Status and Results", "VI. Implementation Status and Results:", "main"],
  ["8", "VII. Requirements", "VII. Requirements:", "main"],
  ["", "Software Requirements", "Software Requirements:", "sub"],
  ["", "Hardware Requirements", "Hardware Requirements:", "sub"],
  ["9", "VIII. Future Work", "VIII. Future Work:", "main"],
  ["10", "References", "References:", "main"],
  ["11", "Signatures", "Students Name", "main"],
];
const INDEX_FIGS = [["Fig. 1", "Architecture of Satya-Score", "Fig. 1: Architecture"], ["Fig. 2", "Decision for a Claim no Source Decides", "Fig. 2: Decision"],
  ["Table 1", "Results of the Components", "Table 1: Results of the Components"],
  ["Table 2", "Held-out Comparison, Version 1 and Version 2", "Table 2: Held-out Comparison"]];
fs.writeFileSync(path.join(HERE, "keys_synopsis.json"), JSON.stringify([...INDEX.map(x => x[2]), ...INDEX_FIGS.map(x => x[2])]));

// ---------- references (only those cited are printed, numbered by first citation) ----------
const REFS = {
  huang: "L. Huang et al., “A survey on hallucination in large language models: Principles, taxonomy, challenges, and open questions,” ACM Trans. Inf. Syst., vol. 43, no. 2, 2025, doi: 10.1145/3703155.",
  llama3: "A. Grattafiori et al., “The Llama 3 herd of models,” arXiv:2407.21783, 2024, doi: 10.48550/arXiv.2407.21783.",
  fever: "J. Thorne, A. Vlachos, C. Christodoulopoulos, and A. Mittal, “FEVER: A large-scale dataset for fact extraction and VERification,” in Proc. NAACL-HLT, 2018, doi: 10.18653/v1/N18-1074.",
  xlmr: "A. Conneau et al., “Unsupervised cross-lingual representation learning at scale,” in Proc. ACL, 2020, doi: 10.18653/v1/2020.acl-main.747.",
  agrawal: "G. Agrawal, T. Kumarage, Z. Alghamdi, and H. Liu, “Can knowledge graphs reduce hallucinations in LLMs? A survey,” arXiv:2311.07914, 2023, doi: 10.48550/arXiv.2311.07914.",
  mushroom: "R. Vázquez et al., “SemEval-2025 Task 3: Mu-SHROOM, the multilingual shared task on hallucinations and related observable overgeneration mistakes,” in Proc. SemEval, 2025, arXiv:2504.11975, doi: 10.48550/arXiv.2504.11975.",
  factscore: "S. Min et al., “FActScore: Fine-grained atomic evaluation of factual precision in long form text generation,” in Proc. EMNLP, 2023, doi: 10.48550/arXiv.2305.14251.",
  selfcheck: "P. Manakul, A. Liusie, and M. J. F. Gales, “SelfCheckGPT: Zero-resource black-box hallucination detection for generative large language models,” in Proc. EMNLP, 2023, doi: 10.48550/arXiv.2303.08896.",
  wikidata: "D. Vrandečić and M. Krötzsch, “Wikidata: A free collaborative knowledgebase,” Commun. ACM, vol. 57, no. 10, pp. 78–85, 2014, doi: 10.1145/2629489.",
  worldbank: "The World Bank, “World Bank Open Data.” [Online]. Available: https://data.worldbank.org",
  who: "World Health Organization, “The Global Health Observatory.” [Online]. Available: https://www.who.int/data/gho",
  googlefc: "Google, “Fact Check Tools API.” [Online]. Available: https://developers.google.com/fact-check/tools/api",
  muril: "S. Khanuja et al., “MuRIL: Multilingual representations for Indian languages,” arXiv:2103.10730, 2021, doi: 10.48550/arXiv.2103.10730.",
  indicsuite: "D. Kakwani et al., “IndicNLPSuite: Monolingual corpora, evaluation benchmarks and pre-trained multilingual language models for Indian languages,” in Findings of EMNLP, 2020, doi: 10.18653/v1/2020.findings-emnlp.445.",
  sbertml: "N. Reimers and I. Gurevych, “Making monolingual sentence embeddings multilingual using knowledge distillation,” in Proc. EMNLP, 2020, doi: 10.48550/arXiv.2004.09813.",
  debertav3: "P. He, J. Gao, and W. Chen, “DeBERTaV3: Improving DeBERTa using ELECTRA-style pre-training with gradient-disentangled embedding sharing,” in Proc. ICLR, 2023, doi: 10.48550/arXiv.2111.09543.",
  faiss: "J. Johnson, M. Douze, and H. Jégou, “Billion-scale similarity search with GPUs,” IEEE Trans. Big Data, vol. 7, no. 3, pp. 535–547, 2021, doi: 10.1109/TBDATA.2019.2921572.",
  true: "O. Honovich et al., “TRUE: Re-evaluating factual consistency evaluation,” in Proc. NAACL-HLT, 2022, doi: 10.18653/v1/2022.naacl-main.287.",
  truthfulqa: "S. Lin, J. Hilton, and O. Evans, “TruthfulQA: Measuring how models mimic human falsehoods,” in Proc. ACL, 2022, doi: 10.18653/v1/2022.acl-long.229.",
  halueval: "J. Li, X. Cheng, X. Zhao, J.-Y. Nie, and J.-R. Wen, “HaluEval: A large-scale hallucination evaluation benchmark for large language models,” in Proc. EMNLP, 2023, doi: 10.18653/v1/2023.emnlp-main.397.",
  refchecker: "X. Hu et al., “Knowledge-centric hallucination detection,” in Proc. EMNLP, 2024, doi: 10.18653/v1/2024.emnlp-main.395.",
  anah: "Z. Ji et al., “ANAH: Analytical annotation of hallucinations in large language models,” in Proc. ACL, 2024, doi: 10.18653/v1/2024.acl-long.442.",
  fava: "A. Mishra, A. Asai, V. Balachandran, Y. Wang, G. Neubig, Y. Tsvetkov, and H. Hajishirzi, “Fine-grained hallucination detection and editing for language models,” in Proc. COLM, 2024, doi: 10.48550/arXiv.2401.06855.",
  mind: "W. Su, C. Wang, Q. Ai, Y. Hu, Z. Wu, Y. Zhou, and Y. Liu, “Unsupervised real-time hallucination detection based on the internal states of large language models,” in Findings of ACL, 2024, doi: 10.18653/v1/2024.findings-acl.854.",
  minicheck: "L. Tang, P. Laban, and G. Durrett, “MiniCheck: Efficient fact-checking of LLMs on grounding documents,” in Proc. EMNLP, 2024, doi: 10.48550/arXiv.2404.10774.",
  mccoy: "R. T. McCoy, E. Pavlick, and T. Linzen, “Right for the wrong reasons: Diagnosing syntactic heuristics in natural language inference,” in Proc. ACL, 2019, doi: 10.18653/v1/P19-1334.",
  msa: "B. Hikal, A. Nasreldin, and A. Hamdi, “MSA at SemEval-2025 Task 3: High quality weak labeling and LLM ensemble verification for multilingual hallucination detection,” in Proc. SemEval, 2025. [Online]. Available: https://aclanthology.org/2025.semeval-1.131/",
  hausa: "M. Bala et al., “HausaNLP at SemEval-2025 Task 3: Towards a fine-grained model-aware hallucination detection,” in Proc. SemEval, 2025. [Online]. Available: https://aclanthology.org/2025.semeval-1.227/",
  detectives: "P. Elchafei and M. Abu-Elkheir, “Hallucination Detectives at SemEval-2025 Task 3: Span-level hallucination detection for LLM-generated answers,” in Proc. SemEval, 2025. [Online]. Available: https://aclanthology.org/2025.semeval-1.84/",
  shroomcap: "A. Sinha et al., “SHROOM-CAP: Shared task on hallucinations and related observable overgeneration mistakes in crosslingual analyses of publications,” in Proc. CHOMPS, 2025, doi: 10.18653/v1/2025.chomps-main.7.",
  bhramil: "H. Terdalkar, K. Bhojani, A. Dongare, and O. A. Behera, “BHRAM-IL: A benchmark for hallucination recognition and assessment in multiple Indian languages,” in Proc. BHASHA Workshop, 2025, doi: 10.18653/v1/2025.bhasha-1.9.",
  indicsbert: "S. Deode et al., “L3Cube-IndicSBERT: A simple approach for learning cross-lingual sentence representations using multilingual BERT,” arXiv:2304.11434, 2023, doi: 10.48550/arXiv.2304.11434.",
  indicxnli: "D. Aggarwal, V. Gupta, and A. Kunchukuttan, “IndicXNLI: Evaluating multilingual inference for Indian languages,” arXiv:2204.08776, 2022, doi: 10.48550/arXiv.2204.08776.",
  mnli: "A. Williams, N. Nangia, and S. R. Bowman, “A broad-coverage challenge corpus for sentence understanding through inference,” in Proc. NAACL-HLT, 2018, doi: 10.18653/v1/N18-1101.",
  xnli: "A. Conneau et al., “XNLI: Evaluating cross-lingual sentence representations,” in Proc. EMNLP, 2018, doi: 10.18653/v1/D18-1269.",
  rag: "P. Lewis et al., “Retrieval-augmented generation for knowledge-intensive NLP tasks,” in Proc. NeurIPS, 2020, doi: 10.48550/arXiv.2005.11401.",
  multihal: "K. Lavrinovics, R. Biswas, K. Hose, and J. Bjerva, “MultiHal: Multilingual dataset for knowledge-graph grounded evaluation of LLM hallucinations,” arXiv:2505.14101, 2025, doi: 10.48550/arXiv.2505.14101.",
  factkg: "J. Kim, S. Park, Y. Kwon, Y. Jo, J. Thorne, and E. Choi, “FactKG: Fact verification via reasoning on knowledge graphs,” in Proc. ACL, 2023, doi: 10.18653/v1/2023.acl-long.895.",
  kgr: "X. Guan et al., “Mitigating large language model hallucinations via autonomous knowledge graph-based retrofitting,” in Proc. AAAI, vol. 38, no. 16, pp. 18126–18134, 2024, doi: 10.1609/aaai.v38i16.29770.",
  lavrinovics: "K. Lavrinovics, R. Biswas, J. Bjerva, and K. Hose, “Knowledge graphs, large language models, and hallucinations: An NLP perspective,” J. Web Semantics, vol. 85, art. 100844, 2025, doi: 10.1016/j.websem.2024.100844.",
  spacy: "M. Honnibal, I. Montani, S. Van Landeghem, and A. Boyd, “spaCy: Industrial-strength natural language processing in Python,” Zenodo, 2020, doi: 10.5281/zenodo.1212303.",
  indicnlp: "A. Kunchukuttan, “The IndicNLP Library,” 2020. [Online]. Available: https://github.com/anoopkunchukuttan/indic_nlp_library",
  gptoss: "OpenAI, “gpt-oss-120b & gpt-oss-20b model card,” arXiv:2508.10925, 2025, doi: 10.48550/arXiv.2508.10925.",
  judge: "L. Zheng et al., “Judging LLM-as-a-judge with MT-Bench and Chatbot Arena,” in Proc. NeurIPS (Datasets and Benchmarks Track), 2023.",
  xfact: "A. Gupta and V. Srikumar, “X-FACT: A new benchmark dataset for multilingual fact checking,” in Proc. ACL-IJCNLP (Short Papers), 2021, pp. 675–682, doi: 10.18653/v1/2021.acl-short.86.",
  ollama: "Ollama. [Online]. Available: https://ollama.com",
};
const ORDER = [];
function cite(s) {
  return s.replace(/\{([a-z0-9,]+)\}/g, (_, keys) => keys.split(",").map(k => {
    if (!REFS[k]) throw new Error("unknown reference " + k);
    if (!ORDER.includes(k)) ORDER.push(k);
    return `[${ORDER.indexOf(k) + 1}]`;
  }).join(", "));
}

// ---------- helpers ----------
const r = (t, o = {}) => new TextRun({ text: cite(t), font: F, size: o.size || 24, bold: o.bold, italics: o.italics });
const runs = (parts, o = {}) => (Array.isArray(parts) ? parts : [parts]).map(x => typeof x === "string" ? r(x, o) : x);
const p = (parts, o = {}) => new Paragraph({ alignment: o.align || AlignmentType.JUSTIFIED, spacing: { line: 360, after: 140 },
  keepNext: o.keepNext, children: runs(parts, { italics: o.italics }) });
// Sections that start on a new page (as laid out by the group in Word, 2026-10-07).
const NEW_PAGE = new Set(["I. Introduction:", "II. Feasibility Study:", "III. Literature Survey:", "V. Proposed System:",
  "VI. Implementation Status and Results:", "References:"]);
const H = (t) => new Paragraph({ keepNext: true, pageBreakBefore: NEW_PAGE.has(t),
  spacing: { before: NEW_PAGE.has(t) ? 0 : 280, after: 140 }, children: [r(t, { bold: true, size: 28 })] });
const h = (t) => new Paragraph({ keepNext: true, spacing: { before: 160, after: 100 }, children: [r(t, { bold: true })] });
const lead = (label, text) => p([r(label, { bold: true }), r(text)]);
const list = (ref, items) => items.map(it => new Paragraph({ numbering: { reference: ref, level: 0 }, alignment: AlignmentType.JUSTIFIED,
  spacing: { line: 360, after: 60 }, children: runs(it) }));

const line = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const borders = { top: line, bottom: line, left: line, right: line };
const cell = (text, w, o = {}) => new TableCell({ width: { size: w, type: WidthType.DXA }, borders, verticalAlign: VerticalAlign.CENTER,
  shading: o.head ? { fill: "D9D9D9", type: ShadingType.CLEAR, color: "auto" } : undefined, margins: { top: 60, bottom: 60, left: 100, right: 100 },
  children: [new Paragraph({ alignment: o.center ? AlignmentType.CENTER : AlignmentType.LEFT, spacing: { line: 276 }, children: [r(text, { bold: o.head, size: 22 })] })] });
const table = (rows, widths, centerCols = []) => new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: widths,
  rows: rows.map((cells, i) => new TableRow({ tableHeader: i === 0, cantSplit: true,
    children: cells.map((c, j) => cell(c, widths[j], { head: i === 0, center: i === 0 || centerCols.includes(j) })) })) });
const tcap = (t) => new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 160, after: 100 }, children: [r(t, { bold: true })] });
const gap = (after = 120) => new Paragraph({ spacing: { after }, children: [] });
function img(file, widthPx, type = "png") {
  const buf = fs.readFileSync(path.join(HERE, file));
  let w, hgt;
  if (type === "png") { w = buf.readUInt32BE(16); hgt = buf.readUInt32BE(20); }
  else { // JPEG: find the SOF0/SOF2 marker for the size
    let i = 2;
    while (i < buf.length) { const m = buf[i + 1], len = buf.readUInt16BE(i + 2);
      if (m === 0xC0 || m === 0xC2) { hgt = buf.readUInt16BE(i + 5); w = buf.readUInt16BE(i + 7); break; } i += 2 + len; }
  }
  return new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 80 },
    children: [new ImageRun({ type, data: buf, transformation: { width: widthPx, height: Math.round(widthPx * hgt / w) } })] });
}
const tab = (a) => new PositionalTab({ alignment: a, relativeTo: PositionalTabRelativeTo.MARGIN, leader: PositionalTabLeader.NONE });

// ---------- title page (same layout as the original synopsis) ----------
const c = (t, o = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: o.after ?? 120, before: o.before || 0 }, children: [r(t, o)] });
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const infoRow = (label, value, bold = true) => new TableRow({ children: [
  new TableCell({ width: { size: 3000, type: WidthType.DXA }, borders: { top: NONE, bottom: NONE, left: NONE, right: NONE },
    margins: { top: 80, bottom: 80, left: 0, right: 100 }, children: [new Paragraph({ children: [r(label, { bold: true })] })] }),
  new TableCell({ width: { size: 5162, type: WidthType.DXA }, borders: { top: NONE, bottom: NONE, left: NONE, right: NONE },
    margins: { top: 80, bottom: 80, left: 100, right: 0 },
    children: (Array.isArray(value) ? value : [value]).map(v => new Paragraph({ spacing: { after: 100 }, children: [r(v, { bold })] })) })] });
const titlePage = [
  c("A Project Synopsis Submitted for", { size: 26, before: 200 }),
  c("Bachelor of Technology", { size: 26, italics: true }),
  c("Project & Seminar (7SA08)", { size: 26, after: 240 }),
  img("logo/Image18.jpg", 230, "jpg"),
  gap(240),
  new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: [3000, 5162], rows: [
    infoRow("PROJECT TITLE", TITLE),
    infoRow("PROJECT GROUP NO.", "10"),
    infoRow("NAME OF PROJECTEES", ["1. BORKAR VIVEK YESHWANTRAO", "2. NANDE PIYUSH DEVIDAS", "3. JUMADE AASAWARI SAHEBRAO", "4. WANKHADE ARUNIMA TRIDIP"]),
    infoRow("NAME OF GUIDE", "Dr. R. R. Karwa"),
  ] }),
  c("Department of Artificial Intelligence & Data Science,", { bold: true, size: 26, before: 360 }),
  c("Prof. Ram Meghe Institute of Technology & Research, Badnera-Amravati.", { bold: true, size: 24 }),
  c("2026-2027", { bold: true, size: 26 }),
];

// ---------- body ----------
const ICOLS = [1150, 5862, 1150];
const pg = (k) => (PAGES[k] ? String(PAGES[k]) : "");
const irow = (cells, o = {}) => new TableRow({ cantSplit: true, children: cells.map((t, j) => new TableCell({
  width: { size: ICOLS[j], type: WidthType.DXA }, borders, verticalAlign: VerticalAlign.CENTER,
  shading: o.head ? { fill: "D9D9D9", type: ShadingType.CLEAR, color: "auto" } : undefined,
  margins: { top: 70, bottom: 70, left: 120, right: 120 },
  children: [new Paragraph({ alignment: j === 1 && !o.head ? AlignmentType.LEFT : AlignmentType.CENTER,
    indent: j === 1 && o.sub ? { left: 360 } : undefined,
    children: [new TextRun({ text: t, font: F, size: 24, bold: o.head || (j === 1 && o.main) })] })] })) });
const indexPage = [
  new Paragraph({ alignment: AlignmentType.CENTER, pageBreakBefore: true, spacing: { after: 300 }, children: [r("INDEX", { bold: true, size: 30 })] }),
  new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: ICOLS, rows: [
    irow(["Sr. No.", "Particulars", "Page No."], { head: true }),
    ...INDEX.map(([n, t, k, kind]) => irow([n, t, pg(k)], { main: kind === "main", sub: kind === "sub" })),
  ] }),
  new Paragraph({ spacing: { before: 360, after: 200 }, alignment: AlignmentType.CENTER, children: [r("LIST OF FIGURES AND TABLES", { bold: true, size: 26 })] }),
  new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: ICOLS, rows: [
    irow(["No.", "Title", "Page No."], { head: true }),
    ...INDEX_FIGS.map(([n, t, k]) => irow([n, t, pg(k)])),
  ] }),
];

const body = [
  ...indexPage,
  new Paragraph({ alignment: AlignmentType.CENTER, pageBreakBefore: true, spacing: { after: 240 }, children: [r(TITLE, { bold: true, size: 30 })] }),
  new Paragraph({ spacing: { after: 120 }, children: [r("Abstract:", { bold: true, italics: true })] }),
  p("AI chatbots based on large language models (LLMs) often give answers that read smoothly yet contain statements that are false or invented. Such hallucinations are hard to spot by reading alone, and for Hindi there are almost no tools to check them. Satya-Score is a claim-level hallucination detection and scoring framework for English and Hindi text, with Marathi kept as a later extension. The system splits an answer into separate factual claims and checks every claim against the most dependable source available for it: official statistics of the World Bank and the WHO and the Wikidata knowledge graph first, then published fact-checks, and, when none of these apply, Wikipedia passages that a multilingual inference model compares with the claim. A structured source that holds the fact decides directly; otherwise a matching fact-check decides. For the remaining claims, Version 2 of the system adds an LLM cross-check: an open-weight language model (gpt-oss-20b, running on the project laptop) reads the claim and the retrieved passages, and its verdict counts only when the passage evidence agrees with it. Each claim is labelled Verified, Uncertain or Hallucinated together with its evidence, the wrong words marked in the text and, when a structured source decided it, the correct fact.", { italics: true }),
  p("Earlier work has studied claim-level checking, multilingual detection and knowledge-graph grounding mostly in isolation; Satya-Score brings them together in one working web application with Hindi support. Facts held in structured sources are judged almost without error. On a held-out sample of 620 English and Hindi items from public benchmarks, evaluated once, the cross-check caught 47% of the false items against 25% without it, let only 6% of them pass as Verified against 22%, and raised false alarms on 13% of true items against 11%. It met three of the four acceptance criteria fixed in advance, narrowly missing the target of doubling the catches. The work is being carried forward as a research paper and a copyright registration through the institute.", { italics: true }),

  H("I. Introduction:"),
  p("Text written by LLMs is now part of everyday life: chat assistants answer questions, tools draft documents, and search engines summarise results. These models are trained to produce likely sequences of words rather than to look facts up, so they sometimes state things that are wrong or unsupported in a confident tone {huang}. When such text is used for health information, education, news or public services, an unnoticed error can mislead many people, which makes automatic detection and measurement of hallucinations important."),
  p("This project lies at the meeting point of three areas of natural language processing: fact verification {fever}, multilingual language modelling {xlmr} and reasoning over knowledge graphs {agrawal}. Most hallucination research so far concerns English. Hindi has hundreds of millions of speakers and is increasingly present in chatbot output, yet checking support for it is limited {mushroom}. Satya-Score is our response to this gap: a framework that checks English and Hindi AI answers claim by claim, with Marathi planned as the next language."),
  p("Most existing detectors rely on one kind of evidence {fever,selfcheck}. Satya-Score breaks every answer into individual claims {factscore} and gathers several kinds of evidence for each: structured facts from Wikidata {wikidata}, country statistics from the World Bank and the WHO {worldbank,who}, published fact-checks {googlefc}, and retrieved Wikipedia passages judged by a natural language inference (NLI) model. A structured source that holds the fact decides; otherwise a matching fact-check decides. Claims that none of these settle go to an LLM cross-check, in which an open-weight LLM {gptoss} and the passage evidence must agree before a claim is called Verified, and the LLM must name a wrong fact before it is called Hallucinated. Each claim is then placed in one of three classes: Verified, Uncertain or Hallucinated. Marathi, with more than 80 million speakers, is a natural extension, since Indic resources such as MuRIL and IndicNLPSuite already cover it {muril,indicsuite}."),
  h("a. Motivation:"),
  p("Chatbots, writing assistants and AI search are used by students, journalists, customer-service teams and ordinary users alike. Their usefulness comes from fluent, confident text, and that same fluency hides mistakes. Hallucination is not a rare glitch but a consequence of how generative models work. As more decisions rely on AI-written text, unchecked errors spread misinformation and slowly erode trust in these systems."),
  p("For Hindi users the problem is sharper. A Hindi speaker who receives an AI answer has no simple way to find out which statement in it is true. The building blocks for such a checker are already available: multilingual models such as XLM-R, NLI models trained on many languages, and open knowledge sources such as Wikidata and official statistics. What has been missing is a system that joins these parts, supports Hindi properly and explains its decisions. Building that system is the motivation for Satya-Score."),
  h("b. Problem Statement:"),
  p("There is no dependable tool that takes an LLM answer in English or Hindi, checks each of its factual claims against trustworthy sources, and points out exactly which claims are false. Existing tools usually rate a whole answer as reliable or unreliable, which is of little help when only one sentence of a long answer is wrong, and very few of them handle Hindi."),
  p("Satya-Score addresses this by dividing an answer into individual claims, verifying each claim against structured and textual sources, and reporting for every claim a verdict, a score, the deciding source and, when a structured source holds it, the correct fact, for both English and Hindi."),

  H("II. Feasibility Study:"),
  p("The feasibility of Satya-Score was examined from four angles: technical, time and resources, need, and significance."),
  lead("Technical Feasibility: ", "The project builds on openly available models and data rather than training large models from scratch. A multilingual XLM-R sentence encoder {sbertml} is used for semantic search, a multilingual mDeBERTa model {debertav3} fine-tuned for inference judges evidence, FAISS {faiss} searches about one lakh Wikipedia passages, and Wikidata, the World Bank, the WHO and the Google Fact Check Tools API supply structured facts. The LLM cross-check uses gpt-oss-20b {gptoss}, an open-weight model under the Apache 2.0 licence, run locally with Ollama {ollama} or, optionally, through the Groq cloud service. The main engineering effort lies in claim extraction, in routing each claim to the right source, in the rules that combine the evidence, and in the web application. This keeps the technical risk low; the complete system, including the LLM, already runs on a laptop with a 6 GB GPU. Work was divided into model development, data engineering, back-end integration, and research with front-end development, so that members could progress in parallel."),
  lead("Time and Resource Feasibility: ", "The work was planned for about 15–16 weeks with weekly milestones for each member. All models, libraries and data sources used are free to use for academic work, and no paid cloud resources were needed: development and testing were done on a laptop GPU, with optional free cloud notebooks."),
  lead("Need: ", "Hallucination is a widely recognised and still unsolved problem in deploying LLMs. No existing tool offers claim-level, source-grounded checking with real Hindi support and readable explanations, which justifies building the proposed system."),
  lead("Significance: ", "Apart from its academic value, Satya-Score helps Hindi- and English-speaking users judge AI answers before relying on them. The project also contributes a human-labelled bilingual claim dataset and a documented evaluation that other researchers can build on."),

  H("III. Literature Survey:"),
  p("Research on LLM hallucination has grown rapidly. The work most relevant to this project falls into five groups: basic detection methods, multilingual detection, cross-lingual and Indic language resources, retrieval-based fact verification, and detection grounded in knowledge graphs. Each group has made clear progress on its own, but they have rarely been combined."),
  lead("Basic detection methods. ", "FEVER {fever} defined the now common sequence of claim, evidence and verdict. FActScore {factscore} applied it at a finer level by splitting long answers into atomic facts, an idea Satya-Score uses in its claim-extraction step. SelfCheckGPT {selfcheck} avoids external sources by testing whether repeated samples of a model agree, but it cannot catch an error that the model repeats consistently. TRUE {true} offers a common way to evaluate factual-consistency metrics rather than a new detector. Benchmarks such as TruthfulQA {truthfulqa} and HaluEval {halueval} provide fixed test sets, and the survey by Huang et al. {huang} organises the field. Later methods moved towards finer and faster checking: knowledge-centric checking of extracted claim triplets (RefChecker) {refchecker}, the ANAH dataset of sentence-level analytical annotations {anah}, span-level detection and editing in FAVA {fava}, and real-time detection from a model’s internal states in MIND {mind}. MIND needs access to the model’s hidden layers, which is not possible for closed commercial chatbots; Satya-Score works only on the output text. Compact checkers such as MiniCheck {minicheck} judge whether a sentence is supported by a given document, and McCoy et al. {mccoy} showed that inference models can rely on word overlap, a weakness that also affects passage-based checking. Strong LLMs are increasingly used as judges and agree with human preferences in many tasks {judge}, but a judge shares the blind spots of its own model family; Satya-Score therefore lets an LLM count only together with retrieved evidence. Most of these methods use a single kind of evidence and none provides meaningful Hindi support."),
  lead("Multilingual detection. ", "X-FACT {xfact} collected statements in 25 languages, Hindi among them, rated by professional fact-checkers. The SemEval-2025 Mu-SHROOM task {mushroom} built hallucination benchmarks in 14 languages including Hindi and reported considerable disagreement between annotators, which shaped our own agreement study. Participating systems such as MSA {msa}, HausaNLP {hausa} and Hallucination Detectives {detectives} used ensembles of LLMs, model-aware detection and span-level decomposition, but none of them used a knowledge graph. SHROOM-CAP {shroomcap} covered nine languages including Hindi, limited to scientific publications and to binary labels. BHRAM-IL {bhramil}, a recent benchmark of about 36,000 questions in Hindi, Gujarati, Marathi, Odia and English, measures how often LLMs hallucinate in Indian languages; it evaluates models rather than checking a given answer. Hindi hallucination detection therefore already exists; what is missing is its combination with graded scoring grounded in structured sources."),
  lead("Cross-lingual and Indic resources. ", "XLM-R {xlmr} and MuRIL {muril} are multilingual encoders, the latter designed for Indian languages and transliterated text, and IndicNLPSuite {indicsuite} supplies Indic corpora and benchmarks. IndicSBERT {indicsbert} and IndicXNLI {indicxnli} provide sentence-similarity and inference resources for Indian languages, including Marathi. Inference models are commonly trained on MultiNLI {mnli} and its cross-lingual extension XNLI {xnli}; the inference model used in Satya-Score is fine-tuned on both."),
  lead("Retrieval-based fact verification. ", "Retrieval-augmented generation {rag} showed that supplying retrieved evidence while generating text reduces factual errors. RAG acts during generation, whereas Satya-Score checks text that has already been produced, which suits an auditing tool that cannot change how a third-party chatbot generates its answers."),
  lead("Knowledge-graph-grounded detection. ", "MultiHal {multihal} is the closest earlier work: a benchmark that pairs questions with knowledge-graph paths in English and five European languages and scores answers with similarity and inference measures. It is an evaluation resource rather than a checker, and it covers neither Hindi nor real-time use. FactKG {factkg} verifies claims by reasoning over a knowledge graph alone and in English only. KGR {kgr} uses a knowledge graph to correct hallucinated text automatically rather than to score and flag it. Surveys by Agrawal et al. {agrawal} and Lavrinovics et al. {lavrinovics} conclude that the role of knowledge graphs in reducing hallucination is still an open question."),
  lead("Identified gap. ", "The literature contains two separate lines of work: multilingual detectors without knowledge-graph grounding (Mu-SHROOM, SHROOM-CAP) and knowledge-graph-grounded work without Hindi support (MultiHal, FactKG, KGR). No reviewed system combines claim-level checking, several evidence sources including structured facts and official statistics, explanations with the correct fact, real-time use and Hindi support in one tool. Satya-Score is designed for this space. Its novelty does not lie in any single model or source, all of which already exist, but in combining them into one deployable and explainable system."),

  H("IV. Objective & Scope of the Project:"),
  p("The objectives move step by step from understanding the problem to building and testing the solution:"),
  ...list("roman", [
    "To analyse hallucination in LLM answers.",
    "To compare existing hallucination-detection methods.",
    "To design a claim-level detection framework for English and Hindi.",
    "To integrate an LLM with retrieved evidence so that neither decides alone.",
    "To develop a secure web application that explains each verdict.",
    "To evaluate the system on public benchmarks with pre-set criteria."]),
  p([r("Scope: ", { bold: true }), r("The system covers English and Hindi; Marathi is a future extension. It checks factual statements such as dates, places, people, quantities, statistics and general facts, and skips opinions, advice and questions. The novelty claimed lies in the way the components are combined, in particular the rule that lets an LLM count only when the evidence agrees, not in the pretrained models or data sources (XLM-R, mDeBERTa, gpt-oss-20b, Wikidata, World Bank, WHO), which are existing public resources. The system detects, scores and explains hallucinations and shows the correct fact where a source provides it; it does not rewrite the original text.")]),

  H("V. Proposed System:"),
  p("A user pastes an AI answer, or uploads a .txt or .pdf file, in the web application. The back end extracts the claims and sends each one to the most suitable source; the results are combined into a verdict per claim and an overall verdict for the whole text. The modules are listed below, and Fig. 1 shows how they are connected."),
  ...list("modules", [
    [r("Claim extraction: ", { bold: true }), r("English text is parsed with spaCy {spacy}; compound sentences are split into simple claims and each pronoun is replaced by the topic it refers to. Hindi text is split into sentences with the Indic NLP Library {indicnlp}.")],
    [r("Evidence retrieval: ", { bold: true }), r("claims and passages are embedded with a multilingual XLM-R sentence encoder {sbertml} and searched in a FAISS index {faiss} of 102,069 English and Hindi Wikipedia passages; relevant articles missing from the index are fetched from live Wikipedia.")],
    [r("Inference: ", { bold: true }), r("a multilingual mDeBERTa model {debertav3} fine-tuned on MultiNLI and XNLI {mnli,xnli} decides whether each passage supports or contradicts the claim. Support from any passage counts, but only a passage about the claim’s own subject may contradict it; this keeps false alarms low, at the cost of catching fewer hallucinations.")],
    [r("Structured sources: ", { bold: true }), r("places and dates of birth and death, founding dates, capitals, authors, office-holders, quantities and currencies are checked in Wikidata {wikidata} in English and Hindi; country statistics are checked against the World Bank and, for life expectancy and infant mortality, also the WHO {worldbank,who}, and when both report a figure they must agree; a published fact-check {googlefc} is applied only when it is about the same claim, so that negated claims are not mismatched.")],
    [r("LLM cross-check (Version 2): ", { bold: true }), r("every claim that no structured source or fact-check decided is read by gpt-oss-20b {gptoss} together with the five best passages; the model may also use its own knowledge and returns a verdict, the wrong words and a reason. A claim is Verified only when the passages support it and the LLM agrees. It is Hallucinated only when the LLM names a wrong fact (a reason that merely says the evidence is missing does not count) and a second reading, in which the model sees only the ten retrieved passages, does not find the claim stated there. The same second reading can confirm a claim left Uncertain that one reader judged true. Fig. 2 shows the decision.")],
    [r("Scoring and explanation (CMHSA): ", { bold: true }), r("HalluScore = α·SemSim + β·NLI + γ·KG. Similarity measures topic rather than truth, so it is excluded (α is fixed at 0) and β and γ (about 0.5 each) are trained on labelled claims. When statistics or Wikidata answer, their decision sets the score (1.0 supported, 0.0 contradicted) and the correct fact is shown; otherwise a matching fact-check sets it (0.05 false, 0.95 true); otherwise the cross-check sets the verdict, and the score is the mean of the passage score and the LLM’s probability, kept inside the verdict’s range. A claim scoring below 0.35 is Hallucinated, above 0.65 Verified, and Uncertain otherwise. The whole text is Hallucinated when at least a third of its claims are.")],
    [r("Web application: ", { bold: true }), r("FastAPI back end and React front end with user accounts, history of checks, export, password change and reset, and access from mobile phones. Flagged claims have their wrong words underlined, and each claim card shows what the passages, the LLM and the second reading said.")],
  ]),

  img("fig1_architecture_v2.png", 430),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [r("Fig. 1: Architecture of Satya-Score", { bold: true })] }),
  img("fig2_decision_v2.png", 470),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [r("Fig. 2: Decision for a claim that no structured source or fact-check decided (s: passage score; j: LLM verdict)", { bold: true })] }),
  H("VI. Implementation Status and Results:"),
  p("All modules described above have been implemented and tested with 319 automated tests. Without the LLM, network look-ups run in parallel and a typical answer of six claims is checked in about 5 seconds the first time and in under 1 second when repeated (on the laptop GPU). With the LLM cross-check, a six-claim answer takes about 46 seconds when the model runs on the laptop and about 16–22 seconds when the Groq cloud service answers first, with the laptop model taking over whenever Groq’s free per-minute limit is reached; a repeated answer takes under 3 seconds. The application can be shared through a secure public https link served from the laptop, and it is packaged as a container for cloud hosting; on the public link, sign-in requests from other websites and the developer API key were both tested and refused. The evaluation data consist of 456 claims from chatbot answers generated with Llama 3.3 {llama3} (266 English, 190 Hindi), labelled by a team of four annotators (the authors) who shared the claims and reviewed AI-suggested verdicts, and checked in two blind rounds (two independent annotators agreed with κ = 0.53 on 56 claims), plus 40 further claims from two other LLMs. Most changes were tested against a decision rule fixed in advance. In four cases the final decision went against the rule: the evidence rule and reading ten passages instead of three were adopted although one of their checks failed, and an LLM judge and a larger inference model were not adopted although the rule favoured them. Two exploratory analyses are reported as such. Table 1 lists the results of the components."),
  tcap("Table 1: Results of the Components"),
  table([
    ["Test", "Result"],
    ["Unseen true Wikipedia sentences (128)", "113 Verified; 4 false alarms"],
    ["Labelled test claims: true (66) / hallucinated (10)", "3 false alarms / 0 caught from Wikipedia text alone"],
    ["Knowledge-graph decisions (40 relational claims, English)", "11 of 13 correct (pre-registered); 12 of 12 after a linking fix (exploratory)"],
    ["Knowledge-graph ablation, pre-registered (same 40 claims)", "AUC 0.704 → 0.784; Hallucinated-F1 0.512 → 0.615"],
    ["Official statistics (40 randomly chosen countries)", "137 of 137 false figures caught; no true figure contradicted"],
    ["Published fact-checks (25 rumours, 15 true claims)", "0 wrong decisions; rumours caught rose from 3 to 10"],
  ], [4100, 4062]),
  gap(),
  p("The results show that claims covered by structured sources are judged reliably and that true text rarely raises a false alarm. Hallucinations that no structured source covers, such as misconceptions and over-generalisations, are hard to catch from encyclopaedic text alone: on the training claims only 5 of 45 were caught and 27 were marked Verified. In a pre-registered test, adding the knowledge graph improved on the inference signal alone; letting the knowledge graph decide whenever it answers was chosen afterwards in an exploratory analysis. The knowledge-graph tests used English claims; the Hindi checks are implemented but have been tested on fewer examples."),
  p("The LLM cross-check (Version 2) was built to close this gap. It was evaluated on seven public and constructed test sets in which no label was written by the project team: FEVER {fever}, Mu-SHROOM answers in English and Hindi {mushroom}, TruthfulQA {truthfulqa}, Hindi rumours from X-FACT {xfact}, and Hindi Wikipedia sentences with one number changed, both as written and reworded. The model was chosen on development data, and each held-out sample was used only once. The rule was refined over three earlier held-out rounds, two of which failed their criteria; the final version was then run once on 620 new items (Table 2)."),
  tcap("Table 2: Held-out Comparison, Version 1 and Version 2 (620 items)"),
  table([
    ["Measure", "Version 1", "Version 2", "Criterion fixed in advance"],
    ["False items caught", "95/374 (25%)", "176/374 (47%)", "at least 2× Version 1: not met (1.85×)"],
    ["False items passed as Verified", "83/374 (22%)", "23/374 (6%)", "at most half: met"],
    ["True items Verified", "137/246 (56%)", "139/246 (57%)", "at most 5 points lower: met"],
    ["False alarms on true items", "28/246 (11%)", "32/246 (13%)", "at most 3 points higher: met"],
  ], [2300, 1500, 1500, 2862], [1, 2]),
  gap(),
  p("The gains in catches and in false items no longer passed as Verified are statistically significant (p < 0.001), while the change in false alarms is not. The largest gains are in Hindi: Hindi Wikipedia sentences with a changed number were caught 39% of the time instead of 3%, and false Mu-SHROOM Hindi claims 45% instead of 7%. The LLM alone caught 86% of the false items but raised false alarms on 28% of true ones, which is why its verdict counts only together with the evidence. Since the catches did not quite double, Version 2 met three of the four criteria and is offered as a mode that can be switched on, while Version 1 remains the default."),

  H("VII. Requirements:"),
  h("Software Requirements:"),
  table([
    ["Sr. No.", "Category", "Requirement"],
    ["1", "Programming languages", "Python 3.13, TypeScript"],
    ["2", "Deep learning frameworks", "PyTorch, Hugging Face Transformers, Sentence-Transformers"],
    ["3", "Pretrained models", "XLM-R sentence encoder (paraphrase-xlm-r-multilingual-v1), mDeBERTa-v3-base-mnli-xnli, spaCy en_core_web_sm"],
    ["4", "LLM (cross-check)", "gpt-oss-20b, run locally with Ollama; optionally the same model through the Groq API"],
    ["5", "Knowledge and data sources", "Wikidata (SPARQL and entity API), World Bank API, WHO GHO API, Google Fact Check Tools API, Wikipedia"],
    ["6", "Vector search / retrieval", "FAISS"],
    ["7", "Language processing", "spaCy, Indic NLP Library"],
    ["8", "Back end and database", "FastAPI, SQLite"],
    ["9", "Front end", "React, Vite, Tailwind CSS"],
    ["10", "Data handling", "Pandas, NumPy, scikit-learn, SciPy"],
    ["11", "Version control", "Git / GitHub"],
    ["12", "Operating system", "Windows / Linux"],
    ["13", "Development environment", "VS Code"],
  ], [900, 2700, 4562], [0]),
  gap(),
  h("Hardware Requirements:"),
  table([
    ["Sr. No.", "Component", "Specification"],
    ["1", "Processor", "64-bit processor; Intel Core i5-13450HX used for development"],
    ["2", "RAM", "About 4 GB for the server without the LLM (measured: 2.3 GB after loading, 2.9 GB at peak); 16 GB or more when the LLM runs locally (the model is 13 GB); 24 GB used for development"],
    ["3", "GPU", "Optional: NVIDIA GPU with CUDA (RTX 4050 Laptop GPU, 6 GB, used); without a GPU a 6-claim answer took 13.7 s instead of 5.1 s without the LLM"],
    ["4", "Storage", "Models 1.6 GB and evidence index 0.45 GB (measured), plus 13 GB for the local LLM and the Python libraries; about 25 GB of free space recommended"],
    ["5", "Internet connectivity", "Stable connection for live Wikipedia, Wikidata, statistics and fact-check look-ups"],
  ], [900, 2400, 4862], [0]),
  gap(),

  H("VIII. Future Work:"),
  ...list("bullets", [
    "Raising the catches of the LLM cross-check further, to the doubling we aimed for, without adding false alarms.",
    "A faster deployment of the cross-check, for example a hosted service for the same open model.",
    "Adding Marathi, using Indic resources such as MuRIL, IndicSBERT and IndicXNLI.",
    "A larger multi-domain Hindi evaluation set labelled blind by two people.",
    "More official data sources, such as Indian government open-data portals."]),
];

// ---------- references and signatures (built after the body so the numbering is final) ----------
const refsBlock = () => [
  H("References:"),
  ...ORDER.map((k, i) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { line: 300, after: 100 }, indent: { left: 640, hanging: 640 },
    children: [new TextRun({ text: `[${i + 1}]`, font: F, size: 24 }),
      new TextRun({ font: F, size: 24, children: [new PositionalTab({ alignment: PositionalTabAlignment.LEFT, relativeTo: PositionalTabRelativeTo.INDENT, leader: PositionalTabLeader.NONE })] }),
      new TextRun({ text: REFS[k], font: F, size: 24 })] })),
];
const signBlock = () => [
  new Paragraph({ pageBreakBefore: true, spacing: { before: 600, after: 300 }, children: [r("Students Name", { bold: true }), new TextRun({ font: F, size: 24, bold: true, children: [tab(PositionalTabAlignment.RIGHT), "Signature"] })] }),
  ...["1. Vivek Yeshwantrao Borkar", "2. Piyush Devidas Nande", "3. Aasawari Sahebrao Jumade", "4. Arunima Tridip Wankhade"].map(n =>
    new Paragraph({ spacing: { after: 360 }, children: [r(n), new TextRun({ font: F, size: 24, children: [tab(PositionalTabAlignment.RIGHT), "____________________"] })] })),
  new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: 700 }, children: [r("Signature")] }),
  new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: 300 }, children: [r("Dr. R. R. Karwa", { bold: true })] }),
  new Paragraph({ alignment: AlignmentType.RIGHT, children: [r("Project Guide")] }),
];

const pageSize = { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 2304, right: 1440, footer: 600 } };
const footer = new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ font: F, size: 20, children: [PageNumber.CURRENT] })] })] });
const doc = new Document({
  styles: { default: { document: { run: { font: F, size: 24 } } } },
  numbering: { config: [
    { reference: "roman", levels: [{ level: 0, format: LevelFormat.LOWER_ROMAN, text: "%1)", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 600, hanging: 460 } } } }] },
    { reference: "modules", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
  ] },
  sections: [
    { properties: { page: pageSize }, children: titlePage },
    { properties: { page: pageSize }, footers: { default: footer }, children: [...body, ...refsBlock(), ...signBlock()] },
  ],
});
fs.writeFileSync(path.join(HERE, "ref_order.json"), JSON.stringify(ORDER));
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT, "| references cited:", ORDER.length, "| defined:", Object.keys(REFS).length,
  "| unused:", Object.keys(REFS).filter(k => !ORDER.includes(k)).join(",") || "none"); });
