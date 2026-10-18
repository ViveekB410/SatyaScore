// Satya-Score B.Tech project report in the official PRMIT&R Dept. AI&DS 2026-27 format
// ("college report format" folder: UG_Project_Report_Format-26-27, Table of Content, Guideline 2026-2027,
// One Page Resume Format, Chapter 1 Template, Final Format guidelines PDF).
// A4; margins L 1.6", R/T/B 1.0"; header-right title; footer: line, "PRMIT&R // Dept. AI&DS // 2026-27" left,
// "Page n" right (Arial 10); TNR 12, 1.5 spacing, justified, 0.5" first-line indent, 6 pt before / 0 after;
// chapter TNR 14 bold uppercase centred; sections TNR 12 bold UPPERCASE; subsections TNR 12 bold sentence case;
// captions TNR 11 bold centred (Table X.Y above, Fig. X.Y below); front pages bordered, roman numbers;
// every chapter starts on a right-hand page.
// Usage: node college_report_v3.js <out.docx>   (reads pages_v3.json for page numbers, writes keys_v3.json)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType, WidthType, BorderStyle,
  Header, Footer, ShadingType, VerticalAlign, ImageRun, PageNumber, NumberFormat, LevelFormat, SectionType,
  PositionalTab, PositionalTabAlignment, PositionalTabRelativeTo, PositionalTabLeader, TableLayoutType,
} = require("docx");

const OUT = process.argv[2];
const HERE = __dirname;
const PAGES_FILE = path.join(HERE, "pages_v3.json");
const PAGES = fs.existsSync(PAGES_FILE) ? JSON.parse(fs.readFileSync(PAGES_FILE, "utf8").replace(/^\uFEFF/, "")) : {};
const KEYS = [];                      // {key, mode}: text Word searches to find each page number
const key = (k, mode = "first") => { if (!KEYS.some(x => x.key === k)) KEYS.push({ key: k, mode }); return k; };
const B = JSON.parse(fs.readFileSync("C:\\Users\\vivek\\Downloads\\satyascore\\results\\public_benchmarks_summary.json", "utf8"));
const pc = (x) => `${Math.round(x.p * 100)}%`; const kn = (x) => `${x.k} of ${x.n}`; const f3 = (v) => v.toFixed(3);
const F = "Times New Roman", MONO = "Consolas", SCRIPT = "Monotype Corsiva", SCHOOL = "Century Schoolbook";
const TITLE = "Satya-Score: An AI Hallucination Detection & Scoring Framework";
const AUTHORS = ["Vivek Yeshwantrao Borkar", "Piyush Devidas Nande", "Aasawari Sahebrao Jumade", "Arunima Tridip Wankhade"];
const GUIDE = "Dr. R. R. Karwa";
const HOD = "Dr. S. R. Gupta";
const TW = 8162; // A4 11906 - left 1.6" (2304) - right 1" (1440)
const MAROON = "943634", FOOTLINE = "622423";

// ---------- references ----------
const src = fs.readFileSync(path.join(HERE, "synopsis_updated.js"), "utf8");
const REFS = Function(`return ${src.match(/const REFS = (\{[\s\S]*?\n\});/)[1]}`)();
Object.assign(REFS, {
  safe: "J. Wei et al., “Long-form factuality in large language models,” arXiv:2403.18802, 2024, doi: 10.48550/arXiv.2403.18802.",
  sbert: "N. Reimers and I. Gurevych, “Sentence-BERT: Sentence embeddings using Siamese BERT-networks,” in Proc. EMNLP-IJCNLP, 2019, doi: 10.18653/v1/D19-1410.",
  alignscore: "Y. Zha, Y. Yang, R. Li, and Z. Hu, “AlignScore: Evaluating factual consistency with a unified alignment function,” in Proc. ACL, 2023, doi: 10.18653/v1/2023.acl-long.634.",
  ji: "Z. Ji et al., “Survey of hallucination in natural language generation,” ACM Comput. Surv., vol. 55, no. 12, 2023, doi: 10.1145/3571730.",
  gpt4: "OpenAI et al., “GPT-4 technical report,” arXiv:2303.08774, 2023, doi: 10.48550/arXiv.2303.08774.",
  pytorch: "A. Paszke et al., “PyTorch: An imperative style, high-performance deep learning library,” in Proc. NeurIPS, 2019, arXiv:1912.01703.",
  transformers: "T. Wolf et al., “Transformers: State-of-the-art natural language processing,” in Proc. EMNLP: System Demonstrations, 2020, doi: 10.18653/v1/2020.emnlp-demos.6.",
});
const ORDER = [];
const cite = (s) => s.replace(/\{([a-z0-9,]+)\}/g, (_, keys) => keys.split(",").map(k => {
  if (!REFS[k]) throw new Error("unknown reference " + k);
  if (!ORDER.includes(k)) ORDER.push(k);
  return `[${ORDER.indexOf(k) + 1}]`;
}).join(", "));

// ---------- body helpers (Chapter Template) ----------
const r = (t, o = {}) => new TextRun({ text: cite(t), font: o.font || (o.mono ? MONO : F), size: o.size || 24, bold: o.bold, italics: o.italics });
const runs = (parts, o = {}) => (Array.isArray(parts) ? parts : [parts]).map(x => typeof x === "string" ? r(x, o) : x);
// paragraph: justified, 1.5 lines, 6 pt before, 0 after, 0.5" first-line indent
const p = (parts, o = {}) => new Paragraph({ alignment: o.align || AlignmentType.JUSTIFIED,
  spacing: { line: 360, before: o.before ?? 120, after: o.after ?? 0 }, indent: o.noIndent || o.align ? undefined : { firstLine: 720 },
  keepNext: o.keepNext, children: runs(parts) });
const chapter = (no, title) => [
  { __chapter: no, title },
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, line: 360 }, keepNext: true,
    children: [r(key(`CHAPTER ${no}`), { bold: true, size: 28 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 360, line: 360 }, keepNext: true,
    children: [r(title.toUpperCase(), { bold: true, size: 28 })] }),
];
// section x.y: TNR 12 bold UPPERCASE; starts 1.5 lines below the previous section
const h = (t) => { const m = t.match(/^(\d+\.\d+)\s+(.*)$/); const text = m ? `${m[1]} ${m[2].toUpperCase()}` : t.toUpperCase();
  return new Paragraph({ keepNext: true, spacing: { before: 360, after: 60, line: 360 }, children: [r(key(text), { bold: true })] }); };
// subsection x.y.z: TNR 12 bold, sentence case
const h3 = (t) => new Paragraph({ keepNext: true, spacing: { before: 240, after: 0, line: 360 }, children: [r(t, { bold: true })] });
const list = (ref, items) => items.map((it, i) => new Paragraph({ numbering: { reference: ref, level: 0 },
  keepNext: i < items.length - 1 && items.length <= 6, alignment: AlignmentType.JUSTIFIED, spacing: { line: 360, before: 60, after: 0 }, children: runs(it) }));
const bullets = (items) => list("bullets", items);
const lb = (label, text) => [r(label, { bold: true }), r(text)];
const eq = (t) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 120, line: 300 }, children: [r(t, { italics: true })] });

// ---------- tables, figures, listings ----------
const line = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const borders = { top: line, bottom: line, left: line, right: line };
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: NONE, bottom: NONE, left: NONE, right: NONE };
function cell(text, w, o = {}) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA }, borders: o.borders || borders, verticalAlign: VerticalAlign.CENTER, columnSpan: o.span, rowSpan: o.rowSpan,
    shading: o.head ? { fill: "D9D9D9", type: ShadingType.CLEAR, color: "auto" } : (o.fill ? { fill: o.fill, type: ShadingType.CLEAR, color: "auto" } : undefined),
    margins: { top: o.tight ? 25 : 45, bottom: o.tight ? 25 : 45, left: 90, right: 90 },
    children: (Array.isArray(text) ? text : [text]).map(t => new Paragraph({ alignment: o.align || AlignmentType.LEFT, spacing: { line: o.line || 264 },
      indent: o.indent ? { left: o.indent } : undefined, children: [r(t, { bold: o.bold || o.head, italics: o.italics, size: o.size || 21, font: o.font })] })),
  });
}
const table = (rows, widths, o = {}) => new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: widths,
  rows: rows.map((cells, i) => new TableRow({ tableHeader: i === 0, cantSplit: true,
    children: cells.map((c, j) => cell(c, widths[j], { head: i === 0, align: i === 0 || (o.center || []).includes(j) ? AlignmentType.CENTER : AlignmentType.LEFT })) })) });
const CAPS = { table: [], figure: [], shot: [] };
const capPara = (text, before, after, keepNext) => new Paragraph({ alignment: AlignmentType.CENTER, keepNext,
  spacing: { before, after }, children: [r(text, { bold: true, size: 22 })] });
// Table X.Y above the table; Fig. X.Y / Screenshot X.Y / Listing X.Y below or above as in the text
const tcap = (k, rest) => { const no = k.replace(/^Table\s+|:$/g, ""); const text = `Table ${no} ${rest}`;
  CAPS.table.push({ no, title: rest, key: key(text) }); return capPara(text, 200, 100, true); };
const fcap = (k, rest) => { const shot = k.startsWith("Screenshot"); const no = k.replace(/^(Fig\.|Screenshot)\s+|:$/g, "");
  const text = `${shot ? "Screenshot" : "Fig."} ${no} ${rest}`;
  (shot ? CAPS.shot : CAPS.figure).push({ no, title: rest, key: key(text) }); return capPara(text, 60, 220, false); };
const lcap = (k, rest) => { const no = k.replace(/^Listing\s+|:$/g, ""); const text = `Listing ${no} ${rest}`;
  CAPS.figure.push({ no: `Listing ${no}`, title: rest, key: key(text) }); return capPara(text, 200, 100, true); };
const gap = () => new Paragraph({ spacing: { after: 120 }, children: [] });
const imgSize = (buf, type) => {
  if (type === "png") return [buf.readUInt32BE(16), buf.readUInt32BE(20)];
  let i = 2; while (i < buf.length) { const m = buf[i + 1], len = buf.readUInt16BE(i + 2);
    if (m === 0xC0 || m === 0xC2) return [buf.readUInt16BE(i + 7), buf.readUInt16BE(i + 5)]; i += 2 + len; }
  throw new Error("jpeg size");
};
function image(file, widthPx, type = "png", o = {}) {
  const buf = fs.readFileSync(path.join(HERE, file)); const [w, hh] = imgSize(buf, type);
  return new Paragraph({ alignment: AlignmentType.CENTER, keepNext: o.keepNext ?? true, spacing: { before: o.before ?? 120, after: o.after ?? 40 },
    children: [new ImageRun({ type, data: buf, transformation: { width: widthPx, height: Math.round(widthPx * hh / w) } })] });
}
const png = (file, widthPx) => image(file, widthPx);
function framed(file, widthPx) {
  const buf = fs.readFileSync(path.join(HERE, file)); const [w, hh] = imgSize(buf, "png");
  const img = new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, children: [
    new ImageRun({ type: "png", data: buf, transformation: { width: widthPx, height: Math.round(widthPx * hh / w) } })] });
  return new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: [TW], rows: [new TableRow({ cantSplit: true, children: [
    new TableCell({ width: { size: TW, type: WidthType.DXA }, borders, margins: { top: 40, bottom: 40, left: 40, right: 40 }, children: [img] })] })] });
}
function code(lines) {
  return new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: [TW], rows: [new TableRow({ cantSplit: true, children: [
    new TableCell({ width: { size: TW, type: WidthType.DXA }, borders, shading: { fill: "F2F2F2", type: ShadingType.CLEAR, color: "auto" },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: lines.map(l => new Paragraph({ spacing: { line: 240, after: 0 }, children: [new TextRun({ text: l || " ", font: MONO, size: 16 })] })) })] })] });
}

// ---------- page furniture ----------
const pageBorders = { pageBorderTop: { style: BorderStyle.THIN_THICK_SMALL_GAP, size: 24, color: MAROON, space: 3 },
  pageBorderLeft: { style: BorderStyle.THIN_THICK_SMALL_GAP, size: 24, color: MAROON, space: 6 },
  pageBorderBottom: { style: BorderStyle.THICK_THIN_SMALL_GAP, size: 24, color: MAROON, space: 3 },
  pageBorderRight: { style: BorderStyle.THICK_THIN_SMALL_GAP, size: 24, color: MAROON, space: 8 },
  pageBorders: { display: "allPages", offsetFrom: "text" } };
const pageSize = { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 2304, right: 1440, header: 600, footer: 600 } };
const ptab = (alignment) => new PositionalTab({ alignment, relativeTo: PositionalTabRelativeTo.MARGIN, leader: PositionalTabLeader.NONE });
const header = new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: TITLE, font: F, size: 20, italics: true })] })] });
const bodyFooter = new Footer({ children: [new Paragraph({
  border: { top: { style: BorderStyle.THIN_THICK_SMALL_GAP, size: 24, color: FOOTLINE, space: 1 } },
  children: [new TextRun({ text: "PRMIT&R // Dept. AI&DS // 2026-27", font: "Arial", size: 20 }),
    new TextRun({ font: "Arial", size: 20, children: [ptab(PositionalTabAlignment.RIGHT), "Page ", PageNumber.CURRENT] })] })] });
const romanFooter = new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ font: F, size: 22, children: [PageNumber.CURRENT] })] })] });

// ---------- front pages (UG_Project_Report_Format-26-27 AI and DS) ----------
const c = (t, o = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: o.after ?? 60, before: o.before || 0 },
  children: (Array.isArray(t) ? t : [t]).map(x => typeof x === "string" ? new TextRun({ text: x, font: o.font || F, size: o.size || 24, bold: o.bold, italics: o.italics }) : x) });
const tr = (t, o = {}) => new TextRun({ text: t, font: o.font || F, size: o.size || 24, bold: o.bold, italics: o.italics });
const titlePage = [
  c("Project Report", { font: SCRIPT, size: 40, bold: true, italics: true, after: 40 }),
  c("On", { size: 32, bold: true, after: 40 }),
  c(TITLE.toUpperCase(), { size: 32, bold: true, after: 440 }),
  c("Submitted to", { size: 28, bold: true, italics: true, after: 20 }),
  c("Prof. Ram Meghe Institute of Technology and Research,", { size: 28, bold: true, after: 20 }),
  c("(An Autonomous Institute)", { size: 28, bold: true, italics: true, after: 20 }),
  c("Affiliated to Sant Gadge Baba Amravati University, Amravati", { size: 24, bold: true, italics: true, after: 200 }),
  c("for partial fulfillment of the requirement for the degree of", { size: 28, bold: true, after: 60 }),
  c("BACHELOR OF TECHNOLOGY", { font: SCRIPT, size: 36, bold: true, italics: true, after: 40 }),
  c("in", { size: 32, bold: true, after: 40 }),
  c("Artificial Intelligence and Data Science", { size: 32, bold: true, after: 260 }),
  c("Submitted By", { size: 28, bold: true, italics: true, after: 140 }),
  ...AUTHORS.map((a, i) => c(a, { size: 28, bold: true, after: i === AUTHORS.length - 1 ? 360 : 40 })),
  c("Under the Guidance of", { size: 28, bold: true, after: 40 }),
  c(GUIDE, { size: 32, bold: true, after: 300 }),
  image("college_logo.jpg", 170, "jpg", { before: 0, after: 300, keepNext: false }),
  c("Department of Artificial Intelligence and Data Science", { font: SCHOOL, size: 28, bold: true, after: 60 }),
  c("Prof. Ram Meghe Institute of Technology & Research, Badnera - Amravati", { font: SCHOOL, size: 34, bold: true, after: 260 }),
  c("2026-2027", { font: SCHOOL, size: 34, bold: true, after: 0 }),
];
const certHeader = new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: [1500, 6662], rows: [new TableRow({ children: [
  new TableCell({ width: { size: 1500, type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
    borders: { top: NONE, left: NONE, right: NONE, bottom: { style: BorderStyle.SINGLE, size: 18, color: MAROON } },
    children: [image("college_logo.jpg", 85, "jpg", { before: 0, after: 60, keepNext: false })] }),
  new TableCell({ width: { size: 6662, type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
    borders: { top: NONE, left: NONE, right: NONE, bottom: { style: BorderStyle.SINGLE, size: 18, color: MAROON } },
    children: [c("Department of Artificial Intelligence and Data Science", { font: SCHOOL, size: 23, bold: true, after: 20 }),
      c("Prof. Ram Meghe Institute of Technology & Research, Badnera - Amravati", { font: SCHOOL, size: 26, bold: true, after: 20 }),
      c("(An Autonomous Institute)", { font: SCHOOL, size: 22, bold: true, italics: true, after: 20 }),
      c("2026 - 2027", { font: SCHOOL, size: 26, bold: true, after: 60 })] })] })] });
const sigCell = (name, role, w) => new TableCell({ width: { size: w, type: WidthType.DXA }, borders: noBorders, children: [
  c(name, { font: SCRIPT, size: 32, bold: true, italics: true, after: 0 }),
  ...[role, "Department of AI & DS", "Prof. Ram Meghe Institute of Technology &", "Research, Badnera - Amravati"].map(t => c(t, { font: SCRIPT, size: 24, after: 0 }))] });
const certificatePage = [
  certHeader,
  c("CERTIFICATE", { size: 36, before: 360, after: 120 }),
  c([tr("This is to certify that the ", { font: SCRIPT, size: 28, italics: true }), tr("Project (7SA08)", { font: SCRIPT, size: 28, bold: true, italics: true }),
    tr(" entitled", { font: SCRIPT, size: 28, italics: true })], { after: 160 }),
  c(TITLE, { size: 30, bold: true, after: 160 }),
  c([tr("is a bonafide work and it is submitted to the Prof. Ram Meghe Institute of Technology and Research (An Autonomous Institute), affiliated to ", { font: SCRIPT, size: 28, italics: true })], { after: 20 }),
  c("Sant Gadge Baba Amravati University, Amravati", { font: SCRIPT, size: 28, bold: true, italics: true, after: 60 }),
  c("By", { font: SCRIPT, size: 28, italics: true, after: 60 }),
  ...AUTHORS.map((a, i) => c(a, { size: 28, bold: true, after: i === AUTHORS.length - 1 ? 200 : 20 })),
  c([tr("in the partial fulfillment of the requirement for the degree of ", { font: SCRIPT, size: 28, italics: true })], { after: 20 }),
  c([tr("Bachelor of Technology", { font: SCRIPT, size: 28, bold: true, italics: true }), tr(" in ", { font: SCRIPT, size: 28, italics: true }),
    tr("Artificial Intelligence and Data Science", { font: SCRIPT, size: 28, bold: true, italics: true }), tr(",", { font: SCRIPT, size: 28, italics: true })], { after: 20 }),
  c([tr("during the academic year ", { font: SCRIPT, size: 28, italics: true }), tr("2026-2027", { font: SCRIPT, size: 28, bold: true, italics: true }),
    tr(" under my guidance.", { font: SCRIPT, size: 28, italics: true })], { after: 1100 }),
  new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: [4081, 4081], rows: [new TableRow({ children: [sigCell(GUIDE, "Guide", 4081), sigCell(HOD, "Head,", 4081)] })] }),
  c("External Examiner", { font: SCRIPT, size: 24, before: 900, after: 300 }),
  c("______________________", { font: SCRIPT, size: 24, after: 0 }),
];
const ackP = (t) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { line: 312, after: 140 }, children: runs(t) });
const acknowledgementPage = [
  new Paragraph({ alignment: AlignmentType.CENTER, pageBreakBefore: true, spacing: { after: 300 }, children: [tr("ACKNOWLEDGEMENT", { size: 28, bold: true })] }),
  ackP("With immense pleasure and deep gratitude, we would like to express our sincere thanks to all those who have supported and guided us throughout the completion of this project. This work stands as a testament to the inspiration, motivation, and technical assistance provided by many individuals. Without their continuous support and encouragement, this project would not have been possible."),
  ackP(["We are profoundly grateful to our respected guide, ", r(GUIDE, { bold: true }), ", for valuable guidance, constant supervision, constructive suggestions, and for providing the necessary resources required for the successful completion of this project. The patience, encouragement, and insightful feedback we received greatly contributed to the quality of our work."]),
  ackP(["We would also like to extend our sincere appreciation to ", r(HOD, { bold: true }), ", Head of the Department of Artificial Intelligence and Data Science, for providing us with the opportunity and encouragement to undertake this project. We are equally thankful to all the faculty members of the Department of Artificial Intelligence and Data Science for their kind cooperation, continuous encouragement, and academic support."]),
  ackP("We owe a special note of gratitude to the staff members of the Department of Artificial Intelligence and Data Science for their direct and indirect assistance throughout this project."),
  ackP("We also express our heartfelt thanks to our colleagues for their collaboration, teamwork, and valuable contributions in developing this project. Their support and cooperation played a significant role in its successful completion. We are also thankful to the authors whose research work we referred to and used in this project, and to the people who maintain the open resources it relies on: Wikipedia, Wikidata, World Bank Open Data, the WHO Global Health Observatory and the published fact-checks."),
  ackP("Finally, we extend our deepest gratitude to our parents, friends, and well-wishers for their constant encouragement, moral support, and understanding. Above all, we thank the Almighty God for guiding us and blessing us with the strength and wisdom to accomplish this work."),
  new Paragraph({ spacing: { before: 400 }, children: [] }),
  ...AUTHORS.map((a, i) => new Paragraph({ indent: { left: 4600 }, spacing: { after: 40 }, children: [tr(`${i + 1}. ${a}`)] })),
];
const ABSTRACT = [
  "Chatbots based on large language models (LLMs) write fluent answers that sometimes contain false statements, and readers cannot easily tell which sentence is wrong; for Hindi, checking tools are scarce. Satya-Score is a framework that detects and scores such hallucinations in English and Hindi text one claim at a time. A claim that official statistics (World Bank, WHO) or the Wikidata knowledge graph can settle is decided by that source, with the correct value shown; otherwise a matching published fact-check is used. For the remaining claims, Version 2 adds an LLM cross-check: a multilingual inference model reads retrieved Wikipedia passages, an open-weight LLM (gpt-oss-20b, run on the project laptop) judges the claim, and the LLM’s verdict counts only when the passage evidence agrees. Each claim receives a verdict (Verified, Uncertain or Hallucinated), a score, its evidence and the wrong words marked, in a secure web application.",
  "Every change was tested against criteria fixed in advance. Structured sources caught all 137 altered country statistics without contradicting a true figure, and a pre-registered ablation showed the knowledge graph raising AUC from 0.704 to 0.784. On a held-out sample of 620 English and Hindi items from FEVER, Mu-SHROOM, TruthfulQA, X-FACT and Hindi Wikipedia, evaluated once, the cross-check caught 47% of false items against 25% without it, passed only 6% of them as Verified against 22%, and raised false alarms on 13% of true items against 11%. The LLM alone caught 86% but flagged 28% of true items. The cross-check met three of the four acceptance criteria, narrowly missing a doubling of catches, and its gains were largest in Hindi.",
];
const frontTitle = (t, mode, first = false) => new Paragraph({ alignment: AlignmentType.CENTER, pageBreakBefore: !first, spacing: { after: 360 },
  children: [tr(mode ? key(t, mode) : t, { size: 32, bold: true })] });
const abstractPage = [frontTitle("ABSTRACT", null, true), ...ABSTRACT.map(t => new Paragraph({ alignment: AlignmentType.JUSTIFIED,
  spacing: { line: 360, after: 160 }, indent: { firstLine: 720 }, children: [tr(t)] }))];

// ===================== chapters =====================
const body = [
  // ===================== CHAPTER 1 =====================
  ...chapter(1, "Introduction"),
  h("1.1 Overview"),
  p("Chatbots built on large language models (LLMs), for example GPT-4 {gpt4} and Llama {llama3}, now answer everyday questions on health, public services, science and history. They produce text by repeatedly choosing a likely next word; they do not consult a record of facts while writing. As a result, an answer can be grammatical, confident and still contain statements that are invented or wrong. Such output is usually called hallucination {ji,huang}. Studies of long model-written answers have found that a noticeable share of their individual facts is not supported by any reliable source {factscore}."),
  p("Satya-Score (“satya” means truth) is a framework for finding these errors. It breaks an answer into individual factual claims, checks each claim against the most authoritative source available, and reports for every claim a verdict, a score and the evidence behind it. Version 2 of the system adds an open-weight LLM as a second reader whose verdict counts only when the retrieved evidence agrees with it."),
  h("1.2 Motivation"),
  p("A wrong date, name or figure inside a long and otherwise correct answer is easy to miss, and checking every sentence by hand removes the benefit of using an assistant. Automatic checkers exist, but most work only for English, give a single score for a whole passage, or depend on another large model whose own judgement may be wrong. Hindi is spoken by hundreds of millions of people and appears more and more in chatbot output, yet a Hindi reader has almost no tool that points to the false statement in an answer and explains why it is false. This gap motivated the project."),
  h("1.3 Problem Definition"),
  p("Given an answer produced by an LLM in English or Hindi, identify its factual claims; decide for each claim whether reliable sources support it, contradict it or cannot settle it; show the evidence and, where a structured source holds it, the correct fact; and do this quickly enough to be useful while reading, without marking true statements as false."),
  h("1.4 Project Goal and Objectives"),
  p("The goal of the project is a bilingual, explainable checker that tells a reader which statements of an AI answer are true, false or unsettled, and why. The objectives are:"),
  ...list("objectives", [
    "To analyse hallucination in LLM answers.",
    "To compare existing hallucination-detection methods.",
    "To design a claim-level detection framework for English and Hindi.",
    "To integrate an LLM with retrieved evidence so that neither decides alone.",
    "To develop a secure web application that explains each verdict.",
    "To evaluate the system on public benchmarks with pre-set criteria.",
  ]),
  h3("1.4.1 Scope of the project"),
  ...bullets([
    lb("Languages: ", "English and Hindi text, typed, pasted or uploaded as a .txt or .pdf file."),
    lb("Claims: ", "statements of fact. Questions, greetings, advice and opinions are recognised and not checked."),
    lb("Sources: ", "English and Hindi Wikipedia, Wikidata, World Bank Open Data, the WHO Global Health Observatory and published fact-checks found through the Google Fact Check Tools API; in Version 2, also an open-weight LLM (gpt-oss-20b) whose verdict counts only with the evidence."),
    lb("Output: ", "a verdict, score and explanation for every claim with the wrong words marked, an overall verdict for the text, and a history of checks for signed-in users."),
    lb("Outside the scope: ", "other languages, images and audio, correcting the chatbot itself, and commercial use (the WHO data licence allows non-commercial use only)."),
  ]),
  h("1.5 Contribution"),
  p("To our knowledge, Satya-Score is the first claim-level checker that combines official statistics, a knowledge graph, published fact-checks and an LLM for English and Hindi, in which the LLM can never decide a claim alone. The project contributes:"),
  ...list("contrib", [
    [r("An agreement-gated LLM cross-check: ", { bold: true }), r("a claim is Verified only when the passage evidence and the LLM agree, and Hallucinated only when the LLM names a wrong fact that a second, passages-only reading does not find stated. Used alone, the same LLM raised false alarms on 28% of true items; under this rule, 13% (Section 5.8).")],
    [r("Source routing with the correct value: ", { bold: true }), r("each claim is answered by the most trustworthy source that covers it (statistics, knowledge graph, fact-check, text), and a structured source also gives the correct value.")],
    [r("Marking of the wrong words ", { bold: true }), r("in the text, instead of flagging whole sentences.")],
    [r("An evaluation with criteria fixed in advance ", { bold: true }), r("on public English and Hindi benchmarks and Hindi sets built for this study, in which every held-out sample was used once and failures are reported.")],
    [r("An open, local system: ", { bold: true }), r("all models are open and run on a student laptop with a 6 GB GPU, together with a secure web application.")],
  ]),
  h("1.6 Organization of Report"),
  p("Chapter 2 reviews related work and identifies the research gap. Chapter 3 analyses the existing approaches and the requirements and presents the overall architecture. Chapter 4 gives the design: block diagram, data flow diagrams, modules, algorithms, database and flowchart. Chapter 5 describes the implementation and reports the results of both versions, including the changes that were tested and rejected and the limitations. Chapter 6 concludes and outlines the future scope of the work."),

  // ===================== CHAPTER 2 =====================
  ...chapter(2, "Literature Review"),
  h("2.1 Fact Verification and Claim Checking"),
  p("Automatic fact verification became a standard task with FEVER {fever}, in which a system receives a claim, finds evidence in Wikipedia and labels the claim as supported, refuted or lacking enough information. Later work asked whether a generated text is consistent with a given source. The TRUE study {true} compared many such consistency metrics on a common footing, and AlignScore {alignscore} trained a single alignment function over many tasks for the same purpose. These methods assume that the right evidence is already available; finding it is a separate problem."),
  h("2.2 Hallucination Detection in LLM Output"),
  p("Benchmarks such as TruthfulQA {truthfulqa} and HaluEval {halueval} measure how often models produce false or unsupported statements. FActScore {factscore} splits a generated biography into atomic facts and checks each against Wikipedia, and SAFE {safe} uses an LLM agent that searches the web for every fact. Both show that checking individual facts is more informative than scoring a whole answer, but both are built for English and rely on large models for splitting or judging. SelfCheckGPT {selfcheck} needs no external source: it samples several answers and treats disagreement between them as a warning, which cannot catch an error the model repeats consistently. Other work operates at a finer grain: RefChecker {refchecker} checks claim triplets against a reference, ANAH {anah} supplies sentence-level analytical annotations for training hallucination annotators, FAVA {fava} detects and edits erroneous spans, and MIND {mind} uses a model’s internal states. A known weakness of inference models is that they can rely on word overlap rather than meaning {mccoy}; this weakness reappears in the error analysis of Chapter 5. Strong LLMs are also widely used as judges, and they agree with human preferences in many tasks {judge}; a judge, however, shares the blind spots of its own model family, and when used to check facts it can treat missing evidence as proof of falsehood. Version 2 of Satya-Score therefore lets an LLM count only together with retrieved evidence."),
  h("2.3 Grounding Checkers"),
  p("A grounding checker decides whether a sentence is supported by a supplied document. MiniCheck {minicheck} reaches accuracy close to GPT-4 on this task at a much smaller size and cost, and AlignScore {alignscore} was the strongest small checker before it. Retrieval-augmented generation {rag} takes a related route, giving the model retrieved documents while it writes; it can reduce errors in a system one controls, but it cannot audit text that a third-party chatbot has already produced."),
  h("2.4 Multilingual and Hindi Fact-Checking"),
  p("X-FACT {xfact} collected short statements in 25 languages, Hindi among them, labelled by professional fact-checkers, and showed that multilingual fact-checking remains hard. The SemEval-2025 Mu-SHROOM shared task {mushroom} posed span-level hallucination detection in 14 languages, Hindi among them. Participating systems used, for example, an ensemble of LLMs that vote on candidate spans {msa}, natural-language inference with a model fine-tuned on synthetic data {hausa}, and semantic-role decomposition with retrieved context {detectives}; none of these three uses a knowledge graph. SHROOM-CAP {shroomcap} extended the task to scientific publications in nine languages, and BHRAM-IL {bhramil} provides a benchmark that measures hallucination in Hindi, Gujarati, Marathi and Odia as well as English. Multilingual encoders such as XLM-R {xlmr} and MuRIL {muril}, the IndicNLPSuite resources {indicsuite}, IndicSBERT {indicsbert} and IndicXNLI {indicxnli} supply building blocks for Indian languages, while inference models are commonly trained on MultiNLI {mnli} and its cross-lingual extension XNLI {xnli}."),
  h("2.5 Knowledge Graphs and Cross-Lingual Retrieval"),
  p("A knowledge graph stores facts as explicit relations between entities. Wikidata {wikidata} is open, multilingual and edited collaboratively. FactKG {factkg} verifies claims by reasoning over graph paths, and KGR {kgr} uses a graph to retrofit and correct a model’s draft answer. MultiHal {multihal} is a multilingual benchmark that pairs questions with knowledge-graph paths in several European languages and reports that answers grounded in those paths score better on similarity and inference measures. Two recent surveys conclude that the benefit of knowledge graphs against hallucination is promising but not yet settled {agrawal,lavrinovics}. For retrieval, sentence encoders such as Sentence-BERT {sbert} and its multilingual distillation {sbertml} map text into vectors that can be searched quickly with FAISS {faiss}; DeBERTaV3 {debertav3} is a strong encoder family on which multilingual inference models are built."),
  h("2.6 Summary of the Literature"),
  p("Table 2.1 summarises representative systems along the properties that matter for this project."),
  tcap("Table 2.1:", "Comparison of existing systems"),
  table([
    ["System", "Unit checked", "Hindi", "Evidence used", "Gives correct fact"],
    ["FActScore {factscore}", "Atomic facts", "No", "Wikipedia passages", "No"],
    ["SAFE {safe}", "Atomic facts", "No", "Web search through an LLM agent", "No"],
    ["SelfCheckGPT {selfcheck}", "Sentences", "No", "None (agreement among sampled answers)", "No"],
    ["MiniCheck {minicheck}", "Sentences", "No", "A supplied document", "No"],
    ["Mu-SHROOM systems {msa,hausa,detectives}", "Text spans", "Yes", "LLMs, inference models or retrieved context; no knowledge graph", "No"],
    ["MultiHal {multihal}", "Benchmark (question answering)", "No", "Knowledge-graph paths", "Not applicable"],
    ["BHRAM-IL {bhramil}", "Benchmark", "Yes", "Not applicable", "Not applicable"],
    ["Satya-Score (this work)", "Claims", "Yes", "Official statistics, Wikidata, published fact-checks, Wikipedia; an LLM that counts only with the evidence", "Yes, when statistics or Wikidata decide; wrong words marked"],
  ], [1900, 1250, 700, 2712, 1600], { center: [2] }),
  gap(),
  h("2.7 Research Gap"),
  p("Claim-level checking, Hindi coverage and knowledge-graph grounding have each been studied, but in separate lines of work. The multilingual detectors reviewed here do not use structured sources, and the graph-grounded work does not cover Hindi. None of the reviewed systems routes each claim to official statistics, a knowledge graph or a published fact-check before falling back on text, states the correct fact when it finds an error, and does this for Hindi. LLM judges catch more errors than inference models but raise many false alarms when used alone. Satya-Score addresses this combination and, in Version 2, uses an LLM as one of two readers that must agree. Its components are existing public models and data sources; the contribution lies in how they are combined, in the safeguards placed on each source and on the LLM, and in an evaluation that reports failures as well as successes."),

  // ===================== CHAPTER 3 =====================
  ...chapter(3, "System Architecture / Analysis"),
  h("3.1 Existing System and its Limitations"),
  p("Today a reader who doubts a chatbot answer has three options: check each statement by hand, look for an article by a professional fact-checking organisation, or use one of the research tools reviewed in Chapter 2. Each has limits:"),
  ...bullets([
    "Manual checking is slow and is rarely done for every sentence.",
    "Professional fact-checks cover popular rumours, not the particular facts in a particular answer.",
    "Most research tools handle English only, return one score for a whole text, or ask another LLM for the verdict, which can itself be wrong.",
    "Few tools explain a verdict with a source the reader can open, and fewer still state what the correct fact is.",
  ]),
  h("3.2 Proposed System"),
  p("Satya-Score checks each claim separately and sends it to the strongest source able to settle it. Official statistics and the Wikidata knowledge graph are consulted first, because they hold exact values. If neither answers, a published fact-check of the same claim is used when one exists. Otherwise, passages from English and Hindi Wikipedia are retrieved and judged by a multilingual inference model under a conservative rule that prefers “Uncertain” to a false alarm. Version 2 adds a second reader for these claims: an open-weight LLM reads the claim and the passages, and a claim is Verified only when the passages and the LLM agree, and Hallucinated only when the LLM names a wrong fact that the retrieved passages, read again, do not state. Every verdict carries its evidence, the wrong words of a flagged claim are marked, and an error decided by a structured source is shown together with the correct value."),
  h("3.3 Requirement Analysis"),
  h3("Functional requirements"),
  ...list("fr", [
    "Accept English or Hindi text, typed or pasted or uploaded as .txt or .pdf, with the language chosen by the user or detected from the script.",
    "Extract self-contained factual claims and skip questions, greetings, advice and opinions.",
    "Verify each claim against official statistics, Wikidata, published fact-checks and Wikipedia, and (Version 2) cross-check the remaining claims with an LLM.",
    "Give each claim a score and a verdict (Verified, Uncertain or Hallucinated), with its source, its evidence, the wrong words marked and, when available, the correct fact.",
    "Give the whole text an overall verdict and score.",
    "Allow users to register, sign in, keep a history of checks and export results as CSV or JSON.",
  ]),
  h3("Non-functional requirements"),
  ...bullets([
    lb("Reliability: ", "true statements should rarely be marked Hallucinated; when the evidence is weak the system should answer Uncertain."),
    lb("Performance: ", "a typical answer should be checked within seconds without the LLM, and within about half a minute with the LLM cross-check."),
    lb("Security: ", "passwords and sessions must be protected and requests from other websites refused."),
    lb("Transparency: ", "every verdict must name its source."),
    lb("Portability: ", "the system must run on a laptop, with or without a GPU."),
  ]),
  h("3.4 Hardware and Software Requirements"),
  p("Table 3.1 lists the hardware on which the system was developed and measured, and Table 3.2 the software. The memory figures were measured with the server running on the CPU."),
  tcap("Table 3.1:", "Hardware requirements"),
  table([
    ["Component", "Used for development", "Needed to run the server"],
    ["Processor", "Intel Core i5-13450HX", "A 64-bit processor (CPU-only operation works, more slowly)"],
    ["Graphics", "NVIDIA GeForce RTX 4050 Laptop GPU, 6 GB", "Optional; speeds up the models"],
    ["Memory", "24 GB RAM", "About 4 GB without the LLM (measured: 2.3 GB after loading, 2.9 GB at peak); 16 GB or more with the local LLM (13 GB model)"],
    ["Storage", "512 GB SSD", "About 2 GB for models and index; 13 GB more for the local LLM"],
    ["Network", "Internet connection", "Internet connection for the live look-ups and, optionally, the Groq and OpenRouter services"],
  ], [1600, 3000, 3562]),
  gap(),
  tcap("Table 3.2:", "Software requirements"),
  table([
    ["Purpose", "Software (version used)"],
    ["Operating system", "Windows 11 (development); Linux container image for cloud hosting"],
    ["Back end", "Python 3.13, FastAPI 0.115.6, Uvicorn 0.34.0, SQLite (Python standard library)"],
    ["Models and search", "PyTorch 2.13.0, Transformers 5.14.1, Sentence-Transformers 5.6.0, FAISS (faiss-cpu 1.14.3)"],
    ["Language processing", "spaCy 3.8.14 with en_core_web_sm, Indic NLP Library 0.92, pdfminer.six"],
    ["LLM cross-check (Version 2)", "gpt-oss-20b run with Ollama 0.40 on the laptop; optionally the same model through the Groq or OpenRouter API"],
    ["Front end", "React 18, TypeScript 5, Vite 5, Tailwind CSS 3, built with Node.js 24"],
    ["Client", "Any modern web browser"],
  ], [2300, 5862]),
  gap(),
  h("3.5 Feasibility Study"),
  ...bullets([
    lb("Technical: ", "all models are open and run on a laptop GPU or CPU, including the 21-billion-parameter LLM, which Ollama {ollama} runs partly on the 6 GB GPU and partly on the CPU; the structured sources are reached through public web interfaces."),
    lb("Economic: ", "the models, libraries and data sources are free of charge; the Google Fact Check Tools API needs only an API key, and the optional Groq service has a free tier (8,000 tokens per minute, 1,000 requests per day), with a paid tier for faster use; OpenRouter, the second cloud service, charges a small amount per reading."),
    lb("Operational: ", "users need only a web browser; results are shown in place, with links to the sources and the verdict of each reader."),
    lb("Legal: ", "the models, including gpt-oss-20b {gptoss}, are released under the MIT or Apache-2.0 licences; Wikidata is CC0, World Bank data CC BY 4.0, Wikipedia text CC BY-SA 4.0, and WHO data CC BY-NC-SA 3.0 IGO, which limits the system to non-commercial use unless the WHO source is switched off."),
  ]),
  h("3.6 Overall System Architecture"),
  p("Fig. 3.1 shows the architecture of Version 2. The React web application sends the text to the FastAPI back end, which handles accounts and sessions and stores history in SQLite. The back end extracts the claims and consults the structured sources and fact-checks for each claim; a claim that none of them decides is scored by the inference model and cross-checked by the LLM, and the scored and explained result is returned. With the cross-check switched off (Version 1), the inference score decides directly. All figures in this report were drawn by the authors."),
  png("fig1_architecture_v2.png", 430),
  fcap("Fig. 3.1:", "Overall system architecture"),

  // ===================== CHAPTER 4 =====================
  ...chapter(4, "System Design"),
  h("4.1 Block Diagram"),
  p("Fig. 4.1 shows the processing blocks of a check and, in particular, the order in which the sources decide a claim. It shows Version 1; in Version 2, step (3) of the decision block, the evidence-rule score, is replaced by the LLM cross-check of Section 4.4.7 (Fig. 4.4)."),
  png("fig_block.png", 430),
  fcap("Fig. 4.1:", "Block diagram of the pipeline"),
  h("4.2 Data Flow Diagrams"),
  p("Fig. 4.2 is the context-level (level 0) data flow diagram: answer text comes in from the user, evidence comes from four external sources, and checks are stored in the user database. Fig. 4.3 refines the system into six processes. Processes 2.0, 3.0 and 4.0 work on the claims produced by process 1.0; process 5.0 combines their results, and process 6.0 keeps accounts and history."),
  png("fig_dfd0.png", 450),
  fcap("Fig. 4.2:", "Data flow diagram, level 0"),
  png("fig_dfd1.png", 540),
  fcap("Fig. 4.3:", "Data flow diagram, level 1"),
  h("4.3 Module Design"),
  p("The code is organised in three Python packages (models, data sources, back end) and a React application. Table 4.1 lists the main modules."),
  tcap("Table 4.1:", "Main modules"),
  table([
    ["Module", "Responsibility"],
    ["member3_backend/claim_extractor.py", "Claim extraction, pronoun resolution, filtering of non-factual sentences"],
    ["member3_backend/pipeline.py", "Orchestration: retrieval, inference, structured checks, fact-checks, scoring, explanations; parallel look-ups"],
    ["member3_backend/evidence_rules.py", "Evidence rule and on-topic test"],
    ["member3_backend/factcheck_rules.py", "Direction-aware matching of published fact-checks"],
    ["member3_backend/crosscheck.py", "Version 2 agreement rule, no-evidence filter, second-reading candidates"],
    ["member1_model/llm_verifier.py", "LLM readings (Ollama, Groq and other providers), JSON parsing, answer cache, fallback between providers"],
    ["member2_data/entity_linker.py, wikidata_connector.py, kg_extra.py", "Entity linking (English and Hindi) and Wikidata checks"],
    ["member2_data/official_stats.py", "World Bank and WHO statistics with two-agency agreement"],
    ["member1_model/", "Embeddings, inference scorer, CMHSA scoring and weight training"],
    ["member3_backend/api.py, auth.py, serve.py", "Web API, accounts and security, production serving"],
    ["web/src/", "React and TypeScript web application"],
  ], [3600, 4562]),
  gap(),
  h("4.4 Algorithms"),
  h3("4.4.1 Claim extraction"),
  p("English text is parsed with spaCy {spacy}. Coordinated statements are split into separate claims and list items become claims of their own. A pronoun is replaced by the topic of the passage rather than by the nearest name; on 400 held-out Wikipedia introductions this raised the number of correctly resolved pronouns from 93 to 277 in the pre-registered test. Questions, greetings, advice and opinions are recognised and dropped. Hindi text is split into sentences with the Indic NLP Library {indicnlp}, and questions, greetings and advice are dropped."),
  h3("4.4.2 Evidence retrieval"),
  p("Claims and passages are encoded with a multilingual XLM-R sentence encoder {sbertml,xlmr} and compared in a FAISS index {faiss} built from 102,069 Wikipedia passages (89,594 English and 12,475 Hindi). When a claim concerns an article that is not yet indexed, the system fetches the article from Wikipedia, embeds it and adds it to the index while it runs. The ten most similar passages are retrieved, and those with a cosine similarity of at least 0.3 are passed on."),
  h3("4.4.3 Inference and the evidence rule"),
  p("A multilingual mDeBERTa-v3 model {debertav3} fine-tuned on MultiNLI and XNLI {mnli,xnli} gives, for each passage p, the probability e(p) that it entails the claim and the probability c(p) that it contradicts it. The passages are combined by the evidence rule:"),
  eq("s = 0.5 + 0.5 · max e(p)                                   if max e(p) ≥ 0.5"),
  eq("s = 0.5 + 0.5 · ( max e(p) − max c(q) over on-topic q )         otherwise"),
  p("A passage is on-topic when the title of its article, or a form of that title, appears in the claim. Support from any retrieved passage can therefore verify a claim, but only a passage about the claim’s own subject can contradict it. The rule removes the most common false alarm of the earlier version, in which a passage about a different subject contradicted the wording of the claim. It also removes many correct detections; Section 5.10 reports this cost."),
  lcap("Listing 4.1:", "Evidence rule (member3_backend/evidence_rules.py)"),
  code([
    "def aggregate(rows):",
    "    \"\"\"rows: (P(entail), P(contradict), on_topic) for each passage.\"\"\"",
    "    if not rows:",
    "        return 0.5",
    "    max_e = max(e for e, _, _ in rows)",
    "    if max_e >= ENTAIL_WINS:                     # 0.5: support from any passage",
    "        return 0.5 + 0.5 * max_e",
    "    on_topic_c = [c for _, c, t in rows if t]    # only on-topic passages contradict",
    "    return 0.5 + 0.5 * (max_e - (max(on_topic_c) if on_topic_c else 0.0))",
  ]),
  h3("4.4.4 Structured verification"),
  ...bullets([
    lb("Official statistics. ", "Claims about the population, GDP, life expectancy, adult literacy or infant mortality of a country are compared with World Bank {worldbank} figures and, for life expectancy and infant mortality, also with WHO {who} figures. A claim is judged at the precision it is written to: a GDP written as “US$ 0.1 billion” is not contradicted by an official 0.066 billion. When both agencies report a value they must agree on the verdict; if they disagree, no verdict is given."),
    lb("Knowledge graph. ", "Claims about places and dates of birth and death, founding dates, capitals, authorship, current office-holders, quantities and currencies are matched to Wikidata {wikidata} through English and Hindi relation templates. When several entities share the claimed name, one of them is enough to support the claim, but a contradiction requires every namesake that has a recorded value to disagree."),
  ]),
  lcap("Listing 4.2:", "Two-agency agreement for statistics (member2_data/official_stats.py)"),
  code([
    "def _agrees(claimed, official, tol, absolute, half=0.0):",
    "    # within the tolerance, or within the precision the claim is written to",
    "    return abs(claimed - official) <= max(tol if absolute else tol * official, half)",
    "",
    "votes = {_agrees(claimed, v, tol, absolute, half) for _, _, v, _ in figures}",
    "if len(votes) > 1:                 # World Bank and WHO disagree: no verdict",
    "    return _unknown(kind, claimed)",
    "status = \"supported\" if votes == {True} else \"contradicted\"",
  ]),
  h3("4.4.5 Matching published fact-checks"),
  p("Fact-checks are found through the Google Fact Check Tools API {googlefc}. A rating of “false” is carried over only if our claim entails the checked claim, and a rating of “true” only if the checked claim entails ours; neither is carried over when either direction reads as a contradiction or when the two claims are not similar enough (cosine below 0.5). This keeps a negated claim, such as “hot water does not kill the coronavirus”, from inheriting the rating of its opposite. If the applicable fact-checks disagree, none is used."),
  lcap("Listing 4.3:", "Direction-aware fact-check matching (member3_backend/factcheck_rules.py)"),
  code([
    "@property",
    "def applies(self):",
    "    \"\"\"Does the fact-check's clear rating carry over to our claim?\"\"\"",
    "    if self.similarity < FC_MIN_SIM or self.contra > FC_MAX_CONTRA:   # 0.50 / 0.20",
    "        return False",
    "    if self.check.verdict == \"false\":",
    "        return self.entail_claim_to_check >= FC_MIN_ENTAIL            # 0.70",
    "    if self.check.verdict == \"true\":",
    "        return self.entail_check_to_claim >= FC_MIN_ENTAIL",
    "    return False",
  ]),
  h3("4.4.6 Scoring: the Composite Multilingual Hallucination Scoring Algorithm (CMHSA)"),
  p("CMHSA was designed as a weighted combination of three signals for a claim c with evidence E and knowledge graph G:"),
  eq("HalluScore(c) = α · SemSim(c, E) + β · NLI(c, E) + γ · KG(c, G),     α + β + γ = 1"),
  p("SemSim is the similarity of the best retrieved passage, NLI the evidence-rule score s, and KG the knowledge-graph answer. The weights are produced by a softmax, so they are non-negative and sum to one, and they are trained separately for each language with class-balanced weighting on the training claims. A signal that is missing for a claim is left out and the remaining weights are rescaled. Two design decisions, both made during development, determine how the formula behaves in practice:"),
  ...bullets([
    lb("Similarity is excluded: ", "SemSim measures whether a passage is on the same topic, not whether it supports the claim, so it was excluded from training and α is fixed at exactly 0. The trained weights are β = 0.500 and γ = 0.500 for English and β = 0.498 and γ = 0.502 for Hindi. Similarity is still used, but only as the 0.3 relevance cut-off that decides which passages reach the inference model."),
    lb("The knowledge graph decides when it answers: ", "if statistics or Wikidata return supported or contradicted, the score is 1.0 or 0.0 and the other signals are not mixed in. This rule was chosen from an exploratory analysis of the 40 relational claims (Section 5.9)."),
  ]),
  p("Since α = 0 and a knowledge-graph answer overrides the formula, the weighted sum never actually blends two signals in the running system. The score of a claim is therefore set by the first of the following that applies:"),
  ...list("steps", [
    "Statistics or Wikidata answered: score 1.0 if supported, 0.0 if contradicted; the correct value is shown.",
    "A published fact-check applies: score 0.05 if rated false, 0.95 if rated true.",
    "Relevant passages were found: in Version 1 the evidence-rule score s; in Version 2 the verdict of the LLM cross-check (Section 4.4.7), with the score set to the mean of s and the LLM’s probability, kept inside the range of that verdict.",
    "None of these: score 0.5 (insufficient evidence) in Version 1; in Version 2 the LLM cross-check still reads the claim, without passages.",
  ]),
  p("The verdict follows from the score: below 0.35 Hallucinated, above 0.65 Verified, and Uncertain in between."),
  lcap("Listing 4.4:", "Claim scoring (member1_model/cmhsa.py)"),
  code([
    "alpha, beta, gamma = self.get_weights(language)        # alpha = 0.0 (SemSim excluded)",
    "raw = {\"semsim\": (alpha, sub_scores.sem_sim), \"nli\": (beta, sub_scores.nli_prob),",
    "       \"kg\": (gamma, sub_scores.kg_conf)}",
    "active = {k: (w, v) for k, (w, v) in raw.items() if v is not None}",
    "if KG_DECIDES and \"kg\" in active:                       # statistics / Wikidata answered",
    "    hallu_score = float(sub_scores.kg_conf)             # 1.0 supported, 0.0 contradicted",
    "else:",
    "    weight_sum = sum(w for w, _ in active.values())",
    "    hallu_score = sum((w / weight_sum) * v for w, v in active.values())",
  ]),
  h3("4.4.7 LLM cross-check (Version 2)"),
  p("The first version caught few hallucinations that no structured source covers, because the inference model accepts a passage that merely discusses a topic as support. An LLM catches many more, but in Version 1’s own test an LLM judge almost quadrupled the false alarms (Section 5.10). The cross-check therefore uses the LLM as a second reader whose verdict counts only together with the evidence. The model is gpt-oss-20b {gptoss}, an open-weight mixture-of-experts model with 21 billion parameters, of which 3.6 billion are active for each word, released under the Apache 2.0 licence. It runs on the project laptop with Ollama {ollama}, partly on the GPU and partly on the CPU; the same model can also be reached through the Groq and OpenRouter services: when Groq’s free per-minute limit is reached OpenRouter answers instead, and the laptop model is the last fallback, without waiting."),
  p("For every claim that no structured source or fact-check decided, the first reading gives the model the claim and the five best passages (600 characters each) and allows it to use its own knowledge. It answers in JSON with a verdict (Verified, Uncertain or Hallucinated), a probability that the claim is true, the wrong words copied from the claim, and a one-sentence reason; decoding is greedy (temperature 0). The verdict j is combined with the evidence-rule score s as follows (Fig. 4.4, Listing 4.5):"),
  ...list("steps2", [
    "If the reason of a Hallucinated j only says that the passages do not mention the fact (“no evidence”, “not stated”), j counts as Uncertain: missing evidence is not proof of falsehood.",
    "If s > 0.65 and j is Verified, the claim is Verified: the passages and the LLM agree.",
    "If j is Hallucinated and the passages do not support the claim (s ≤ 0.65), the claim is about to be flagged. A second reading first asks the same model, now restricted to all ten retrieved passages, whether they state the claim; if they do, the claim becomes Uncertain, otherwise it is Hallucinated. A passage contradiction alone never flags a claim.",
    "If the claim leans true (j is not Hallucinated and either s > 0.65 or j is Verified), the second reading is asked whether the passages state it; if they do, the claim becomes Verified, otherwise it stays Uncertain. Optionally (a switch that is off by default), a second reading that finds the claim false flags it.",
    "Otherwise the claim is Uncertain.",
  ]),
  p("The wrong words shown in the web application are the claimed value that Wikidata contradicts, or else the words the LLM named as wrong, or else the whole claim. Claims are cross-checked in parallel when a cloud provider is used, and each answer is cached, so a repeated claim costs no new LLM call."),
  png("fig2_decision_v2.png", 470),
  fcap("Fig. 4.4:", "Decision of the LLM cross-check for one claim"),
  lcap("Listing 4.5:", "Agreement rule of the cross-check (member3_backend/crosscheck.py)"),
  code([
    "def crosscheck_verdict(v1_verdict, decided_by_source, s, llm,",
    "                       number_missing=False, symmetric=True, flag_needs_llm=False):",
    "    if decided_by_source or llm not in (\"Verified\", \"Hallucinated\", \"Uncertain\"):",
    "        return v1_verdict              # a structured source decided, or no LLM answer",
    "    supported = s is not None and s > SUPPORT and not number_missing      # 0.65",
    "    contradicted = s is not None and s < CONTRADICT                       # 0.35",
    "    if contradicted and not flag_needs_llm and not (symmetric and llm == \"Verified\"):",
    "        return \"Hallucinated\"         # off in the final version (flag_needs_llm)",
    "    if supported and llm == \"Verified\":",
    "        return \"Verified\"             # both readers agree",
    "    if not supported and llm == \"Hallucinated\":",
    "        return \"Hallucinated\"         # then checked by the second reading",
    "    return \"Uncertain\"",
  ]),
  h3("4.4.8 Whole-text verdict"),
  p("The overall verdict is taken from the claim verdicts, not from an average, so that one false claim cannot be hidden among many true ones. A text is Hallucinated when at least one third of its claims are Hallucinated; otherwise it is Uncertain if any claim is Hallucinated or Uncertain; otherwise it is Verified. The overall score shown beside the verdict is the mean of the claim scores."),
  h("4.5 Database Design"),
  p("Accounts and history are stored in SQLite. Table 4.2 lists the tables. Passwords are stored only as salted scrypt hashes, and session tokens and password-reset codes only as SHA-256 hashes, so a copy of the database cannot be used to sign in."),
  tcap("Table 4.2:", "Database tables"),
  table([
    ["Table", "Main columns", "Purpose"],
    ["users", "id, email (unique), name, password_hash, created_at", "Registered accounts"],
    ["sessions", "token_hash, user_id, created_at, expires_at", "Signed-in sessions"],
    ["analyses", "id, user_id, created_at, language, input_text, result_json, total_claims, flagged_count", "History of checks"],
    ["password_resets", "code_hash, user_id, expires_at", "One-time password-reset codes (valid 30 minutes)"],
  ], [1700, 3900, 2562]),
  gap(),
  h("4.6 Flowchart of a Fact-Check Request"),
  p("Fig. 4.5 traces a single request from the input text to the final verdict."),
  png("fig_flowchart.png", 390),
  fcap("Fig. 4.5:", "Flowchart of a fact-check request"),

  // ===================== CHAPTER 5 =====================
  ...chapter(5, "Implementation and Results"),
  h("5.1 Technologies Used"),
  tcap("Table 5.1:", "Technologies used"),
  table([
    ["Purpose", "Technology"],
    ["Programming", "Python 3.13 (back end), TypeScript (web application)"],
    ["Deep learning", "PyTorch {pytorch}, Hugging Face Transformers {transformers}, Sentence-Transformers"],
    ["Models", "paraphrase-xlm-r-multilingual-v1 (embeddings); mDeBERTa-v3-base-mnli-xnli (inference); spaCy en_core_web_sm (parsing)"],
    ["Search", "FAISS index of Wikipedia passages; live Wikipedia search"],
    ["Structured data", "Wikidata; World Bank Open Data; WHO Global Health Observatory; Google Fact Check Tools API"],
    ["LLM (Version 2)", "gpt-oss-20b {gptoss} through Ollama {ollama} (local) or the Groq and OpenRouter APIs"],
    ["Web", "FastAPI, Uvicorn, SQLite, React, Vite, Tailwind CSS"],
  ], [2000, 6162]),
  gap(),
  h("5.2 Implementation of the Modules"),
  p("A request passes through the modules of Table 4.1 in the order of Fig. 4.1. Most of the waiting time comes from web look-ups rather than from the models, so the implementation concentrates on them. Up to six claims are looked up at the same time; each external service is paced separately, so that Wikipedia, Wikidata and the World Bank do not wait for one another; recent Wikidata and Wikipedia searches are remembered for a day; and a slow statistics service is abandoned after 8 seconds and one retry. None of these changes alters a verdict: the 13 claims of three test texts received the same verdicts before and after."),
  p("The LLM cross-check is switched on with a server setting, so that the same code runs Version 1 or Version 2; the server’s health check reports which one is running. The LLM providers are tried in order: Groq first when a key is set, then OpenRouter, and the local Ollama model last; when a service answers that its limit is reached, the next one is tried at once, so a limit costs no waiting. Readings are cached by claim and passages, a provider that fails is skipped for a minute, and a reply that is not valid JSON is read tolerantly or asked for again. If no LLM answers at all, the claim keeps its Version 1 verdict and the claim card says so."),
  p("For demonstrations, a single server process (serve.py) delivers both the website and the API, and a secure public https link to the laptop is created with a Cloudflare tunnel; a script starts Version 2 with all its settings. The application is also packaged as a container for cloud hosting. The code base has 323 automated tests."),
  h("5.3 Web Application"),
  p("A user pastes or uploads an answer, leaves the language on automatic detection (Devanagari script means Hindi) or chooses it, and starts the check. The result page shows the whole-text verdict and overall score, the text with each claim underlined in the colour of its verdict, and a card for every claim with its source, evidence and, where available, the correct fact. Signed-in users keep a history of their checks and can export results as CSV or JSON. In Version 2 the wrong words of a flagged claim are underlined in the text, and each claim card also shows what each reader said: the passages (support, contradict or unclear, with the score), the LLM with its reason, and the second reading. Screenshots 5.1 to 5.5 were taken from the running system in Version 1, and Screenshot 5.6 in Version 2."),
  framed("shot1.png", 520), fcap("Screenshot 5.1:", "Input page with an example answer"),
  framed("shot2.png", 520), fcap("Screenshot 5.2:", "Results page: whole-text verdict and highlighted claims"),
  framed("shot3.png", 520), fcap("Screenshot 5.3:", "Claim cards with the correct fact from Wikidata"),
  framed("shot4.png", 520), fcap("Screenshot 5.4:", "A Hindi claim decided by a published fact-check"),
  framed("shot5.png", 520), fcap("Screenshot 5.5:", "History of saved checks (account e-mail hidden)"),
  framed("shot6.png", 520), fcap("Screenshot 5.6:", "Version 2: wrong words marked and the verdict of each reader"),
  p("Security measures: passwords are hashed with scrypt and a per-user salt; sessions use HttpOnly cookies; state-changing requests from other websites are refused by an origin check; failed sign-ins are throttled (five failures for the same account from the same address within 15 minutes block further attempts until the window clears); checks are rate-limited per user and per network address; a password change requires the current password; and a forgotten password is reset with a one-time code that is valid for 30 minutes."),
  h("5.4 Datasets and Annotation"),
  p("Table 5.2 lists the data used for evaluation. The main set consists of claims extracted from answers that the Llama 3.3 (70B) model {llama3} gave to questions in five domains: government, healthcare, science, sports and history."),
  tcap("Table 5.2:", "Datasets"),
  table([
    ["Dataset", "Source", "Size", "Used for"],
    ["Labelled chatbot claims", "Llama 3.3 (70B) answers, five domains", "456 claims (266 English, 190 Hindi); 418 well-formed", "Weight training and main evaluation"],
    ["Train / test split", "418 well-formed claims, grouped by source question; test fold fixed in advance", "334 / 84 claims; binary sets 303 (258 true, 45 hallucinated) / 76 (66 true, 10 hallucinated)", "Main evaluation"],
    ["Relational claims", "Answers from gpt-oss-120b and qwen3.8-27b", "45 labelled by two annotators; 40 where they agreed (25 true, 15 hallucinated); English", "Knowledge-graph study"],
    ["Unseen true sentences", "Wikipedia sentences not used in development", "99 claims and 128 claims (two samples)", "False-alarm tests"],
    ["Statistics test", "True and altered figures for 40 randomly chosen countries", "137 true and 137 altered claims", "Statistics check"],
    ["Fact-check test", "Known rumours and true statements", "40 claims (25 rumours, 15 true)", "Fact-check matching"],
    ["Pronoun test", "Held-out Wikipedia introductions", "400 introductions", "Pronoun resolution"],
    ["Common-sense set", "Statements written for the error analysis", "15 statements (9 false)", "Error analysis"],
    ["FEVER (public) {fever}", "paper_dev split, random sample (seed 20261010)", "150 supported and 150 refuted claims (English)", "Public benchmark"],
    ["Mu-SHROOM (public) {mushroom}", "SemEval-2025 Task 3 test sets", "150 Hindi and 154 English model answers with annotated spans", "Public benchmark"],
    ["Version 2 sets (public and constructed)", "FEVER; Mu-SHROOM claims (English, Hindi); TruthfulQA {truthfulqa}; X-FACT Hindi rumours {xfact}; Hindi Wikipedia sentences with one number changed, as written and reworded", "Development and locked test splits per set", "Choosing and evaluating the cross-check"],
    ["Version 2 held-out sample", "Locked test splits, up to 60 true and 60 false items per set and language, none used before", "620 items (246 true, 374 false)", "Final comparison of Version 1 and Version 2"],
  ], [1700, 2400, 2462, 1600]),
  gap(),
  p("Annotation was done in two ways, and the difference matters. The 456 main claims were labelled by a team of four annotators, the authors, who shared the claims among themselves so that each claim was labelled by one of them. An AI system suggested a verdict for every claim, and the annotator confirmed or overrode each suggestion. Overall, 79% of the final labels agree with the suggestion. Because the suggestion was visible, these labels may be biased towards it. Two blind checks measured this. In the first, two annotators independently labelled 56 claims without seeing any suggestion; their agreement on “hallucination or not” was κ = 0.53 (88% raw agreement). In the second, 50 claims were labelled blind; where the two annotators agreed (46 claims), the existing label matched theirs in 45 cases. The relational claims were labelled by two annotators with AI assistance, and only the 40 claims on which both agreed are used."),
  p("The Version 2 sets contain no label written by the project team. A Mu-SHROOM claim is labelled false when it overlaps a human-marked hallucinated span by at least three characters, and claims with one or two overlapping characters are dropped. TruthfulQA contributes the best answer and the first incorrect answer to each question, stated without the question. X-FACT contributes Hindi statements rated false by professional fact-checkers. The Hindi Wikipedia true items are sentences taken from articles, and each false item is the same sentence with one number changed; the reworded set paraphrases the true sentences with a different LLM (qwen3.8-27b), keeps a paraphrase only if the inference model finds that each sentence entails the other with probability at least 0.80 and all numbers are kept, and changes one number for the false item. The chatbot claims of the first version were used while the cross-check was developed, so they are not used to report it."),
  h("5.5 Evaluation Method"),
  p("For each proposed change, a decision rule stating what the change had to achieve (for example, fewer false alarms without fewer correct verdicts) was written down and committed to the project repository before the change was run. Most evaluations followed this protocol. Two analyses of how the knowledge graph should be used were exploratory: they were made after the labels had been seen and are marked as such. In four cases the final decision went against the outcome of the rule; these are reported in Section 5.10."),
  p("Version 2 followed a stricter protocol, recorded in the project repository before each run. The LLM was chosen in a bake-off on 202 development items fixed in advance: gpt-oss-20b reached the highest balanced accuracy under the cross-check (57%, with 7% false alarms), ahead of gpt-oss-120b (56%, 10%); qwen3.8-27b answered fewer than 90% of the items and was excluded by rule. Held-out samples were drawn from the locked test splits, no item twice, and each was run once for both versions. Before each run the configuration and its acceptance criterion were written down; the final criterion required, relative to Version 1, at least twice as many catches, at most half as many false items passed as Verified, false alarms at most 3 points higher, and true items Verified at most 5 points lower. Paired differences are tested with exact McNemar tests, and the ratio of catches with a bootstrap over items (2,000 resamples)."),
  p("The measures are defined as follows. A false alarm is a true claim marked Hallucinated. A hallucination is caught when it is marked Hallucinated. A verdict is correct when it matches the label; Uncertain is never counted as correct. Claims from the same chatbot answer are always on the same side of the train/test split, so that the context of an answer cannot leak into the test."),
  h("5.6 Results on Real Chatbot Claims and Unseen Data"),
  tcap("Table 5.3:", "Results of the running system on chatbot claims and unseen data"),
  table([
    ["Set", "Correct", "False alarms", "Hallucinations caught", "Hallucinations marked Verified", "Uncertain"],
    ["Training claims (303)", "157", "9 of 258", "5 of 45", "27 of 45", "110"],
    ["Test claims (76)", "38", "3 of 66", "0 of 10", "8 of 10", "27"],
    ["Unseen true sentences (128)", "113 (Verified)", "4 of 128", "—", "—", "11"],
  ], [2162, 1100, 1150, 1250, 1400, 1100], { center: [1, 2, 3, 4, 5] }),
  gap(),
  p("The system seldom calls a true statement false: 4 of 128 unseen true sentences and 3 of 66 true test claims. It is, however, weak at catching hallucinations that no structured source covers: on the training claims 27 of 45 hallucinations were marked Verified and only 5 were caught, and on the small test set none of 10 was caught. Many claims end as Uncertain."),
  h("5.7 Results on Public Benchmarks"),
  p("To allow comparison with other work, the unchanged Version 1 system was run on two public, human-labelled benchmarks. The protocol (samples, measures, baselines) was written down before the run, and nothing in the system was tuned on these data."),
  p(`FEVER {fever}. Table 5.4 gives the results on 300 claims from the FEVER paper_dev split. Of the supported claims ${pc(B.fever.live.supports_verified)} were verified and ${kn(B.fever.live.supports_false_alarm)} raised false alarms; of the refuted claims ${pc(B.fever.live.refutes_caught)} were caught. The system gave a definite verdict on ${pc(B.fever.live.decided)} of the claims, and ${pc(B.fever.live.accuracy_decided)} of those verdicts were correct. Statistics or Wikidata decided only 9 claims (7 correctly) and no fact-check applied, so the inference-only figures are almost the same. Among the 17 false alarms are facts that were true in 2017 but have changed since (“Marillyn Hewson is currently the President of Lockheed Martin”), vague statements (“Kesha has a full name”), genuine inference errors (“Tim McGraw acted in The Blind Side”) and one knowledge-graph error (“The Bee Gees wrote songs”).`),
  tcap("Table 5.4:", "FEVER sample: live system and inference only"),
  table([
    ["", "Live system", "Inference only"],
    ["Supported claims marked Verified", kn(B.fever.live.supports_verified), kn(B.fever.nli_only.supports_verified)],
    ["Supported claims marked Hallucinated (false alarms)", kn(B.fever.live.supports_false_alarm), kn(B.fever.nli_only.supports_false_alarm)],
    ["Refuted claims marked Hallucinated (caught)", kn(B.fever.live.refutes_caught), kn(B.fever.nli_only.refutes_caught)],
    ["Refuted claims marked Verified (missed)", kn(B.fever.live.refutes_missed), kn(B.fever.nli_only.refutes_missed)],
    ["Accuracy of definite verdicts", pc(B.fever.live.accuracy_decided), pc(B.fever.nli_only.accuracy_decided)],
  ], [4362, 1900, 1900], { center: [1, 2] }),
  gap(),
  p(`Mu-SHROOM {mushroom}. Each model answer was checked as a whole, and the characters of the claims marked Hallucinated were compared with the annotated hallucinated spans (Table 5.5). The system flagged at least one claim in ${pc(B.mushroom_hi.answers_flagged)} of the Hindi and ${pc(B.mushroom_en.answers_flagged)} of the English answers. When it flagged a claim, the claim lay on an annotated span in ${pc(B.mushroom_hi.flagged_claims_on_gold)} (Hindi) and ${pc(B.mushroom_en.flagged_claims_on_gold)} (English) of cases, but because it flags so little, its span IoU is far below a baseline that marks every character and far below the teams of the shared task (best IoU 0.74 for Hindi and 0.65 for English; team means 0.50 and 0.40). No Hindi claim and only 3 English claims were decided by a structured source.`),
  tcap("Table 5.5:", "Mu-SHROOM test sets: span IoU and correlation"),
  table([
    ["Method", "Hindi (150): IoU / correlation", "English (154): IoU / correlation"],
    ["Satya-Score (live)", `${f3(B.mushroom_hi.live.iou)} / ${f3(B.mushroom_hi.live.cor)}`, `${f3(B.mushroom_en.live.iou)} / ${f3(B.mushroom_en.live.cor)}`],
    ["Mark-all baseline", `${f3(B.mushroom_hi.mark_all.iou)} / ${f3(B.mushroom_hi.mark_all.cor)}`, `${f3(B.mushroom_en.mark_all.iou)} / ${f3(B.mushroom_en.mark_all.cor)}`],
    ["Mark-none baseline", `${f3(B.mushroom_hi.mark_none.iou)} / ${f3(B.mushroom_hi.mark_none.cor)}`, `${f3(B.mushroom_en.mark_none.iou)} / ${f3(B.mushroom_en.mark_none.cor)}`],
    ["Best team (task report)", "0.74 / 0.78", "0.65 / 0.62"],
    ["Mean of teams (task report)", "0.50 / 0.52", "0.40 / 0.37"],
  ], [3162, 2500, 2500], { center: [1, 2] }),
  gap(),
  p("The benchmarks confirm the picture from the project’s own data: when the system flags a claim it is usually right, but it flags little, and the structured sources that make it reliable apply to few of the claims in these benchmarks. This is the gap the LLM cross-check was built to close."),
  h("5.8 Results of the LLM Cross-Check (Version 2)"),
  p("Table 5.6 gives the final comparison of the two versions on the 620 held-out items, run once. With the cross-check the system caught 176 of 374 false items instead of 95 (McNemar test: 92 newly caught, 11 lost, p < 0.001) and passed 23 of them as Verified instead of 83 (p < 0.001). Of the 246 true items, 139 were Verified instead of 137 and 32 were flagged instead of 28; neither change is significant (p = 0.87 and 0.63; difference in false alarms +1.6 points, 95% interval −3.2 to +6.6). Three of the four criteria were met. Catches rose by a factor of 1.85 (95% interval 1.61 to 2.19), short of the required 2, so by its own rule Version 2 was not made the default; it is offered as a mode that can be switched on."),
  tcap("Table 5.6:", "Held-out comparison of Version 1 and Version 2 (620 items)"),
  table([
    ["Measure", "Version 1", "Version 2", "Criterion fixed in advance"],
    ["False items caught", "95 of 374 (25%)", "176 of 374 (47%)", "At least 2× Version 1: not met (1.85×)"],
    ["False items passed as Verified", "83 of 374 (22%)", "23 of 374 (6%)", "At most half: met"],
    ["True items Verified", "137 of 246 (56%)", "139 of 246 (57%)", "At most 5 points lower: met"],
    ["False alarms on true items", "28 of 246 (11%)", "32 of 246 (13%)", "At most 3 points higher: met"],
  ], [2262, 1600, 1600, 2700], { center: [1, 2] }),
  gap(),
  p("Table 5.7 breaks the result down by set. The gains are largest where Version 1 relied on weak text evidence: Hindi Wikipedia sentences with a changed number (caught 3% → 39%), false Mu-SHROOM Hindi claims (7% → 45%) and TruthfulQA misconceptions (17% → 43%). On FEVER the cross-check caught more and also flagged fewer true claims, although it Verified slightly fewer (72% → 67%). The costs fall on TruthfulQA, where false alarms rose from 18% to 27% because many answers are vague without their question, and on the reworded Hindi sentences (3% → 11%). X-FACT rumours were already caught by published fact-checks; without that source Version 1 caught only 5% of them."),
  tcap("Table 5.7:", "Results per set, Version 1 → Version 2 (percent of items)"),
  table([
    ["Set (true / false items)", "Caught", "Passed as Verified", "False alarms"],
    ["FEVER, English (60 / 60)", "37 → 62", "20 → 5", "13 → 7"],
    ["Hindi Wikipedia (38 / 38)", "3 → 39", "13 → 5", "0 → 0"],
    ["Hindi Wikipedia, reworded (36 / 36)", "28 → 47", "33 → 0", "3 → 11"],
    ["Mu-SHROOM, English (52 / 60)", "13 → 20", "23 → 15", "15 → 15"],
    ["Mu-SHROOM, Hindi (0 / 60)", "7 → 45", "38 → 5", "—"],
    ["TruthfulQA, English (60 / 60)", "17 → 43", "27 → 8", "18 → 27"],
    ["X-FACT, Hindi (0 / 60)", "67 → 70", "2 → 2", "—"],
  ], [3062, 1700, 1700, 1700], { center: [1, 2, 3] }),
  gap(),
  p("Table 5.8 removes the parts of the rule one at a time, using the LLM answers already stored for the same 620 items; this analysis was made after the result above and is exploratory. The LLM alone caught most false items but flagged 28% of true ones. Requiring agreement with the passages lowered false alarms to 22%, the no-evidence filter to 16% at the cost of catches, the second reading brought true claims Verified back from 47% to 57%, and requiring the LLM to say false, with the passages-only check before flagging, brought false alarms to 13%. The optional switch that lets a second reading’s “Hallucinated” flag a claim raised catches to 49% and false alarms to 15%."),
  tcap("Table 5.8:", "Ablation on the held-out sample (exploratory)"),
  table([
    ["Variant", "Caught", "Passed as Verified", "True Verified", "False alarms"],
    ["Version 1 (no LLM)", "25%", "22%", "56%", "11%"],
    ["LLM alone", "86%", "11%", "65%", "28%"],
    ["Agreement rule only", "68%", "4%", "47%", "22%"],
    ["+ no-evidence filter", "49%", "4%", "47%", "16%"],
    ["+ second reading", "49%", "6%", "57%", "16%"],
    ["+ LLM must say false, check before flagging (Version 2)", "47%", "6%", "57%", "13%"],
    ["Version 2 + second reading may flag (optional)", "49%", "6%", "57%", "15%"],
  ], [3162, 1250, 1250, 1250, 1250], { center: [1, 2, 3, 4] }),
  gap(),
  p("The final rule is the fourth version tested on held-out data, each time on a fresh sample (Table 5.9). The plain agreement rule failed the first criterion, an absolute limit of 5% false alarms; inspection showed the LLM calling claims false only because the passages did not mention them. That limit had been set when Version 1’s own rate on chatbot claims looked like 3–6%, whereas on these sets it is 9–12%, so before the next run the criterion was changed to one relative to Version 1 and the no-evidence filter was added. The criteria and each change were written down before the sample they were tested on."),
  tcap("Table 5.9:", "Development rounds of the cross-check on held-out samples (Version 2 against Version 1)"),
  table([
    ["Round (items)", "Change", "Caught", "False alarms", "Outcome"],
    ["1 (201)", "Agreement rule", "58% vs 20%", "17% vs 9%", "Failed (false alarms)"],
    ["2 (175)", "+ no-evidence filter", "47% vs 15%", "12% vs 12%", "Passed; true Verified 40% vs 56%"],
    ["3 (162)", "+ second reading", "37% vs 19%", "14% vs 5%", "Failed (catches, false alarms)"],
    ["4 (620)", "+ check before flagging", "47% vs 25%", "13% vs 11%", "3 of 4 criteria met"],
  ], [1300, 2062, 1500, 1500, 1800], { center: [0, 2, 3] }),
  gap(),
  p("Marking only the wrong words instead of whole claims also improved span overlap on Mu-SHROOM (Table 5.10, answers in the held-out sample), especially for Hindi, although the system remains below a baseline that marks every character and far below the shared-task teams, which were built for span marking."),
  tcap("Table 5.10:", "Mu-SHROOM span IoU on the held-out answers"),
  table([
    ["Method", "Hindi (52 answers)", "English (72 answers)"],
    ["Version 1, flagged claims", "0.010", "0.114"],
    ["Version 2, flagged claims", "0.097", "0.172"],
    ["Version 2, wrong words only", "0.189", "0.184"],
    ["Mark-all baseline", "0.318", "0.307"],
  ], [3162, 2500, 2500], { center: [1, 2] }),
  gap(),
  h("5.9 Results of the Structured Sources"),
  tcap("Table 5.11:", "Results of the structured sources"),
  table([
    ["Component", "Test data", "Result"],
    ["Knowledge graph, pre-registered run", "40 relational claims (English)", "11 of 13 decisions correct: supported 8 of 8, contradicted 3 of 5"],
    ["Knowledge graph after a place-linking fix (exploratory)", "Same 40 claims", "12 of 12 decisions correct: supported 10 of 10, contradicted 2 of 2"],
    ["Knowledge graph ablation, pre-registered", "Same 40 claims", "Inference model alone against inference plus knowledge graph: AUC 0.704 \u2192 0.784 (difference +0.080, 95% interval +0.003 to +0.189); Hallucinated-F1 0.512 \u2192 0.615"],
    ["Knowledge graph deciding when it answers (after the fix)", "Same 40 claims", "Correct verdicts: 14 with the inference model alone, 24 when the knowledge graph decides"],
    ["Official statistics", "40 randomly chosen countries", "137 of 137 altered figures contradicted; of 137 true figures, 131 Verified, 0 contradicted, 6 without an answer"],
    ["Published fact-checks", "40 claims (25 rumours, 15 true)", "No wrong decision; rumours caught 3 → 10 of 25; correct verdicts 13 → 20 of 40"],
    ["Pronoun resolution", "400 Wikipedia introductions", "Correctly resolved 93 → 277; wrongly resolved 206 → 128"],
  ], [2500, 2100, 3562]),
  gap(),
  p("The two incorrect decisions of the pre-registered knowledge-graph run came from place names linked to the wrong Wikidata items (for example, a town linked to a given name and a village to a monorail station). The linking was corrected after these results had been seen, which is why the 12-of-12 figure is exploratory. The rule that the knowledge graph decides when it answers was also chosen on these 40 claims after the labels were known: its score separated true from hallucinated claims slightly better than the weighted combination (AUC 0.872 against 0.848; difference +0.024, 95% interval −0.000 to +0.083). The pre-registered ablation, by contrast, was fixed before any label existed and shows that adding the knowledge graph to the inference signal improves the separation of true and hallucinated claims. The knowledge-graph results are for English claims; the Hindi templates are implemented but were not part of this test."),
  h("5.10 Changes Tested and Not Adopted"),
  p("Table 5.12 lists the main changes to Version 1 and the decision taken on each. The first four rows are the cases in which the final decision went against the outcome of the rule. The changes of Version 2 are reported in Section 5.8."),
  tcap("Table 5.12:", "Changes tested and the decisions taken"),
  table([
    ["Change", "Measured outcome", "Decision"],
    ["Evidence rule (Section 4.4.3)", "False alarms on 99 unseen true statements 33 → 8; but its pre-fixed check on training AUC failed, and hallucinations caught fell (train 11 → 3 of 45, test 3 → 0 of 10, relational 12 → 2 of 15)", "Adopted against the rule, to avoid calling true text false"],
    ["Reading 10 passages instead of 3", "Correct training verdicts 130 → 170 of 303; but its pre-fixed check on false alarms failed (8 → 11 of 258)", "Adopted against the rule"],
    ["LLM judge (open mode)", "Met its rule (training AUC 0.717 against 0.552); caught 18 instead of 5 of 45 hallucinations, but false alarms rose from 9 to 35 of 258", "Kept off against the rule; Version 2 uses the LLM as a cross-checker instead"],
    ["Larger inference models", "The rule picked other models (English: train AUC 0.602 against 0.539, intervals overlapping; Hindi: too few hallucinations to judge)", "Current model kept against the rule"],
    ["Number guard (two versions)", "Removed correct verifications (115 → 101; 109 → 103)", "Not adopted"],
    ["MedlinePlus as a second source", "False alarms 9 → 11 of 258", "Not adopted"],
    ["Strict support rule", "True claims Verified 152 → 47; false alarms 9 → 11", "Not adopted"],
    ["Wikipedia articles fetched on demand", "First test: no gain (ΔAUC −0.020); second test, with the evidence rule: all three conditions met", "Adopted after the second test"],
    ["MiniCheck grounding checker (probe)", "Still supported 7 of 9 false common-sense statements, as the current model did", "Not pursued"],
  ], [2100, 4062, 2000]),
  gap(),
  p("These results are informative in themselves. The method that caught the most hallucinations, an LLM judge, did so at a cost in false alarms that the project was not willing to accept, and the evidence rule bought its low false-alarm rate with fewer detections. Version 2 grew out of these two observations."),
  h("5.11 Performance"),
  tcap("Table 5.13:", "Performance on the laptop (RTX 4050 GPU)"),
  table([
    ["Text and configuration", "First check", "Repeated check"],
    ["Version 1 before optimisation: chatbot answer, 6 claims (English)", "27.7 s", "10.1 s"],
    ["Version 1 after optimisation: same answer", "5.1 s", "0.7 s"],
    ["Version 1: general facts, 4 claims (English)", "1.6 s", "0.3 s"],
    ["Version 1: Hindi answer, 3 claims", "3.7 s", "0.4 s"],
    ["Version 2, local LLM only: 6 claims (English)", "45.7 s", "under 3 s"],
    ["Version 2, Groq first: 5 claims (English)", "18.2 s", "2.7 s"],
  ], [4562, 1800, 1800], { center: [1, 2] }),
  gap(),
  p("Without a GPU, the six-claim answer took 13.7 s on first check and 0.7 s on repetition in Version 1. Starting the server loads the models once, which takes about 20 seconds; the local LLM is loaded on first use, which adds about half a minute to the first check. In Version 2 most of the time is spent by the LLM: the 13 GB model does not fit in the 6 GB GPU memory, so Ollama runs most of it on the CPU at about 4 seconds per reading. Allowing four parallel requests to the local model made a six-claim answer slower (202 s), so it reads one claim at a time. With Groq answering first, the readings take about a second each and run in parallel, but the free tier allows only about 8,000 tokens per minute, three to four readings, so a busy minute falls back to the next service. With OpenRouter as the second service, a three-claim check took 6 to 8 s, against 41 s when the busy minutes fell back to the laptop model."),
  h("5.12 Discussion and Limitations"),
  p([r("Comparison with existing methods. ", { bold: true }), "The systems in Table 2.1 were evaluated on other data and languages, so their published scores cannot be compared directly with these results, except on Mu-SHROOM (Section 5.7), where the system is far behind the shared-task teams on span-level IoU. Qualitatively, Satya-Score is the only one among them that checks Hindi claims against structured sources and states the correct fact. On this project’s data, a purpose-built grounding checker and larger inference models did not improve on the model in use, and an LLM judge traded many more false alarms for its extra detections. Used as a cross-checker instead, the same kind of model nearly doubled the catches of Version 1 at a cost of about two points in false alarms."]),
  p([r("What the cross-check shows. ", { bold: true }), "An LLM is a strong but unreliable witness: alone it caught 86% of the false items and flagged 28% of the true ones, so its value lies in being combined with evidence rather than in replacing it. Most of the improvement comes from claims that no structured source covers, especially in Hindi, where the inference model had found almost nothing. Each safeguard traded some catches for fewer false alarms, and the final rule sits close to Version 1’s false-alarm rate. When the passages and the LLM disagree, the claim is left Uncertain rather than given either reader’s verdict, which is why some false claims are reported as Uncertain instead of Hallucinated."]),
  p([r("Error analysis. ", { bold: true }), "Of the 45 hallucinations in the training split, about 31 turned out to come from an earlier version of the claim extractor rather than from the chatbot. Most of the remaining ones are misconceptions or over-generalisations that no structured source records; several were marked Verified because a retrieved passage was merely about the same topic, the word-overlap weakness described by McCoy et al. {mccoy}. On 15 common-sense statements written for this analysis, all 9 false ones were marked Verified."]),
  p([r("Limitations:", { bold: true })], { keepNext: true }),
  ...bullets([
    "In Version 1, hallucinations outside the coverage of structured sources are usually missed; in Version 2 about half of the false items are still not caught.",
    "The Version 2 criterion of doubling the catches was missed (1.85×); the criterion was changed once after a failed run, and the final rule was chosen on samples that had already been used. All held-out samples are now used up.",
    "The constructed Hindi false items change a single number and are easier than real errors; Mu-SHROOM claim labels come from span overlap; TruthfulQA answers lack their question; each set contributes at most 60 true and 60 false items.",
    "The LLM’s knowledge has a cut-off date, it can share the misconceptions of the chatbots it checks, and on the laptop it makes a check take tens of seconds.",
    "The labelled chatbot data are small (456 main and 40 relational claims) and contain few Hindi hallucinations (9).",
    "Each main claim was labelled once, by one of the four annotators, with the AI suggestion visible; agreement between independent annotators was moderate (κ = 0.53).",
    "The knowledge-graph rules were chosen in exploratory analyses on the same 40 claims on which they were measured.",
    "Live look-ups need internet access, and the WHO data may be used for non-commercial purposes only.",
  ]),

  // ===================== CHAPTER 6 =====================
  ...chapter(6, "Conclusions and Future Scope"),
  h("6.1 Conclusion"),
  p("Satya-Score checks English and Hindi answers one claim at a time and supports every verdict with a source that the reader can open. Sending each claim first to official statistics, the Wikidata knowledge graph or a published fact-check made the system precise wherever such a source applies, and the conservative evidence rule kept false alarms on true text low. The first version showed the price of that caution: most hallucinations that no structured source covers were not caught. The second version adds an open-weight LLM as a second reader whose verdict counts only when the evidence agrees. On 620 held-out items it nearly doubled the hallucinations caught (47% against 25%) and cut those passed as Verified from 22% to 6%, while false alarms rose only from 11% to 13%; it met three of the four criteria fixed in advance. Testing each change against a rule fixed in advance made clear which attractive ideas did not help, and the cases in which the project decided against a rule are reported openly. In one sentence, the contribution is an explainable bilingual claim checker that combines published fact-checks, official statistics, a knowledge graph, encyclopaedic text and an LLM that can never decide alone."),
  h("6.2 Future Scope"),
  ...bullets([
    "Raising the catches of the cross-check further, to the doubling we aimed for, without adding false alarms; for example by letting an LLM propose suspect claims that a structured source must then confirm.",
    "A faster deployment of the cross-check, for example a hosted service for the same open model.",
    "Extending the system to Marathi with MuRIL, IndicSBERT and IndicXNLI.",
    "A larger, multi-domain Hindi evaluation set, labelled blind by at least two annotators.",
    "Further official sources, such as Indian government open-data portals.",
  ]),
];


// ===================== back matter =====================
const backTitle = (t, first = false) => new Paragraph({ pageBreakBefore: !first, spacing: { after: 360 }, children: [r(key(t), { bold: true, size: 28 })] });
const resumeRows = (name) => {
  const W3 = [2300, 3762, 2100];
  const L = (t, o = {}) => cell(t, o.w, { size: 20, tight: true, ...o });
  const personal = new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: W3, rows: [
    new TableRow({ children: [L("PERSONAL DETAILS", { w: W3[0] + W3[1], span: 2, bold: true }),
      cell("Photo", W3[2], { rowSpan: 7, bold: true, align: AlignmentType.CENTER, size: 22 })] }),
    ...[["NAME", name], ["DOB", ""], ["ADDRESS", ""], ["MOBILE NO", ""], ["EMAIL_ID", ""], ["LINKEDIN ID", ""]].map(([a, b]) =>
      new TableRow({ height: { value: 360, rule: "atLeast" }, children: [L(a, { w: W3[0] }), L(b, { w: W3[1] })] })) ] });
  const W6 = [1300, 1300, 1500, 1500, 1281, 1281];
  const E = (t, i, o = {}) => cell(t, o.span ? W6.slice(i, i + o.span).reduce((a, b) => a + b, 0) : W6[i], { size: 20, tight: true, align: AlignmentType.CENTER, ...o });
  const sems = [["Ist Year", "I - SEM", "II - SEM"], ["IInd Year", "III - SEM", "IV - SEM"], ["IIIrd Year", "V - SEM", "VI - SEM"], ["IVth Year", "VII - SEM", "VIII - SEM"]];
  const education = new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: W6, rows: [
    new TableRow({ children: [E("EDUCATION DETAILS", 0, { span: 6, bold: true, align: AlignmentType.LEFT })] }),
    new TableRow({ children: [E("Name of Board", 0, { span: 3, bold: true }), E("Passing Year", 3, { bold: true }), E("% of Marks / CGPA", 4, { span: 2, bold: true })] }),
    ...[["10th SSC", "Maharashtra State Board"], ["12th HSC", "Maharashtra State Board"], ["Diploma", "Maharashtra State Board of Technical Education"]].map(([a, b]) =>
      new TableRow({ children: [E(a, 0), E(b, 1, { span: 2 }), E("", 3), E("", 4, { span: 2 })] })),
    new TableRow({ children: [E("Bachelor of Technology (B.Tech)", 0, { span: 2, bold: true }), E("Passing Year & Month", 2, { bold: true }),
      E("Marks Obtained / Out of", 3, { bold: true }), E("% of Marks", 4, { bold: true }), E("Pointer", 5, { bold: true })] }),
    ...sems.flatMap(([y, s1, s2]) => [
      new TableRow({ children: [E(y, 0, { rowSpan: 2 }), E(s1, 1), E("", 2), E("", 3), E("", 4), E("", 5)] }),
      new TableRow({ children: [E(s2, 1), E("", 2), E("", 3), E("", 4), E("", 5)] })]),
  ] });
  const W2 = [3000, 5162];
  const placement = new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: W2, rows: [
    new TableRow({ children: [cell("PLACEMENT DETAILS", TW, { span: 2, bold: true, size: 20, tight: true })] }),
    new TableRow({ children: [cell("Campus Placement (If Any)", W2[0], { size: 20, tight: true }), cell("", W2[1], { size: 20 })] }),
    new TableRow({ children: [cell("(If Any) Name of Company", W2[0], { size: 20, tight: true }), cell("", W2[1], { size: 20 })] }) ] });
  const WF = [3000, 2581, 2581];
  const future = new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: WF, rows: [
    new TableRow({ children: [cell("FUTURE PLANNING", TW, { span: 3, bold: true, size: 20, tight: true })] }),
    ...["Higher Studies", "Job", "Training", "Business"].map((t, i) => new TableRow({ children: [
      ...(i === 0 ? [cell("Higher Studies / Job Preferences", WF[0], { rowSpan: 4, size: 20, tight: true })] : []),
      cell(t, WF[1], { size: 20, tight: true }), cell("", WF[2], { size: 20, tight: true })] })) ] });
  const sp = () => new Paragraph({ spacing: { after: 60 }, children: [] });
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, pageBreakBefore: true, spacing: { after: 160 }, children: [r(key("RESUME"), { bold: true, size: 28 })] }),
    personal, sp(), education, sp(), placement, sp(), future,
    new Paragraph({ spacing: { before: 240 }, children: [r("Place: Amravati", { size: 22 }), new TextRun({ font: F, size: 22, children: [ptab(PositionalTabAlignment.RIGHT), "Signature"] })] }),
    new Paragraph({ children: [r("Date:   /   /2026", { size: 22 }), new TextRun({ font: F, size: 22, children: [ptab(PositionalTabAlignment.RIGHT), name] })] }),
  ];
};
const backMatter = () => [
  backTitle("REFERENCES", true),
  ...ORDER.map((k, i) => new Paragraph({ alignment: AlignmentType.LEFT, spacing: { line: 240, after: 120 }, indent: { left: 600, hanging: 600 },
    tabStops: [{ type: "left", position: 600 }], children: [new TextRun({ text: `[${i + 1}]\t${REFS[k]}`, font: F, size: 24 })] })),
  backTitle("LIST OF PUBLICATIONS"),
  p("Published papers and IPR filed in connection with this project:", { noIndent: true }),
  gap(),
  table([
    ["Sr. No.", "Title", "Type", "Status"],
    ["1", TITLE, "Research paper (IEEE conference format)", "Manuscript prepared; submission pending"],
    ["2", TITLE, "Copyright (to be filed through the institute)", "[Diary / application number, once filed]"],
  ], [900, 3262, 2200, 1800], { center: [0] }),
  ...AUTHORS.flatMap(a => resumeRows(a)),
];

// ===================== contents and lists =====================
const ROMAN = ["", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx"];
const pgNum = (k) => (k && PAGES[k] ? PAGES[k] : null);
const pgRoman = (k) => (pgNum(k) ? ROMAN.at(pgNum(k)) || String(pgNum(k)) : "");
const pgArabic = (k) => (pgNum(k) ? String(pgNum(k)) : "");
const COLS = [1000, 700, 5362, 1100];
const T = { line: 252, tight: true, size: 22 };
const tocRow = (a, b, title, page, o = {}) => new TableRow({ cantSplit: true, children: [
  cell(a, COLS[0], { ...T, align: AlignmentType.CENTER, bold: o.bold }), cell(b, COLS[1], { ...T, align: AlignmentType.CENTER }),
  cell(title, COLS[2], { ...T, bold: o.bold, italics: o.italics }), cell(page, COLS[3], { ...T, align: AlignmentType.CENTER, bold: o.bold, italics: o.italics })] });
const SUBS = {
  1: ["Overview", "Motivation", "Problem Definition", "Project Goal and Objectives", "Contribution", "Organization of Report"],
  2: ["Fact Verification and Claim Checking", "Hallucination Detection in LLM Output", "Grounding Checkers", "Multilingual and Hindi Fact-Checking", "Knowledge Graphs and Cross-Lingual Retrieval", "Summary of the Literature", "Research Gap"],
  3: ["Existing System and its Limitations", "Proposed System", "Requirement Analysis", "Hardware and Software Requirements", "Feasibility Study", "Overall System Architecture"],
  4: ["Block Diagram", "Data Flow Diagrams", "Module Design", "Algorithms", "Database Design", "Flowchart of a Fact-Check Request"],
  5: ["Technologies Used", "Implementation of the Modules", "Web Application", "Datasets and Annotation", "Evaluation Method", "Results on Real Chatbot Claims and Unseen Data", "Results on Public Benchmarks", "Results of the LLM Cross-Check (Version 2)", "Results of the Structured Sources", "Changes Tested and Not Adopted", "Performance", "Discussion and Limitations"],
  6: ["Conclusion", "Future Scope"],
};
const CH = { 1: "Introduction", 2: "Literature Review", 3: "System Architecture / Analysis", 4: "System Design", 5: "Implementation and Results", 6: "Conclusions and Future Scope" };
const FRONT_LISTS = ["List of Tables", "List of Figures", "List of Screenshots", "Notations", "Abbreviations"];
const range = (n) => { const s = pgNum(`CHAPTER ${n}`); const next = n < 6 ? pgNum(`CHAPTER ${n + 1}`) : pgNum("REFERENCES");
  return s ? (next && next - 1 > s ? `${s}-${next - 1}` : `${s}`) : ""; };
const contentsPage = () => [frontTitle("Table of Contents"), new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: COLS, rows: [
  new TableRow({ tableHeader: true, children: [cell("Chapter No", COLS[0], { head: true, align: AlignmentType.CENTER, size: 22 }), cell("", COLS[1], { head: true }),
    cell("Content / Title", COLS[2], { head: true, align: AlignmentType.CENTER, size: 22 }), cell("Page No", COLS[3], { head: true, align: AlignmentType.CENTER, size: 22 })] }),
  ...FRONT_LISTS.map(t => tocRow("", "", t, pgRoman(t), { italics: true })),
  ...Object.keys(CH).flatMap(n => [tocRow(`${n}.`, "", CH[n], range(+n), { bold: true }),
    ...SUBS[n].map((t, i) => tocRow("", `${n}.${i + 1}`, t, pgArabic(`${n}.${i + 1} ${t.toUpperCase()}`)))]),
  tocRow("", "", "References", pgArabic("REFERENCES"), { bold: true }),
  tocRow("", "", "List of Publications", pgArabic("LIST OF PUBLICATIONS"), { bold: true }),
  tocRow("", "", "Resume", pgArabic("RESUME"), { bold: true }),
] })];
const LCOLS = [1300, 5762, 1100];
const listTable = (head, items) => new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: LCOLS, rows: [
  new TableRow({ tableHeader: true, children: [cell(head, LCOLS[0], { head: true, align: AlignmentType.CENTER, size: 22 }),
    cell(`Name of ${head.replace(" No.", "")}`, LCOLS[1], { head: true, align: AlignmentType.CENTER, size: 22 }), cell("Page No.", LCOLS[2], { head: true, align: AlignmentType.CENTER, size: 22 })] }),
  ...items.map(x => new TableRow({ cantSplit: true, children: [cell(x.no, LCOLS[0], { ...T, align: AlignmentType.CENTER }), cell(x.title, LCOLS[1], T),
    cell(pgArabic(x.key), LCOLS[2], { ...T, align: AlignmentType.CENTER })] }))] });
const NCOLS = [2000, 6162];
const pairTable = (h1, h2, rows) => new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: NCOLS, rows: [
  new TableRow({ tableHeader: true, children: [cell(h1, NCOLS[0], { head: true, align: AlignmentType.CENTER, size: 22 }), cell(h2, NCOLS[1], { head: true, align: AlignmentType.CENTER, size: 22 })] }),
  ...rows.map(([a, b]) => new TableRow({ cantSplit: true, children: [cell(a, NCOLS[0], { ...T, align: AlignmentType.CENTER }), cell(b, NCOLS[1], T)] }))] });
const NOTATIONS = [
  ["s", "Passage (evidence) score of a claim from the inference model, between 0 and 1"],
  ["e(p), c(p)", "Probability that passage p entails / contradicts the claim"],
  ["j", "Verdict of the LLM's first reading (Verified, Uncertain or Hallucinated)"],
  ["α, β, γ", "CMHSA weights of the similarity, inference and knowledge-graph signals"],
  ["HalluScore", "CMHSA score of a claim (0 = contradicted, 1 = supported)"],
  ["SemSim, NLI, KG", "Similarity, inference and knowledge-graph signals of a claim"],
  ["κ", "Cohen's kappa, agreement between two annotators"],
  ["p", "p-value of a statistical test (exact McNemar test)"],
  ["n×", "Ratio of catches between two versions (e.g. 1.85×)"],
];
const ABBREVIATIONS = [
  ["AI", "Artificial Intelligence"], ["API", "Application Programming Interface"], ["AUC", "Area Under the ROC Curve"],
  ["CMHSA", "Composite Multilingual Hallucination Scoring Algorithm"], ["CSV", "Comma-Separated Values"], ["DFD", "Data Flow Diagram"],
  ["FAISS", "Facebook AI Similarity Search"], ["FEVER", "Fact Extraction and VERification (dataset)"], ["GPU", "Graphics Processing Unit"],
  ["IoU", "Intersection over Union"], ["IPR", "Intellectual Property Rights"], ["JSON", "JavaScript Object Notation"],
  ["KG", "Knowledge Graph"], ["LLM", "Large Language Model"], ["mDeBERTa", "Multilingual Decoding-enhanced BERT with disentangled attention"],
  ["MNLI / XNLI", "Multi-Genre / Cross-lingual Natural Language Inference corpora"],
  ["Mu-SHROOM", "Multilingual Shared-task on Hallucinations and Related Observable Overgeneration Mistakes"],
  ["NLI", "Natural Language Inference"], ["NLP", "Natural Language Processing"], ["RAG", "Retrieval-Augmented Generation"],
  ["REST", "Representational State Transfer"], ["ROC", "Receiver Operating Characteristic"], ["SemEval", "International Workshop on Semantic Evaluation"],
  ["SQL", "Structured Query Language"], ["UI", "User Interface"], ["WHO", "World Health Organization"], ["XLM-R", "Cross-lingual Language Model (RoBERTa)"],
];
const listsPages = () => [
  frontTitle("List of Tables", "last"), listTable("Table No.", CAPS.table),
  frontTitle("List of Figures", "last"), listTable("Figure No.", CAPS.figure),
  frontTitle("List of Screenshots", "last"), listTable("Screenshot No.", CAPS.shot),
  frontTitle("Notations", "last"), pairTable("Symbol", "Meaning", NOTATIONS),
  frontTitle("Abbreviations", "last"), pairTable("Abbreviation", "Full form", ABBREVIATIONS),
];

// ===================== assembly =====================
const bodyAll = [...body, { __back: true }, ...backMatter()];   // body first: fixes citation order and captions
const chunks = []; let cur = null;
for (const x of bodyAll) {
  if (x && x.__chapter) { cur = { chapter: x.__chapter, children: [] }; chunks.push(cur); continue; }
  if (x && x.__back) { cur = { back: true, children: [] }; chunks.push(cur); continue; }
  cur.children.push(x);
}
// the back matter's first title starts its own section, so drop its page break
const bodySections = chunks.map((ch, i) => ({
  properties: { type: ch.back ? SectionType.NEXT_PAGE : SectionType.ODD_PAGE,
    page: { ...pageSize, pageNumbers: i === 0 ? { start: 1, formatType: NumberFormat.DECIMAL } : { formatType: NumberFormat.DECIMAL } } },
  headers: { default: header }, footers: { default: bodyFooter }, children: ch.children,
}));
const doc = new Document({
  styles: { default: { document: { run: { font: F, size: 24 } } } },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    { reference: "objectives", levels: [{ level: 0, format: LevelFormat.LOWER_ROMAN, text: "%1)", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 420 } } } }] },
    { reference: "fr", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "FR%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 900, hanging: 620 } } } }] },
    { reference: "steps", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    { reference: "steps2", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    { reference: "contrib", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
  ] },
  sections: [
    { properties: { page: { ...pageSize, borders: pageBorders, pageNumbers: { start: 1, formatType: NumberFormat.LOWER_ROMAN } } }, children: titlePage },
    { properties: { type: SectionType.NEXT_PAGE, page: { ...pageSize, borders: pageBorders, pageNumbers: { formatType: NumberFormat.LOWER_ROMAN } } },
      children: [...certificatePage, ...acknowledgementPage] },
    { properties: { type: SectionType.NEXT_PAGE, page: { ...pageSize, borders: pageBorders, pageNumbers: { formatType: NumberFormat.LOWER_ROMAN } } },
      footers: { default: romanFooter }, children: [...abstractPage, ...contentsPage(), ...listsPages()] },
    ...bodySections,
  ],
});
fs.writeFileSync(path.join(HERE, "keys_v3.json"), JSON.stringify(KEYS));
const abstractWords = ABSTRACT.join(" ").split(/\s+/).length;
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf);
  console.log("wrote", OUT, "| keys:", KEYS.length, "| references:", ORDER.length, "| tables:", CAPS.table.length, "| figures:", CAPS.figure.length,
    "| screenshots:", CAPS.shot.length, "| abstract words:", abstractWords, "| unused refs:", Object.keys(REFS).filter(k => !ORDER.includes(k)).join(", ") || "none"); });
