// Satya-Score results paper (A4, for the publisher meeting). Numbers: results/v2_results_final.md, the v1 results,
// the exploratory ablation and the measured timings. Usage: node results_paper.js <out.docx>
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType, WidthType, BorderStyle,
  ShadingType, ImageRun, LevelFormat, Footer, PageNumber, HeadingLevel,
} = require("docx");

const OUT = process.argv[2];
const HERE = __dirname;
const F = "Times New Roman";
const W = 9638; // A4 width 11906 - 2 x 1134 margins

const run = (t, o = {}) => new TextRun({ text: t, font: F, size: o.size || 22, bold: o.bold, italics: o.italics, color: o.color });
const p = (parts, o = {}) => new Paragraph({ alignment: o.align || AlignmentType.JUSTIFIED, spacing: { after: o.after ?? 120, line: 288 },
  keepNext: o.keepNext, children: (Array.isArray(parts) ? parts : [parts]).map(x => typeof x === "string" ? run(x) : x) });
const h1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 240, after: 100 }, keepNext: true,
  children: [run(t, { bold: true, size: 26, color: "1F3864" })] });
const num = (items) => items.map(t => new Paragraph({ numbering: { reference: "steps", level: 0 }, spacing: { after: 60, line: 276 },
  alignment: AlignmentType.JUSTIFIED, children: (Array.isArray(t) ? t : [t]).map(x => typeof x === "string" ? run(x) : x) }));
const bul = (items) => items.map(t => new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 60, line: 276 },
  alignment: AlignmentType.JUSTIFIED, children: (Array.isArray(t) ? t : [t]).map(x => typeof x === "string" ? run(x) : x) }));

const line = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
const borders = { top: line, bottom: line, left: line, right: line };
function table(rows, widths, center = []) {
  if (widths.reduce((a, b) => a + b, 0) !== W) throw new Error("table widths");
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: widths, rows: rows.map((cells, i) => new TableRow({
    tableHeader: i === 0, cantSplit: true, children: cells.map((c, j) => new TableCell({
      width: { size: widths[j], type: WidthType.DXA }, borders, margins: { top: 60, bottom: 60, left: 100, right: 100 },
      shading: i === 0 ? { fill: "DCE6F2", type: ShadingType.CLEAR, color: "auto" } : undefined,
      children: [new Paragraph({ alignment: i === 0 || center.includes(j) ? AlignmentType.CENTER : AlignmentType.LEFT,
        children: [run(c, { size: 20, bold: i === 0 })] })] })) })) });
}
const cap = (t) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 200 }, children: [run(t, { size: 19, italics: true })] });
const tcap = (t) => new Paragraph({ alignment: AlignmentType.LEFT, keepNext: true, spacing: { before: 120, after: 80 }, children: [run(t, { size: 20, bold: true })] });
function img(file, widthPx) {
  const buf = fs.readFileSync(path.join(HERE, file));
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  return new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 40 },
    children: [new ImageRun({ type: "png", data: buf, transformation: { width: widthPx, height: Math.round(widthPx * h / w) } })] });
}
function box(parts) {
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows: [new TableRow({ cantSplit: true, children: [new TableCell({
    width: { size: W, type: WidthType.DXA }, margins: { top: 120, bottom: 120, left: 180, right: 180 },
    shading: { fill: "EEF3FA", type: ShadingType.CLEAR, color: "auto" },
    borders: { top: { style: BorderStyle.SINGLE, size: 12, color: "1F5FBF" }, bottom: line, left: line, right: line },
    children: parts })] })] });
}

const content = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [run("Satya-Score: Results", { bold: true, size: 40, color: "1F3864" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [run("An AI Hallucination Detection & Scoring Framework for English and Hindi", { size: 24, italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [run("Vivek Yeshwantrao Borkar, Piyush Devidas Nande, Aasawari Sahebrao Jumade, Arunima Tridip Wankhade; guide: Dr. R. R. Karwa", { size: 20 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [run("Dept. of Artificial Intelligence and Data Science, PRMIT&R, Badnera-Amravati · October 2026", { size: 20 })] }),

  box([
    p([run("In one sentence. ", { bold: true }), "Satya-Score checks an AI chatbot’s answer one claim at a time, in English and Hindi, and labels each claim Verified, Uncertain or Hallucinated with its evidence, the wrong words marked and, where an official source holds the fact, the correct value."], { after: 80 }),
    p([run("Headline result. ", { bold: true }), "On 620 held-out test items, the LLM cross-check (Version 2) caught 47% of false items against 25% without it, and let only 6% of them pass as Verified against 22%, while false alarms on true items stayed at 13% against 11% (not significant)."], { after: 0 }),
  ]),

  h1("1. What the system does"),
  p("Chatbots based on large language models (LLMs) write fluent answers that sometimes contain false statements, and readers cannot easily tell which sentence is wrong. Tools to check this are rare for Hindi. Satya-Score splits an answer into separate factual claims and sends each claim to the most trustworthy source that can settle it, so that every verdict comes with evidence the reader can open."),
  h1("2. Novelty claim"),
  box([p([run("To our knowledge, Satya-Score is the first claim-level checker that combines official statistics, a knowledge graph, published fact-checks and an LLM for English and Hindi, in which the LLM can never decide a claim alone: its verdict counts only when the retrieved evidence agrees.", { italics: true })], { after: 0 })]),
  new Paragraph({ spacing: { after: 80 }, children: [] }),
  ...bul([
    [run("Agreement-gated LLM: ", { bold: true }), "alone, the LLM flagged 28% of true items; under the agreement rule, 13% (Section 5)."],
    [run("Source routing with the correct value: ", { bold: true }), "statistics and Wikidata answer what they cover and show the right value."],
    [run("Wrong words marked, ", { bold: true }), "not just whole sentences flagged."],
    [run("Open and local: ", { bold: true }), "all models are open and run on a student laptop (RTX 4050, 6 GB)."],
    [run("Honest evaluation: ", { bold: true }), "acceptance criteria written down before every test; failures reported."],
  ]),

  h1("3. How it works"),
  ...num([
    [run("Split: ", { bold: true }), "the answer is broken into self-contained claims (spaCy for English, with pronouns resolved; Indic NLP Library for Hindi)."],
    [run("Trusted sources first: ", { bold: true }), "official statistics (World Bank, WHO), the Wikidata knowledge graph and published fact-checks. If one of them settles the claim, that verdict is final and the correct value is shown."],
    [run("Two readers for the rest: ", { bold: true }), "a multilingual inference model (mDeBERTa) reads the 10 most relevant Wikipedia passages, and an open-source LLM (gpt-oss-20b) judges the claim with the passages and its own knowledge."],
    [run("Agreement rule: ", { bold: true }), "a claim is Verified only when both readers say it is true. It is Hallucinated only when the LLM names a wrong fact and a second, passages-only reading does not find the claim stated. When the readers disagree, the claim is Uncertain."],
    [run("Explain: ", { bold: true }), "the web application underlines each claim in its verdict colour, marks the wrong words, and shows what each reader said and which source decided."],
  ]),
  img("fig1_architecture_v2.png", 360),
  cap("Fig. 1. Architecture of Satya-Score (Version 2). Claims a structured source decides never reach the LLM."),

  h1("4. Main result"),
  p("Version 1 (sources plus the inference model) and Version 2 (plus the LLM cross-check) were compared once on 620 held-out items from seven English and Hindi test sets: FEVER, Mu-SHROOM (English and Hindi), TruthfulQA, X-FACT Hindi rumours, and Hindi Wikipedia sentences with one number changed (as written and reworded). No label was written by the team."),
  tcap("Table 1. Held-out comparison (620 items: 374 false, 246 true)"),
  table([
    ["Measure", "Version 1", "Version 2", "Criterion fixed in advance", "Met"],
    ["False items caught", "95 (25%)", "176 (47%)", "at least 2× Version 1", "no (1.85×)"],
    ["False items passed as Verified", "83 (22%)", "23 (6%)", "at most half", "yes"],
    ["True items Verified", "137 (56%)", "139 (57%)", "at most 5 points lower", "yes"],
    ["False alarms on true items", "28 (11%)", "32 (13%)", "at most 3 points higher", "yes"],
  ], [2638, 1500, 1500, 2600, 1400], [1, 2, 4]),
  p("The gains in catches (92 newly caught, 11 lost) and in false items no longer passed as Verified are statistically significant (McNemar test, p < 0.001); the change in false alarms is not (p = 0.63; 95% interval −3.2 to +6.6 points). Catches rose 1.85× (95% interval 1.61–2.19), just short of the doubling set as the target, so Version 2 met three of the four criteria.", { after: 120 }),
  img("chart_caught.png", 600),
  cap("Fig. 2. Catches rose in every set, most in Hindi (Mu-SHROOM Hindi 7% → 45%, Hindi Wikipedia 3% → 39%)."),
  p("The costs fall on TruthfulQA, where false alarms rose from 18% to 27% because its answers are vague without their question, and on the reworded Hindi sentences (3% → 11%). On FEVER, false alarms fell from 13% to 7%."),

  h1("5. Why the agreement rule matters"),
  img("chart_ablation.png", 600),
  cap("Fig. 3. Removing the safeguards one at a time on the same 620 items (exploratory analysis made after the main result)."),
  p("Used alone, the LLM caught 86% of false items but raised false alarms on 28% of true ones. Requiring agreement with the evidence, ignoring “no evidence” reasons, and checking the passages before flagging brought false alarms down to 13% while keeping catches near double those of Version 1."),

  h1("6. Results of the other components"),
  tcap("Table 2. Structured sources and other components"),
  table([
    ["Component (test data)", "Result"],
    ["Official statistics (40 random countries, 137 altered and 137 true figures)", "137 of 137 altered figures caught; no true figure contradicted"],
    ["Published fact-checks (25 rumours, 15 true claims)", "0 wrong decisions; rumours caught rose from 3 to 10"],
    ["Wikidata decisions (40 relational claims)", "11 of 13 correct (pre-registered); 12 of 12 after a linking fix (exploratory)"],
    ["Knowledge-graph ablation, pre-registered (same 40 claims)", "AUC 0.704 → 0.784 (+0.080, 95% interval +0.003 to +0.189)"],
    ["Pronoun resolution (400 Wikipedia introductions)", "correctly resolved 93 → 277"],
    ["Marking wrong words, Mu-SHROOM span overlap (IoU)", "Hindi 0.010 → 0.189, English 0.114 → 0.184 (mark-all baseline 0.32 / 0.31)"],
  ], [5038, 4600]),
  tcap("Table 3. Speed on the laptop (RTX 4050 GPU)"),
  table([
    ["Configuration", "First check", "Same text again"],
    ["Version 1, 6 claims (English)", "5.1 s", "0.7 s"],
    ["Version 2, laptop LLM only, 6 claims", "45.7 s", "under 3 s"],
    ["Version 2, Groq cloud first, 5 claims", "18.2 s", "2.7 s"],
    ["Version 2, Groq then OpenRouter, 6 claims", "27.3 s", "1.1 s"],
  ], [5238, 2200, 2200], [1, 2]),

  h1("7. How it was tested"),
  ...bul([
    "Models and settings were chosen on development data only; the LLM won a bake-off fixed in advance (gpt-oss-20b: balanced accuracy 57%, false alarms 7%).",
    "Four held-out rounds were run, each on a new sample and each once (201, 175, 162 and 620 items); rounds 1 and 3 failed their criteria and are reported. Every criterion and change was recorded in the project’s protocol file before the run.",
    "System quality: 323 automated tests pass; all 56 references verified against Crossref and arXiv; text overlap with published papers 0.0% (8-word runs).",
  ]),

  h1("8. Limitations"),
  ...bul([
    "About half of the false items are still not caught; when the readers disagree the claim is left Uncertain on purpose.",
    "The target of doubling the catches was narrowly missed (1.85×), so the cross-check is offered as a mode rather than the default.",
    "Test sets are modest (at most 60 true and 60 false items per set); constructed Hindi errors change only one number.",
    "On the laptop a check takes 15–45 seconds; a hosted model would remove most of this time.",
  ]),
  p([run("Further reading: ", { bold: true }), "the full IEEE-format paper (SatyaScore_IEEE_Paper_v2), the project report and the protocol of every test are available from the authors."], { after: 0 }),
];

const doc = new Document({
  styles: { default: { document: { run: { font: F, size: 22 } } } },
  numbering: { config: [
    { reference: "steps", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 300 } } } }] },
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 260 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new TextRun({ text: "Satya-Score results · page ", font: F, size: 18, color: "666666" }), new TextRun({ font: F, size: 18, color: "666666", children: [PageNumber.CURRENT] })] })] }) },
    children: content,
  }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(OUT, b); console.log("wrote", OUT); });
