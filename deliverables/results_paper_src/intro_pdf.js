// Satya-Score: short project introduction for the publisher (5 sections only). Usage: node intro_pdf.js <out.docx>
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, AlignmentType, LevelFormat, BorderStyle } = require("docx");
const OUT = process.argv[2];
const F = "Times New Roman";
const run = (t, o = {}) => new TextRun({ text: t, font: F, size: o.size || 24, bold: o.bold, italics: o.italics, color: o.color });
const p = (parts) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 140, line: 312 },
  children: (Array.isArray(parts) ? parts : [parts]).map(x => typeof x === "string" ? run(x) : x) });
const h = (t) => new Paragraph({ spacing: { before: 280, after: 120 }, keepNext: true,
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F5FBF", space: 2 } }, children: [run(t, { bold: true, size: 28, color: "1F3864" })] });
const item = (ref, parts) => new Paragraph({ numbering: { reference: ref, level: 0 }, alignment: AlignmentType.JUSTIFIED, spacing: { after: 90, line: 300 },
  children: (Array.isArray(parts) ? parts : [parts]).map(x => typeof x === "string" ? run(x) : x) });

const children = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [run("Satya-Score", { bold: true, size: 40, color: "1F3864" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [run("An AI Hallucination Detection & Scoring Framework", { italics: true, size: 26 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [run("Vivek Yeshwantrao Borkar, Piyush Devidas Nande, Aasawari Sahebrao Jumade, Arunima Tridip Wankhade · Guide: Dr. R. R. Karwa", { size: 20 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [run("Department of Artificial Intelligence and Data Science, Prof. Ram Meghe Institute of Technology & Research, Badnera-Amravati", { size: 20 })] }),

  h("1. Introduction"),
  p("Satya-Score (“satya” means truth) is a system that checks answers written by AI chatbots and finds the statements that are false. It works on English and Hindi text, one claim at a time. For every claim it gives a verdict (Verified, Uncertain or Hallucinated), the evidence behind that verdict, and the wrong words marked in the text; when an official source holds the fact, it also shows the correct value."),

  h("2. Need"),
  p("AI chatbots such as ChatGPT are now used for questions about health, education, government schemes and history. They write fluent and confident answers, but sometimes state facts that are invented or wrong, a problem known as hallucination."),
  item("bul", "The wrong fact is usually one sentence inside an otherwise correct answer, so readers easily miss it."),
  item("bul", "Checking every sentence by hand removes the benefit of using a chatbot."),
  item("bul", "Most existing checking tools work only in English and give one score for a whole answer, without saying which sentence is wrong or what the correct fact is."),
  item("bul", "Hindi, used by hundreds of millions of people, has almost no such tools."),

  h("3. What We Built"),
  p("A working web application in which a user pastes or uploads an AI answer in English or Hindi and receives, for each factual claim:"),
  item("bul", [run("a verdict: ", { bold: true }), run("Verified, Uncertain or Hallucinated, with a score;")]),
  item("bul", [run("the evidence: ", { bold: true }), run("the official figure, knowledge-graph fact, fact-check or Wikipedia passage that decided it;")]),
  item("bul", [run("the correction: ", { bold: true }), run("the wrong words underlined and, where available, the correct value;")]),
  item("bul", [run("an overall verdict ", { bold: true }), run("for the whole answer, with saved history and export for signed-in users.")]),
  p("All models used are open-source and run on a student laptop, so no answer has to leave the machine."),

  h("4. Novelty"),
  p([run("An AI model that can never decide alone. ", { bold: true }),
    run("Satya-Score combines official statistics, a knowledge graph, published fact-checks and an AI language model for English and Hindi, and lets the AI model’s verdict count only when the retrieved evidence agrees with it. Used alone, the same AI model wrongly flagged 28% of true claims as false; under this agreement rule, 13%.")]),
  item("bul", [run("Source routing with the correct value: ", { bold: true }), run("each claim is answered by the most trustworthy source that covers it, and a structured source also gives the right fact.")]),
  item("bul", [run("Claim-level checking in Hindi as well as English, ", { bold: true }), run("with the wrong words marked rather than whole sentences flagged.")]),
  item("bul", [run("Honest evaluation: ", { bold: true }), run("success criteria were fixed before testing and every result, including shortfalls, is reported.")]),

  h("5. Working"),
  item("num", [run("Split: ", { bold: true }), run("the answer is broken into separate factual claims (spaCy for English, with pronouns resolved; Indic NLP Library for Hindi).")]),
  item("num", [run("Trusted sources first: ", { bold: true }), run("each claim is checked against World Bank and WHO statistics, the Wikidata knowledge graph and published fact-checks. If one of them holds the fact, its answer is final and the correct value is shown.")]),
  item("num", [run("Two readers for the rest: ", { bold: true }), run("a multilingual inference model (mDeBERTa) reads the ten most relevant Wikipedia passages, and an open-source AI model (gpt-oss-20b) judges the claim.")]),
  item("num", [run("Agreement rule: ", { bold: true }), run("a claim is Verified only when both readers say it is true; it is Hallucinated only when the AI model names a wrong fact and a second reading of the passages does not support the claim; if the readers disagree, it is Uncertain.")]),
  item("num", [run("Explain: ", { bold: true }), run("the web application underlines each claim in its verdict colour, marks the wrong words, and shows the evidence and what each reader said.")]),
];

const doc = new Document({
  styles: { default: { document: { run: { font: F, size: 24 } } } },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
  ] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1247, right: 1247 } } }, children }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(OUT, b); console.log("wrote", OUT); });
