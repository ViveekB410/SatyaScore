// IEEE conference paper (two-column, US Letter, 10 pt Times) for Satya-Score Version 2.
// Numbers: results/v2_results_final.md (620-item held-out sample), results/v2_data_PROTOCOL.md (rounds, bake-off),
// scratchpad/paper/ablate.py (exploratory ablations, McNemar, bootstrap), and the v1 paper for components kept from v1.
// Usage: node ieee_paper_v2.js <out.docx>
const fs = require("fs");
const path = require("path");
const OLD = "C:\\Users\\vivek\\AppData\\Local\\Temp\\claude\\C--Users-vivek-Downloads-satyascore\\b4965359-c236-491c-9218-9ec55611bd1a\\scratchpad\\docgen";
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType, WidthType, BorderStyle,
  SectionType, LevelFormat, ImageRun,
} = require(path.join(OLD, "node_modules", "docx"));

const OUT = process.argv[2];
const HERE = __dirname;
const F = "Times New Roman";
const COLW = 5040; // 3.5" column

// ---------- references ----------
const src = fs.readFileSync(path.join(OLD, "synopsis_updated.js"), "utf8");
const REFS = Function(`return ${src.match(/const REFS = (\{[\s\S]*?\n\});/)[1]}`)();
Object.assign(REFS, {
  safe: "J. Wei et al., \u201cLong-form factuality in large language models,\u201d arXiv:2403.18802, 2024.",
  alignscore: "Y. Zha, Y. Yang, R. Li, and Z. Hu, \u201cAlignScore: Evaluating factual consistency with a unified alignment function,\u201d in Proc. ACL, 2023, pp. 11328\u201311348.",
  ji: "Z. Ji et al., \u201cSurvey of hallucination in natural language generation,\u201d ACM Comput. Surv., vol. 55, no. 12, 2023.",
  gptoss: "OpenAI, \u201cgpt-oss-120b & gpt-oss-20b model card,\u201d arXiv:2508.10925, 2025, doi: 10.48550/arXiv.2508.10925.",
  xfact: "A. Gupta and V. Srikumar, \u201cX-FACT: A new benchmark dataset for multilingual fact checking,\u201d in Proc. ACL-IJCNLP (Short Papers), 2021, pp. 675\u2013682, doi: 10.18653/v1/2021.acl-short.86.",
  judge: "L. Zheng et al., \u201cJudging LLM-as-a-judge with MT-Bench and Chatbot Arena,\u201d in Proc. NeurIPS (Datasets and Benchmarks Track), 2023.",
  ollama: "Ollama. [Online]. Available: https://ollama.com",
});
const ORDER = [];
const cite = (s) => s.replace(/\{([a-z0-9,]+)\}/g, (_, keys) => keys.split(",").map(k => {
  if (!REFS[k]) throw new Error("unknown reference " + k);
  if (!ORDER.includes(k)) ORDER.push(k);
  return `[${ORDER.indexOf(k) + 1}]`;
}).join(", "));

// ---------- text helpers ----------
const run = (t, o = {}) => new TextRun({ text: cite(t), font: o.font || F, size: o.size || 20, bold: o.bold, italics: o.italics, smallCaps: o.smallCaps });
const runs = (parts, o = {}) => (Array.isArray(parts) ? parts : [parts]).map(t => typeof t === "string" ? run(t, o) : t);
const body = (parts, o = {}) => new Paragraph({ alignment: o.align || AlignmentType.JUSTIFIED, spacing: { after: o.after ?? 40, line: 230 },
  indent: o.noIndent ? undefined : { firstLine: 202 }, keepNext: o.keepNext, children: runs(parts) });
const roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"];
let secNo = 0, subNo = 0;
const sec = (t) => { subNo = 0; return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 140, after: 70 }, keepNext: true,
  children: [run(`${roman[secNo++]}. ${t}`, { smallCaps: true })] }); };
const secPlain = (t) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 140, after: 70 }, keepNext: true, children: [run(t, { smallCaps: true })] });
const sub = (t) => new Paragraph({ spacing: { before: 70, after: 30 }, keepNext: true, children: [run(`${"ABCDEFG"[subNo++]}. ${t}`, { italics: true })] });
const item = (parts) => new Paragraph({ numbering: { reference: "contrib", level: 0 }, alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 30, line: 230 }, children: runs(parts) });
const eq = (t, n) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 40, after: 60 },
  children: [run(t, { italics: true }), run(`\t(${n})`)], tabStops: [{ type: "right", position: COLW }] });

const thin = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
let tabNo = 0;
function ieeeTable(caption, rows, widths) {
  const n = rows.length;
  if (widths.reduce((a, b) => a + b, 0) !== COLW) throw new Error("widths of " + caption);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 100, after: 0 }, keepNext: true, children: [run(`TABLE ${roman[tabNo++]}`, { size: 16 })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 50 }, keepNext: true, children: [run(caption, { size: 16, smallCaps: true })] }),
    new Table({ width: { size: COLW, type: WidthType.DXA }, columnWidths: widths,
      rows: rows.map((cells, i) => new TableRow({ cantSplit: true, children: cells.map((c, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA },
        borders: { top: i === 0 ? thin : none, bottom: i === 0 || i === n - 1 ? thin : none, left: none, right: none },
        margins: { top: 20, bottom: 20, left: 50, right: 50 },
        children: [new Paragraph({ alignment: j === 0 ? AlignmentType.LEFT : AlignmentType.CENTER, spacing: { line: 200 }, keepNext: i < n - 1,
          children: [run(c, { size: 15, bold: i === 0 })] })] })) })) }),
    new Paragraph({ spacing: { after: 70 }, children: [] }),
  ];
}
// Algorithm box: one bordered cell, numbered lines
function algorithm(title, lines) {
  const box = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
  return [
    new Table({ width: { size: COLW, type: WidthType.DXA }, columnWidths: [COLW], rows: [new TableRow({ cantSplit: true, children: [new TableCell({
      width: { size: COLW, type: WidthType.DXA }, borders: { top: box, bottom: box, left: box, right: box },
      margins: { top: 60, bottom: 60, left: 90, right: 90 },
      children: [new Paragraph({ spacing: { after: 40 }, keepNext: true, children: [run("Algorithm 1. ", { size: 16, bold: true }), run(title, { size: 16 })] }),
        ...lines.map((l, i) => new Paragraph({ spacing: { line: 200, after: 0 }, keepNext: i < lines.length - 1,
          indent: { left: 300 + 220 * (l.match(/^ */)[0].length / 2), hanging: 300 },
          children: [run(`${i + 1}:\t`, { size: 15 }), run(l.trim(), { size: 15 })], tabStops: [{ type: "left", position: 300 }] }))],
    })] })] }),
    new Paragraph({ spacing: { after: 80 }, children: [] }),
  ];
}
function figure(file, widthPx, caption) {
  const buf = fs.readFileSync(path.join(HERE, file));
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  return [new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 80, after: 40 },
      children: [new ImageRun({ type: "png", data: buf, transformation: { width: widthPx, height: Math.round(widthPx * h / w) } })] }),
    new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 100 }, children: [run(caption, { size: 16 })] })];
}

// ---------- title block ----------
const AUTH = ["Vivek Yeshwantrao Borkar", "Piyush Devidas Nande", "Aasawari Sahebrao Jumade", "Arunima Tridip Wankhade", "R. R. Karwa"];
const AFF = "Dept. of Artificial Intelligence and Data Science, Prof. Ram Meghe Institute of Technology & Research, Badnera-Amravati, India";
const titleSection = {
  properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1440, left: 900, right: 900 } } },
  children: [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: [run("Satya-Score: An AI Hallucination Detection & Scoring Framework", { size: 48 })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 30 }, children: [run(AUTH.join(", "), { size: 22 })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 30 }, children: [run(AFF, { size: 18, italics: true })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [run("[e-mail addresses of the authors]", { size: 18 })] }),
  ],
};

// ---------- content ----------
const content = [
  body([run("Abstract", { bold: true, italics: true, size: 18 }), run("\u2014Large language model (LLM) answers read well yet may contain falsehoods, and Hindi has little tooling to find them. Satya-Score checks English and Hindi text one claim at a time. A claim is first sent to official statistics (World Bank, WHO), the Wikidata knowledge graph or published fact-checks. When none of them decides it, two independent readers must agree: Wikipedia passages assessed by a multilingual inference model, and an open-weight LLM (gpt-oss-20b, run on a laptop). A claim is Verified only when the passages support it and the LLM agrees, and Hallucinated only when the LLM finds it false and the retrieved passages, read again, do not state it. Every verdict names its evidence, gives the correct value when a structured source decides, and marks the wrong words. On a held-out sample of 620 items from seven English and Hindi test sets drawn from FEVER, Mu-SHROOM, TruthfulQA, X-FACT and Hindi Wikipedia, evaluated once, the cross-check caught 47% of false items against 25% for the same system without it (p < 0.001), let 6% of them pass as Verified against 22%, kept 57% of true items Verified (56% before) and raised false alarms on 13% of true items against 11% (difference not significant). The LLM alone caught 86% but flagged 28% of true items. The gain in catches (1.85\u00d7) fell just short of the doubling fixed in advance as the adoption criterion; this result and the earlier failed rounds are reported in full. Structured sources remain the most dependable part: altered country statistics were caught in all 137 cases, and a pre-registered ablation showed the knowledge graph lifting AUC from 0.704 to 0.784.", { bold: true, size: 18 })], { noIndent: true, after: 60 }),
  body([run("Index Terms", { bold: true, italics: true, size: 18 }), run("\u2014LLM hallucination, claim verification, knowledge graphs, natural language inference, LLM-as-a-judge, Hindi NLP, explainable fact-checking.", { bold: true, size: 18 })], { noIndent: true, after: 100 }),

  sec("Introduction"),
  body("Assistants such as those based on Llama {llama3} are now asked about medicine, government schemes and history. They compose the most probable continuation of a prompt instead of consulting a record of facts, and so they sometimes state invented or incorrect details with full confidence, the behaviour known as hallucination {ji,huang}. The fault is usually confined to one statement inside an otherwise sound answer, which is why checking has to happen per claim and has to point to evidence {factscore}. Nearly all available checkers handle English, even though Hindi, with several hundred million speakers, turns up more and more often in chatbot replies."),
  body("Our first system routed each claim to official statistics, a knowledge graph, published fact-checks and, failing those, Wikipedia passages judged by an inference model. It rarely raised false alarms, but text evidence exposed few hallucinations: an inference model accepts a passage that merely discusses a topic as support. Asking an LLM instead found many more hallucinations but flagged almost four times as many true claims. This paper describes the second version, which lets the two disagree safely. The paper contributes:"),
  item("An agreement-gated LLM cross-check: the LLM can neither verify nor flag a claim on its own. Verified needs passage support and the LLM\u2019s agreement; Hallucinated needs the LLM to name a wrong fact, not merely missing evidence, and a second, passages-only reading that does not state the claim."),
  item("Source routing kept from the first version: each claim goes to the most trustworthy source that covers it (statistics, knowledge graph, fact-check, text), the verdict names that source, and the wrong words are marked in the text."),
  item("An evaluation with acceptance criteria fixed in advance, on public English and Hindi sets plus Hindi sets built for this study, in which every held-out sample was used once and all rounds, including those that failed, are reported, together with ablations."),
  item("A system that runs on a student laptop with open-weight models only, so that no checked text has to leave the machine."),

  sec("Related Work"),
  body("The FEVER dataset {fever} made verification of claims against Wikipedia a standard task, and X-FACT {xfact} extended fact-checking to 25 languages including Hindi. For model output, FActScore {factscore} breaks long answers into atomic facts and looks each up in Wikipedia, while SAFE {safe} has an LLM agent search the web for every fact; both are English-only and lean on large models. SelfCheckGPT {selfcheck} compares several sampled answers, so an error the model makes consistently goes unnoticed. AlignScore {alignscore} and MiniCheck {minicheck} decide whether a supplied document backs a sentence, and inference models are known to mistake lexical overlap for support {mccoy}. Using a strong LLM as a judge approximates human judgements in many tasks {judge}, yet a judge shares the blind spots of the model family it belongs to. SemEval-2025 Mu-SHROOM {mushroom} asked teams to mark hallucinated spans in 14 languages, Hindi included, and BHRAM-IL {bhramil} quantifies hallucination rates across Indian languages. Graph-based work includes FactKG {factkg}, KGR {kgr} and the multilingual benchmark MultiHal {multihal}; reviews describe the value of graphs as promising yet not established {agrawal,lavrinovics}. Retrieval-augmented generation {rag} grounds text while it is written, which does not help when auditing what an external chatbot has already said. We are not aware of a checker that combines structured sources, published fact-checks and an LLM whose vote counts only together with retrieved evidence, for both English and Hindi."),

  sec("System"),
  body("Fig. 1 shows the architecture. Steps A\u2013C and the scoring in E come from the first version; the cross-check in D is new."),
  ...figure("fig1_architecture_v2.png", 318, "Fig. 1. Architecture of Satya-Score. Claims that a structured source or a fact-check decides never reach the LLM."),
  sub("Claim Extraction"),
  body("For English we use the spaCy dependency parser {spacy}. Coordinated statements become separate claims, each list entry becomes a claim, and a pronoun is resolved to the topic of the passage instead of the closest name; in a pre-registered test on 400 held-out Wikipedia introductions this increased correct resolutions from 93 to 277. Hindi input is segmented into sentences by the Indic NLP Library {indicnlp}. Questions, greetings and advice are recognised and left unchecked."),
  sub("Retrieval and Inference"),
  body("An XLM-R multilingual sentence encoder {sbertml,xlmr} maps claims and passages to vectors, and FAISS {faiss} searches an index of 102,069 Wikipedia passages (89,594 English, 12,475 Hindi) that grows when a relevant article is missing. Up to ten nearest passages whose cosine similarity reaches 0.3 go to an mDeBERTa-v3 classifier {debertav3} trained on MultiNLI and XNLI {mnli,xnli}, which returns an entailment probability e(p) and a contradiction probability c(p) per passage. They are combined as"),
  eq("s = 0.5 + 0.5 max e(p),   if max e(p) \u2265 0.5", 1),
  eq("s = 0.5 + 0.5 (max e(p) \u2212 max c(q)),  q on-topic,  otherwise", 2),
  body("where a passage counts as on-topic if the title of its article occurs in the claim. Support may therefore come from anywhere, but refutation only from text about the claim\u2019s own subject."),
  sub("Structured Sources"),
  body("A claim on a country\u2019s population, GDP, life expectancy, literacy or infant mortality is checked against World Bank figures {worldbank} and, for the two health indicators, WHO figures {who}; the comparison respects the precision in which the claim is stated, and if both agencies hold a value their verdicts must coincide. Relations such as birth and death places and dates, founding dates, capitals, authorship, office-holders, quantities and currencies are looked up in Wikidata {wikidata} through templates for both languages. When a name is shared by several entities, one match suffices for support, while refutation needs disagreement from all namesakes that have a value. Published fact-checks are retrieved with the Google Fact Check Tools API {googlefc}; a \u201cfalse\u201d rating transfers to our claim only when the claim entails the checked statement, a \u201ctrue\u201d rating only when the reverse entailment holds."),
  sub("LLM Cross-Check"),
  body("Every claim that no structured source or fact-check decided is shown to gpt-oss-20b {gptoss}, an open-weight mixture-of-experts model (21B parameters, 3.6B active per token, Apache 2.0), which we run with Ollama {ollama} on the laptop that serves the system. The first reading gives the model the claim and the five best passages (600 characters each) and allows it to use its own knowledge; it returns a JSON object with a verdict (Verified, Uncertain or Hallucinated), a probability that the claim is true, the wrong words copied from the claim, and a one-sentence reason. Decoding is greedy. The verdict j is combined with the passage score s by the rule of Fig. 2 and Algorithm 1."),
  body("The rule has three safeguards, each introduced after a failure described in Section V-C. First, an LLM verdict of Hallucinated whose reason only says that the passages do not mention the fact (\u201cno evidence\u201d, \u201cnot stated\u201d) counts as Uncertain, since missing evidence is not proof of falsehood. Second, a passage contradiction alone never flags a claim; the LLM must say it is false. Third, before a claim is flagged, a second reading asks the same model, now restricted to the passages, whether all ten retrieved passages state the claim; if they do, the claim becomes Uncertain. The second reading is also used in the opposite direction: a claim left Uncertain although one reader judged it true becomes Verified if the ten passages state it. The LLM therefore never decides alone, and a claim the structured sources decided is never sent to it."),
  ...figure("fig2_decision_v2.png", 318, "Fig. 2. Decision for a claim that no structured source or fact-check decided. s: passage score (1)\u2013(2); j: first LLM reading; the second reading uses only the ten retrieved passages."),
  ...algorithm("Verdict for one claim c", [
    "if a statistic, Wikidata or a fact-check decides c then return that verdict and the correct value",
    "s \u2190 passage score over the top-10 passages of c        \u25b7 (1)\u2013(2)",
    "j \u2190 LLM(c, top-5 passages, own knowledge)",
    "if j = Hallucinated and its reason only cites missing evidence then j \u2190 Uncertain",
    "if s > 0.65 and j = Verified then v \u2190 Verified",
    "else if j = Hallucinated and s \u2264 0.65 then",
    "  v \u2190 Uncertain if LLM_passages(c, top-10) = Verified, else Hallucinated",
    "else if j \u2260 Hallucinated and (s > 0.65 or j = Verified) then",
    "  v \u2190 Verified if LLM_passages(c, top-10) = Verified, else Uncertain",
    "else v \u2190 Uncertain",
    "score \u2190 mean(s, P_LLM(true)) clamped to the band of v",
    "mark the wrong value (Wikidata), else the LLM\u2019s wrong words, else the whole claim",
  ]),
  sub("Scoring and Explanation"),
  body("The Composite Multilingual Hallucination Scoring Algorithm (CMHSA) of the first version has the form HalluScore = \u03b1\u00b7SemSim + \u03b2\u00b7NLI + \u03b3\u00b7KG, with per-language softmax weights; since similarity reflects topic and not truth, \u03b1 is set to 0, and training gives \u03b2 \u2248 \u03b3 \u2248 0.5. In operation the first available source decides: a statistics or Wikidata answer yields 1.0 or 0.0, an applicable fact-check 0.05 or 0.95, and otherwise the cross-check sets the verdict and the score as in Algorithm 1. Scores under 0.35 mean Hallucinated, scores over 0.65 Verified, and the middle range Uncertain; a whole text is labelled Hallucinated once a third or more of its claims are. The web application underlines the wrong words of each flagged claim and shows the deciding source, the LLM\u2019s reason and, for structured sources, the correct value. Table I shows outputs of the running system."),
  ...ieeeTable("Outputs of the running system", [
    ["Claim", "Verdict", "Deciding evidence"],
    ["The Eiffel Tower ... was completed in 1925.", "Halluc.", "passages contradict; LLM: finished in 1889; \u201ccompleted in 1925\u201d marked"],
    ["The Great Wall of China is visible from the Moon with the naked eye.", "Halluc.", "passages contradict; LLM: a myth"],
    ["Albert Einstein developed the theory of relativity.", "Verified", "passages and LLM agree"],
    ["\u092d\u093e\u0930\u0924 \u0915\u0940 \u0930\u093e\u091c\u0927\u093e\u0928\u0940 \u092e\u0941\u0902\u092c\u0908 \u0939\u0948\u0964 (India\u2019s capital is Mumbai)", "Halluc.", "Wikidata; correct: New Delhi"],
    ["Mahatma Gandhi was born in Delhi.", "Halluc.", "Wikidata; correct: Porbandar"],
    ["\u092f\u0942\u0928\u0947\u0938\u094d\u0915\u094b \u0928\u0947 \u0928\u0930\u0947\u0902\u0926\u094d\u0930 \u092e\u094b\u0926\u0940 \u0915\u094b \u0926\u0941\u0928\u093f\u092f\u093e \u0915\u093e \u0938\u0930\u094d\u0935\u0936\u094d\u0930\u0947\u0937\u094d\u0920 \u092a\u094d\u0930\u0927\u093e\u0928\u092e\u0902\u0924\u094d\u0930\u0940 \u0918\u094b\u0937\u093f\u0924 \u0915\u093f\u092f\u093e \u0939\u0948\u0964 (UNESCO declared Modi the best PM)", "Halluc.", "Fact-check (Vishvas News): False"],
  ], [2340, 700, 2000]),

  sec("Experimental Setup"),
  sub("Data"),
  body("Table II lists the data. The cross-check was evaluated on seven sets in which no label was written by us. FEVER {fever} supplies supported and refuted English claims. Mu-SHROOM {mushroom} supplies chatbot answers with human-marked hallucinated spans; we extract claims and label a claim false if it overlaps a marked span by at least three characters, dropping claims with one or two overlapping characters. TruthfulQA {truthfulqa} supplies the best answer and the first incorrect answer to each question, both stated without the question. X-FACT {xfact} supplies Hindi rumours rated false by professional fact-checkers. For Hindi Wikipedia, true items are sentences taken from articles and false items are the same sentences with one number changed; a reworded set paraphrases the true sentences with a different LLM (qwen3.8-27b), keeps a paraphrase only if inference in both directions reaches 0.80 and all numbers survive, and changes one of its numbers for the false item. Each set has a development split and a locked test split, and items were drawn at random, up to 60 true and 60 false per set and language."),
  ...ieeeTable("Evaluation data", [
    ["Set", "Lang.", "True / false", "Labels"],
    ["Held-out sample (v1 vs. v2), 620 items", "", "", ""],
    ["  FEVER", "EN", "60 / 60", "FEVER annot."],
    ["  Mu-SHROOM claims", "EN", "52 / 60", "human spans"],
    ["  Mu-SHROOM claims", "HI", "0 / 60", "human spans"],
    ["  TruthfulQA answers", "EN", "60 / 60", "TruthfulQA"],
    ["  X-FACT rumours", "HI", "0 / 60", "fact-checkers"],
    ["  Hindi Wikipedia", "HI", "38 / 38", "construction"],
    ["  Hindi Wikipedia, reworded", "HI", "36 / 36", "construction"],
    ["Components (first version)", "", "", ""],
    ["  Chatbot claims", "EN/HI", "456", "4 annotators"],
    ["  Relational claims", "EN", "25 / 15", "2 annotators"],
    ["  Country statistics", "\u2013", "137 / 137", "construction"],
    ["  Fact-check set", "EN/HI", "15 / 25", "fact-checkers"],
  ], [2240, 600, 1000, 1200]),
  body("The 456 chatbot claims come from answers of Llama 3.3 (70B) in five domains. An AI system proposed a verdict for every claim, and a team of four annotators, the authors, confirmed or overrode each proposal; 79% of the final labels coincide with the proposal. In a blind study two people labelled 56 claims with \u03ba = 0.53 (88% raw agreement). These claims were used while the cross-check was developed and are therefore not used to report it."),
  sub("Protocol and Measures"),
  body("All choices were made on development data or on earlier held-out samples, never on the final one. The LLM was chosen in a bake-off on 202 development items fixed in advance: gpt-oss-20b reached the highest balanced accuracy under the cross-check (57%, false alarms 7%), ahead of gpt-oss-120b (56%, 10%); qwen3.8-27b answered fewer than 90% of the items and was excluded by rule. Held-out samples were drawn from the locked test splits, no item twice, and each was run once for both systems. Before each run we recorded the configuration and the acceptance criterion; the final criterion required, relative to the first version (v1), at least twice as many catches, at most half as many false items passed as Verified, false alarms at most 3 points higher, and true items Verified at most 5 points lower. A catch is a false item labelled Hallucinated and a false alarm a true item labelled Hallucinated; Uncertain is never counted as correct. Paired differences are tested with exact McNemar tests and ratios with a bootstrap over items (2,000 resamples). For Mu-SHROOM we also report the official character-level IoU between marked and gold spans."),

  sec("Results"),
  sub("Held-out Comparison"),
  body("Table III gives the final comparison on 620 held-out items. With the cross-check the system caught 176 of 374 false items instead of 95 (McNemar: 92 newly caught, 11 lost, p < 0.001) and passed 23 of them as Verified instead of 83 (p < 0.001). Among the 246 true items, 139 were Verified instead of 137 and 32 were flagged instead of 28; neither change is significant (p = 0.87 and 0.63; false-alarm difference +1.6 points, 95% CI \u22123.2 to +6.6). Three of the four criteria were met. Catches rose by a factor of 1.85 (95% CI 1.61\u20132.19), short of the required 2, so by our own rule the second version was not adopted on this sample. We report it because the measured trade-off is useful in its own right and because the criterion was fixed before the run."),
  ...ieeeTable("Held-out sample: first version (v1) vs. cross-check (v2)", [
    ["Measure", "v1", "v2", "Criterion", "Met"],
    ["False items caught", "95/374 (25%)", "176/374 (47%)", "\u2265 2\u00d7 v1", "no (1.85\u00d7)"],
    ["False items passed as Verified", "83/374 (22%)", "23/374 (6%)", "\u2264 \u00bd v1", "yes"],
    ["True items Verified", "137/246 (56%)", "139/246 (57%)", "\u2265 v1 \u2212 5", "yes"],
    ["False alarms", "28/246 (11%)", "32/246 (13%)", "\u2264 v1 + 3", "yes"],
  ], [1440, 900, 900, 900, 900]),
  body("Table IV breaks the result down by set. Gains are largest where the first version relied on weak text evidence: Hindi Wikipedia items with a changed number (caught 3% \u2192 39%), Mu-SHROOM Hindi answers (7% \u2192 45%) and TruthfulQA misconceptions (17% \u2192 43%). On FEVER the cross-check caught more and also flagged fewer true claims, though it Verified slightly fewer (72% → 67%). The costs fall on TruthfulQA, where false alarms rose from 18% to 27% (the answers lack their question, so many are vague), and on the reworded Hindi sentences (3% \u2192 11%). X-FACT rumours were already caught by published fact-checks; without that source the first version caught only 5% of them."),
  ...ieeeTable("Per set, v1 \u2192 v2 (percent of items)", [
    ["Set (true/false)", "Caught", "Passed as Ver.", "False alarm"],
    ["FEVER EN (60/60)", "37 \u2192 62", "20 \u2192 5", "13 \u2192 7"],
    ["Hindi Wikipedia (38/38)", "3 \u2192 39", "13 \u2192 5", "0 \u2192 0"],
    ["Hindi Wiki., reworded (36/36)", "28 \u2192 47", "33 \u2192 0", "3 \u2192 11"],
    ["Mu-SHROOM EN (52/60)", "13 \u2192 20", "23 \u2192 15", "15 \u2192 15"],
    ["Mu-SHROOM HI (0/60)", "7 \u2192 45", "38 \u2192 5", "\u2013"],
    ["TruthfulQA EN (60/60)", "17 \u2192 43", "27 \u2192 8", "18 \u2192 27"],
    ["X-FACT HI (0/60)", "67 \u2192 70", "2 \u2192 2", "\u2013"],
  ], [1740, 1100, 1100, 1100]),
  sub("Ablation"),
  body("Table V removes the parts of the rule one at a time, using the answers already cached for the 620 items (exploratory: this analysis was made after the result above). The LLM alone catches most false items but flags 28% of true ones. Requiring agreement with the passages lowers false alarms to 22%; the no-evidence filter lowers them to 16% at the cost of catches; the second reading restores the true claims Verified (47% \u2192 57%); and requiring the LLM to say false, with the passages-only check before flagging, brings false alarms to 13%."),
  ...ieeeTable("Ablation on the held-out sample (exploratory)", [
    ["Variant", "Caught", "Passed", "True Ver.", "False al."],
    ["v1 (no LLM)", "25%", "22%", "56%", "11%"],
    ["LLM alone", "86%", "11%", "65%", "28%"],
    ["Agreement rule only", "68%", "4%", "47%", "22%"],
    ["+ no-evidence filter", "49%", "4%", "47%", "16%"],
    ["+ second reading", "49%", "6%", "57%", "16%"],
    ["+ LLM must say false, check before flag (v2)", "47%", "6%", "57%", "13%"],
  ], [2240, 700, 700, 700, 700]),
  sub("Development Rounds"),
  body("The final rule is the fourth version tested on held-out data, each time on a fresh sample. The plain agreement rule (201 items) caught 58% against 20% but raised false alarms to 17% against 9% and failed the first criterion, an absolute limit of 5%; inspection showed the LLM calling claims false only because the passages did not mention them. That limit had been set when the first version\u2019s own rate on chatbot claims was 3\u20136%, while on these sets it is 9\u201312%, so the criterion was changed to one relative to v1 before the next run, and the no-evidence filter was added. The second round (175 items) caught 47% against 15% with equal false alarms (12%) and passed, but Verified only 40% of true items against 56%. Adding the second reading and the criterion on true items, the third round (162 items) caught 37% against 19% with false alarms of 14% against 5% and failed. The safeguards against flagging, chosen on the three used samples, gave the result of Table III. All held-out samples are now used up."),
  sub("Hallucinated Spans"),
  body("Table VI gives Mu-SHROOM span overlap for the answers in the held-out sample. Marking only the wrong words named by Wikidata or the LLM, instead of whole claims, raised Hindi IoU from 0.010 to 0.189 and English IoU from 0.114 to 0.184, still below marking every character and far below the best shared-task systems, which were built for span marking."),
  ...ieeeTable("Mu-SHROOM span IoU, held-out answers", [
    ["Method", "Hindi (52)", "English (72)"],
    ["v1, flagged claims", "0.010", "0.114"],
    ["v2, flagged claims", "0.097", "0.172"],
    ["v2, wrong words only", "0.189", "0.184"],
    ["Mark-all baseline", "0.318", "0.307"],
    ["Best team, full test set {mushroom}", "0.74", "0.65"],
  ], [2440, 1300, 1300]),
  sub("Structured Sources and Chatbot Claims"),
  body("The structured sources were evaluated for the first version and are unchanged. Altered country statistics were caught in all 137 cases and none of the 137 true figures was contradicted. In a pre-registered ablation on 40 relational claims, adding the knowledge graph to the inference score raised AUC from 0.704 to 0.784 (difference +0.080, 95% CI +0.003 to +0.189); 11 of its 13 pre-registered decisions were correct, and all 12 after a repair of place-name linking (exploratory). On a fact-check set of 40 claims no fact-check decision was wrong. On the labelled chatbot claims the first version flagged 9 of 258 true training claims but caught only 5 of 45 hallucinations, the observation that motivated the cross-check."),
  sub("Latency"),
  body("Without the LLM a six-claim English answer is checked in 5.1 s on an RTX 4050 laptop GPU (6 GB). With the cross-check the same kind of answer took 45.7 s, of which most is the LLM: the 13 GB model does not fit in GPU memory, so Ollama runs most of it on the CPU at about 4 s per reading, and claims decided by structured sources skip it. Allowing four parallel requests made the answer slower (202 s) on this hardware, so claims are read one at a time; repeated claims are answered from a cache. A hosted provider serving the same open weights would remove most of this time, which we did not measure."),

  sec("Discussion and Limitations"),
  body("Three findings stand out. First, an LLM is a strong but unreliable witness: alone it caught 86% of false items and flagged 28% of true ones, so its value lies in being combined with evidence, not in replacing it. Second, most of the improvement comes from claims that no structured source covers, especially in Hindi, where the inference model had found almost nothing. Third, each safeguard trades catches for fewer false alarms, and the final rule sits close to the first version\u2019s false-alarm rate while catching nearly twice as many false items; the doubling we required was missed by a small margin."),
  body("The study has limits. The constructed Hindi false items change a single number and are easier than real errors; Mu-SHROOM claim labels are derived from span overlap; TruthfulQA answers lack their question; and each set contributes at most 60 true and 60 false items, so per-set figures move by 2–3 points per item. The acceptance criterion was changed once after a failed run (reported above), and the final configuration was chosen on samples that had already been used. The LLM\u2019s knowledge has a cut-off date and it can share misconceptions with the chatbots it checks. Live look-ups require internet access, the cross-check is slow on a laptop, and the WHO data licence permits non-commercial use only."),

  sec("Conclusion"),
  body("Satya-Score checks English and Hindi answers claim by claim and supports every verdict with evidence that readers can inspect. Structured sources answer what they cover and give the correct value; for the rest, an open-weight LLM and retrieved passages must agree, which nearly doubled the hallucinations caught and cut those passed as Verified by three quarters at a cost of about two points in false alarms. Committing to criteria before each run showed both how much the LLM helps and where it does not yet meet the bar we set. Next steps are a larger Hindi test set labelled blind by two people, Marathi, and a faster deployment of the cross-check. The code and data can be obtained from the authors."),

  secPlain("Acknowledgment"),
  body("We are grateful to the Department of Artificial Intelligence and Data Science, PRMIT&R, for its support. AI tools were used for code assistance, for drafting the text of this manuscript and for drawing Figs. 1 and 2; AI also proposed the initial verdicts that the authors reviewed (Section IV-A). An open-weight LLM (gpt-oss-20b) is a component of the system (Section III-D), and another (qwen3.8-27b) reworded Hindi test sentences (Section IV-A). All experiments, labels and reported figures were checked by the authors, who take full responsibility for the content.", { noIndent: true }),
];

const refsBlock = () => [secPlain("References"),
  ...ORDER.map((k, i) => new Paragraph({ spacing: { after: 20, line: 200 }, indent: { left: 360, hanging: 360 }, alignment: AlignmentType.JUSTIFIED,
    tabStops: [{ type: "left", position: 360 }], children: [new TextRun({ text: `[${i + 1}]\t${REFS[k]}`, font: F, size: 16 })] }))];

const all = [...content, ...refsBlock()];
const doc = new Document({
  styles: { default: { document: { run: { font: F, size: 20 } } } },
  numbering: { config: [{ reference: "contrib", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1)",
    alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 260 } } } }] }] },
  sections: [titleSection, {
    properties: { type: SectionType.CONTINUOUS, column: { count: 2, space: 360, equalWidth: true },
      page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1440, left: 900, right: 900 } } },
    children: all,
  }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf);
  console.log("wrote", OUT, "| references:", ORDER.length); });
