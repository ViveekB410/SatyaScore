// Satya-Score journal manuscript (single column, A4, Springer-style submission for J. Intelligent Information Systems).
// Numbers: results/v2_results_final.md (620-item held-out sample), the IEEE v2 paper (protocol, rounds, ablation, components),
// results paper (latency). New references: jpaper/newrefs.json (OpenAlex + Crossref metadata).
// Usage: node journal_paper.js <out.docx>
const fs = require("fs");
const path = require("path");
const OLD = "C:\\Users\\vivek\\AppData\\Local\\Temp\\claude\\C--Users-vivek-Downloads-satyascore\\b4965359-c236-491c-9218-9ec55611bd1a\\scratchpad\\docgen";
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType, WidthType, BorderStyle,
  LevelFormat, ImageRun, Footer, PageNumber, TabStopType,
} = require(path.join(OLD, "node_modules", "docx"));

const OUT = process.argv[2];
const HERE = __dirname;
const F = "Times New Roman";
const TW = 9026; // A4 text width with 1-inch margins

// ---------- references ----------
const src = fs.readFileSync(path.join(OLD, "synopsis_updated.js"), "utf8");
const REFS = Function(`return ${src.match(/const REFS = (\{[\s\S]*?\n\});/)[1]}`)();
const NEW = JSON.parse(fs.readFileSync(path.join(HERE, "newrefs.json"), "utf8"));
const initials = (full) => {
  const parts = full.replace(/\./g, ". ").split(/\s+/).filter(Boolean);
  const last = parts.pop();
  return parts.map(p => p.split("-").map(x => x[0].toUpperCase() + ".").join("-")).join(" ") + " " + last;
};
const authorList = (a) => a.length > 6 ? `${initials(a[0])} et al.` :
  a.length === 1 ? initials(a[0]) : a.length === 2 ? `${initials(a[0])} and ${initials(a[1])}` :
  a.slice(0, -1).map(initials).join(", ") + ", and " + initials(a[a.length - 1]);
const NEWT = { // sentence-case titles and journal abbreviations
  farquhar: ["Detecting hallucinations in large language models using semantic entropy", "Nature"],
  siren: ["Siren’s song in the AI ocean: A survey on hallucination in large language models", "Comput. Linguist."],
  augenstein: ["Factuality challenges in the era of large language models and opportunities for fact-checking", "Nat. Mach. Intell."],
  quelle: ["The perils and promises of fact-checking with large language models", "Front. Artif. Intell."],
  dunning: ["Large language models show Dunning-Kruger-like effects in multilingual fact-checking", "Sci. Rep."],
  multigran: ["Hallucination detection in large language models based on multi-granularity consistency", "J. Intell. Inf. Syst."],
  factualrag: ["FactualRAG: A RAG-powered framework for LLM fact-checking via IFCN-accredited sources", "J. Intell. Inf. Syst."],
  kqfv: ["KQFV: A knowledge-enhanced method using question answering for fact verification", "J. Intell. Inf. Syst."],
  mmrag: ["Multimodal misinformation detection across diverse languages using RAG and LLMs", "J. Intell. Inf. Syst."],
  lresurvey: ["Hallucinations in generative artificial intelligence and large language models: Tests, datasets, detection and correction methods", "Lang. Resour. Eval."],
  entityhi: ["Reward-driven fine-tuning with entity hallucination index for low-resource Hindi abstractive summarisation", "SN Comput. Sci."],
  inclusive: ["Towards inclusive fact-checking: Claim verification in English, Hindi, Bengali, and code-mixed languages", "Comput. Sist."],
  mmhfnd: ["MMHFND: Fusing modalities for multimodal multiclass Hindi fake news detection via contrastive learning", "ACM Trans. Asian Low-Resour. Lang. Inf. Process."],
  kgbert: ["Fact-checking Vietnamese information using knowledge graph, Datalog, and KG-BERT", "ACM Trans. Asian Low-Resour. Lang. Inf. Process."],
  synkg: ["Synonym knowledge graph enhanced language model for inconsistent hallucination detection", "ACM Trans. Asian Low-Resour. Lang. Inf. Process."],
};
for (const [k, [title, jr]] of Object.entries(NEWT)) {
  const r = NEW[k];
  const loc = [r.vol && `vol. ${r.vol}`, r.issue && `no. ${r.issue}`,
    r.fp && r.lp && r.fp !== r.lp ? `pp. ${r.fp}–${r.lp}` : (r.artno ? `Art. no. ${r.artno}` : null)].filter(Boolean).join(", ");
  REFS[k] = `${authorList(r.authors)}, “${title},” ${jr}${loc ? ", " + loc : ""}, ${r.year}, doi: ${r.doi}.`;
}
Object.assign(REFS, {
  safe: "J. Wei et al., “Long-form factuality in large language models,” arXiv:2403.18802, 2024.",
  alignscore: "Y. Zha, Y. Yang, R. Li, and Z. Hu, “AlignScore: Evaluating factual consistency with a unified alignment function,” in Proc. ACL, 2023, pp. 11328–11348.",
  ji: "Z. Ji et al., “Survey of hallucination in natural language generation,” ACM Comput. Surv., vol. 55, no. 12, 2023.",
  gptoss: "OpenAI, “gpt-oss-120b & gpt-oss-20b model card,” arXiv:2508.10925, 2025, doi: 10.48550/arXiv.2508.10925.",
  xfact: "A. Gupta and V. Srikumar, “X-FACT: A new benchmark dataset for multilingual fact checking,” in Proc. ACL-IJCNLP (Short Papers), 2021, pp. 675–682, doi: 10.18653/v1/2021.acl-short.86.",
  judge: "L. Zheng et al., “Judging LLM-as-a-judge with MT-Bench and Chatbot Arena,” in Proc. NeurIPS (Datasets and Benchmarks Track), 2023.",
  ollama: "Ollama. [Online]. Available: https://ollama.com",
});
const ORDER = [];
const cite = (s) => s.replace(/\{([a-z0-9,]+)\}/g, (_, keys) => "[" + keys.split(",").map(k => {
  if (!REFS[k]) throw new Error("unknown reference " + k);
  if (!ORDER.includes(k)) ORDER.push(k);
  return ORDER.indexOf(k) + 1;
}).join(", ") + "]");

// ---------- text helpers ----------
const run = (t, o = {}) => new TextRun({ text: cite(t), font: F, size: o.size || 22, bold: o.bold, italics: o.italics,
  superScript: o.sup, subScript: o.sub, color: o.color });
const R = (parts, o = {}) => (Array.isArray(parts) ? parts : [parts]).map(t => typeof t === "string" ? run(t, o) : t);
const b = (t) => run(t, { bold: true });
const i = (t) => run(t, { italics: true });
const P = (parts, o = {}) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: o.after ?? 120, line: 300 },
  indent: o.indent === false ? undefined : (o.first ? undefined : { firstLine: 340 }), keepNext: o.keepNext, children: R(parts) });
const P0 = (parts, o = {}) => P(parts, { ...o, indent: false });
let s1 = 0, s2 = 0;
const H1 = (t) => { s1++; s2 = 0; return new Paragraph({ spacing: { before: 300, after: 120 }, keepNext: true, children: [run(`${s1} ${t}`, { bold: true, size: 26 })] }); };
const H2 = (t) => { s2++; return new Paragraph({ spacing: { before: 200, after: 90 }, keepNext: true, children: [run(`${s1}.${s2} ${t}`, { bold: true, size: 23 })] }); };
const Hn = (t) => new Paragraph({ spacing: { before: 300, after: 120 }, keepNext: true, children: [run(t, { bold: true, size: 26 })] });
const LI = (parts, ref = "bul") => new Paragraph({ numbering: { reference: ref, level: 0 }, alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 70, line: 290 }, children: R(parts) });
const SB = (t) => run(t, { italics: true, sub: true });
const EQ = (parts, n) => new Paragraph({ spacing: { before: 80, after: 120 }, tabStops: [{ type: TabStopType.CENTER, position: TW / 2 }, { type: TabStopType.RIGHT, position: TW }],
  children: [run("\t"), ...R(parts, { italics: true }), run(`\t(${n})`)] });

const rule = { style: BorderStyle.SINGLE, size: 8, color: "000000" };
const thin = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
let tabNo = 0, figNo = 0;
// Three-line (booktabs) table, caption above
function TABLE(caption, rows, widths, o = {}) {
  if (widths.reduce((a, c) => a + c, 0) !== TW) throw new Error("widths of " + caption + " = " + widths.reduce((a, c) => a + c, 0));
  const n = rows.length, sub = o.groupRows || [];
  tabNo++;
  return [
    new Paragraph({ spacing: { before: 200, after: 80 }, keepNext: true, children: [run(`Table ${tabNo} `, { bold: true, size: 20 }), run(caption, { size: 20 })] }),
    new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: widths,
      rows: rows.map((cells, r) => new TableRow({ cantSplit: true, tableHeader: r === 0, children: cells.map((c, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA },
        borders: { top: r === 0 ? rule : none, bottom: r === 0 ? thin : (r === n - 1 ? rule : none), left: none, right: none },
        margins: { top: 45, bottom: 45, left: 80, right: 80 },
        children: [new Paragraph({ alignment: (o.left || [0]).includes(j) ? AlignmentType.LEFT : AlignmentType.CENTER, keepNext: r < n - 1,
          children: R(c, { size: 19, bold: r === 0 || (o.boldRows || []).includes(r), italics: sub.includes(r) }) })] })) })) }),
    ...(o.note ? [new Paragraph({ spacing: { before: 50, after: 60 }, children: [run(o.note, { size: 18 })] })] : []),
    new Paragraph({ spacing: { after: 100 }, children: [] }),
  ];
}
function FIG(file, widthPx, caption) {
  const buf = fs.readFileSync(path.join(HERE, file));
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  figNo++;
  return [new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 160, after: 60 },
      children: [new ImageRun({ type: "png", data: buf, transformation: { width: widthPx, height: Math.round(widthPx * h / w) } })] }),
    new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 200 }, children: [run(`Fig. ${figNo} `, { bold: true, size: 20 }), run(caption, { size: 20 })] })];
}
function ALGO(title, lines) {
  const box = { style: BorderStyle.SINGLE, size: 6, color: "000000" };
  return [new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: [TW], rows: [new TableRow({ cantSplit: true, children: [new TableCell({
      width: { size: TW, type: WidthType.DXA }, borders: { top: box, bottom: box, left: none, right: none },
      margins: { top: 80, bottom: 80, left: 60, right: 60 },
      children: [new Paragraph({ spacing: { after: 60 }, keepNext: true, border: { bottom: thin }, children: [run("Algorithm 1 ", { bold: true, size: 20 }), run(title, { size: 20 })] }),
        ...lines.map((l, k) => new Paragraph({ spacing: { line: 260, after: 0 }, keepNext: k < lines.length - 1,
          indent: { left: 420, hanging: 420 },
          tabStops: [{ type: TabStopType.LEFT, position: 420 }],
          children: [run(`${k + 1}:\t` + "  ".repeat(l.match(/^ */)[0].length / 2), { size: 19 }), ...R(l.trim(), { size: 19 })] }))],
    })] })] }), new Paragraph({ spacing: { after: 160 }, children: [] })];
}

// ---------- front matter ----------
const AUTH = [["Vivek Yeshwantrao Borkar", "1"], ["Piyush Devidas Nande", "1"], ["Aasawari Sahebrao Jumade", "1"], ["Arunima Tridip Wankhade", "1"], ["R. R. Karwa", "1*"]];
const front = [
  new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 240, line: 360 }, children: [run("Satya-Score: An Evidence-Gated Framework for Detecting and Scoring Hallucinated Claims in English and Hindi LLM Answers", { bold: true, size: 34 })] }),
  new Paragraph({ spacing: { after: 100 }, children: AUTH.flatMap(([n, s], k) => [run(n, { size: 23 }), run(s, { size: 23, sup: true }), run(k < AUTH.length - 1 ? ", " : "", { size: 23 })]) }),
  new Paragraph({ spacing: { after: 40 }, children: [run("1", { size: 19, sup: true }), run("Department of Artificial Intelligence and Data Science, Prof. Ram Meghe Institute of Technology & Research, Badnera-Amravati, Maharashtra, India", { size: 19, italics: true })] }),
  new Paragraph({ spacing: { after: 40 }, children: [run("*Corresponding author: R. R. Karwa, [e-mail address]", { size: 19 })] }),
  new Paragraph({ spacing: { after: 280 }, children: [run("Contributing authors: [e-mail addresses of the student authors]", { size: 19 })] }),
  new Paragraph({ spacing: { after: 80 }, children: [run("Abstract", { bold: true, size: 23 })] }),
  P0("Answers produced by chatbots that run on large language models (LLMs) read smoothly yet sometimes state things that are untrue, and tools that pinpoint such errors are scarce for Hindi. We present Satya-Score, a framework that divides English or Hindi text into claims and labels each claim as Verified, Uncertain or Hallucinated, attaching a score and the evidence used. Each claim is offered first to sources able to settle it directly—official World Bank and WHO figures, Wikidata relations and fact-checks already published by journalists—and a decision from these sources also supplies the correct value. For the remaining claims, an open-weight LLM (gpt-oss-20b) serves as a second reader next to a multilingual inference model applied to retrieved Wikipedia passages, and its judgement is accepted only if the passage evidence points the same way. We evaluated the framework against acceptance criteria fixed in advance, on 620 held-out items, each used only once, taken from FEVER, Mu-SHROOM, TruthfulQA, X-FACT and two sets built from Hindi Wikipedia. Compared with the same pipeline without the LLM, the evidence-gated design detected 47% rather than 25% of false items (p < 0.001) and reduced the share of false items wrongly accepted from 22% to 6%; on true items the false-alarm rate went from 11% to 13%, a difference that is not significant. Left ungated, the same LLM raised alarms on 28% of true items. Detections grew by a factor of 1.85 (95% CI 1.61–2.19), just short of the factor of two set beforehand; we report this shortfall, and the rounds that failed before it, without omission. The structured sources proved the most reliable part of the system, detecting every one of 137 altered country statistics.", { after: 160 }),
  new Paragraph({ spacing: { after: 300 }, children: [run("Keywords: ", { bold: true }), run("Hallucination detection · Large language models · Claim verification · Knowledge graphs · Natural language inference · Hindi · Explainable fact-checking")] }),
];

// ---------- body ----------
const body = [
  H1("Introduction"),
  P0("Conversational assistants are now consulted on health, public schemes, law and history. The models behind them generate the most likely continuation of a prompt; they do not look facts up, and so they sometimes produce details that are invented or wrong while sounding entirely certain. This behaviour, usually called hallucination, has been described in several recent surveys {ji,huang,siren,lresurvey}, and its consequences for public information have been discussed at length {augenstein}."),
  P("Two properties of the problem shape any practical checker. First, an error is typically one statement inside an otherwise correct answer. A single score for the whole answer therefore tells a reader little; what helps is to know which statement is wrong, why, and what the right fact is {factscore}. Second, almost all available checkers work in English. Hindi, the first language of several hundred million people, appears increasingly in chatbot replies, yet resources for verifying Hindi text remain thin {xfact,bhramil,inclusive}."),
  P("Satya-Score was built to examine answers in English and Hindi one claim at a time and to back every verdict with evidence that the reader can open and inspect. Its first version routed every claim to the most trustworthy source available: official statistics, a knowledge graph, a published fact-check, or—when none applied—Wikipedia text assessed by a natural language inference (NLI) classifier. False alarms were rare under that design, yet the text route uncovered only a small fraction of the hallucinations, because an inference model readily treats a passage about the right topic as support {mccoy}. Replacing the inference model with an LLM judge {judge} caught many more errors but flagged almost four times as many correct claims. This paper describes the second version, in which the two readers are combined so that neither can decide alone."),
  P("Our contributions are as follows:"),
  LI([b("An evidence-gated LLM cross-check. "), run("Acceptance as Verified requires both supporting passages and the LLM’s assent; a Hallucinated label requires the LLM to point to a concrete incorrect fact, rather than to an absence of evidence, and a further reading confined to the passages must fail to find the claim.")]),
  LI([b("Source routing with corrections. "), run("Each claim is answered by the most reliable source that covers it; statistics and knowledge-graph decisions return the correct value, and the offending words are highlighted for the reader.")]),
  LI([b("Bilingual coverage. "), run("The full pipeline, including retrieval, inference, knowledge-graph templates and the cross-check, operates on English and Hindi.")]),
  LI([b("A pre-registered evaluation. "), run("Acceptance criteria were fixed before each run on held-out public and constructed data; every held-out item was used once, and failed rounds are reported together with ablations.")]),
  P("Section 2 reviews related work. Section 3 describes the framework, Section 4 the data and protocol, and Section 5 the results. Section 6 discusses where the approach stands relative to earlier work and its limitations, and Section 7 concludes."),

  H1("Related Work"),
  H2("Hallucination detection"),
  P0("Surveys classify hallucination by its source and type and group detection methods into those that consult external knowledge and those that rely on the model itself {ji,huang,siren,lresurvey}. Among self-contained methods, SelfCheckGPT {selfcheck} samples several answers and treats disagreement as a warning sign, and semantic entropy {farquhar} measures uncertainty over clusters of answers that share a meaning. Both need repeated sampling and both miss errors that a model repeats consistently. Other detectors read the internal states of the generating model {mind}, which is impossible when checking a closed chatbot. Recent journal work refines consistency checking at several granularities without external knowledge {multigran} and uses synonym-aware knowledge graphs to avoid flagging paraphrases as errors {synkg}. Benchmarks such as HaluEval {halueval} and analytical annotations such as ANAH {anah} have made comparison easier, and fine-grained detectors such as FAVA {fava} and RefChecker {refchecker} mark the erroneous span rather than the whole answer."),
  H2("Claim verification and LLM-based fact-checking"),
  P0("FEVER {fever} established verification of claims against Wikipedia as a standard task. For model output, FActScore {factscore} decomposes long answers into atomic facts and checks each against retrieved passages, and SAFE {safe} lets an LLM agent issue web searches for every fact. Document-grounded checkers such as AlignScore {alignscore} and MiniCheck {minicheck} decide whether a given document supports a sentence, while TRUE {true} showed how unevenly factual-consistency metrics behave across tasks. LLM agents that phrase queries, retrieve context and decide have been studied directly {quelle}: retrieved context improves them, but their accuracy varies with the language of the query and with the veracity of the claim. A multilingual study of nine LLMs on 5,000 claims assessed by 174 fact-checking organisations found that smaller models expressed high confidence even though they erred more often, whereas larger models were more accurate yet less sure of themselves, with the largest gaps for non-English claims {dunning}. Journal work has combined question answering with knowledge enhancement for verification {kqfv} and has grounded LLM fact-checking in sources accredited by the International Fact-Checking Network {factualrag}. These findings motivate our decision to treat the LLM as one witness among several rather than as the judge."),
  H2("Knowledge graphs and hallucination"),
  P0("Knowledge graphs store facts as explicit relations and can therefore confirm or refute a claim with a definite answer. FactKG {factkg} checks claims by following reasoning paths through a graph, KGR {kgr} retrofits a model’s draft with graph facts, and MultiHal {multihal} provides multilingual questions grounded in graph paths. A knowledge graph combined with KG-BERT has been used for fact-checking in Vietnamese, another lower-resource language {kgbert}. Reviews judge the benefit of graphs against hallucination promising but not yet established {agrawal,lavrinovics}. Retrieval-augmented generation {rag} supplies evidence during writing, which is of no use once the task is to audit an answer that some other chatbot has already produced."),
  H2("Hindi and multilingual verification"),
  P0("X-FACT {xfact} collected labelled claims in 25 languages, Hindi among them. The SemEval-2025 Mu-SHROOM task {mushroom} invited systems that locate hallucinated character spans in 14 languages; submissions relied on voting among several LLMs {msa}, on inference models tuned with synthetic examples {hausa} and on semantic-role analysis combined with retrieved text {detectives}, and none of these drew on a knowledge graph. BHRAM-IL {bhramil} measures hallucination across Indian languages, and a recent dataset supports verifying claims written in English, Hindi, Bengali or a code-mixed form, with fine-tuned multilingual encoders as baselines {inclusive}. Related Hindi work addresses multimodal fake-news detection {mmhfnd} and entity hallucination in abstractive summarisation {entityhi}, and multilingual retrieval-augmented pipelines now verify news in English, Chinese and Urdu {mmrag}. Cross-lingual encoders like XLM-R {xlmr} and MuRIL {muril}, together with the IndicNLP resources {indicsuite} and the IndicXNLI benchmark {indicxnli} make cross-lingual retrieval and inference for Hindi feasible."),
  H2("Research gap"),
  P0("Table 1 compares representative systems on the properties that matter for checking chatbot answers. We found no system that, for both English and Hindi, combines official statistics, a knowledge graph and published fact-checks with an LLM whose vote is accepted only together with retrieved evidence, and that returns the correct value when a structured source holds it."),
  ...TABLE("Comparison of representative systems", [
    ["System", "Unit checked", "Hindi", "Evidence", "Role of the LLM", "Correct value"],
    ["FActScore {factscore}", "Atomic facts", "No", "Wikipedia passages", "Judges support of each fact", "No"],
    ["SAFE {safe}", "Atomic facts", "No", "Web search", "Agent searches and decides", "No"],
    ["SelfCheckGPT {selfcheck}", "Sentences", "No", "None", "Sampled answers compared", "No"],
    ["MiniCheck {minicheck}", "Sentences", "No", "Supplied document", "Small trained checker", "No"],
    ["M&M-RAG {mmrag}", "News claims", "No", "Multilingual web retrieval", "LLM/LVLM decides", "No"],
    ["Mu-SHROOM systems {msa,hausa,detectives}", "Character spans", "Yes", "LLM votes, NLI, retrieved text", "Varies by team", "No"],
    ["Pal et al. {inclusive}", "Claims", "Yes", "Evidence passages", "None (fine-tuned encoders)", "No"],
    ["Satya-Score (ours)", "Claims, wrong words", "Yes", "Statistics, Wikidata, fact-checks, Wikipedia", "Second reader, gated by evidence", "Yes"],
  ], [1900, 1250, 650, 1956, 1820, 1450], { boldRows: [8] }),

  H1("The Satya-Score Framework"),
  H2("Overview"),
  P0("Fig. 1 shows the pipeline. Text arrives through a web application or a REST interface and is split into claims. Each claim is offered to the structured sources and to evidence retrieval in parallel. If a statistic, a Wikidata relation or a published fact-check settles the claim, that decision is final and the LLM is never consulted. Otherwise the passage score and the LLM cross-check are combined by the agreement rule of Section 3.5. Every claim leaves the pipeline with a verdict, a score, the deciding evidence and, where possible, the wrong words marked."),
  ...FIG("fig1_architecture_v2.png", 470, "Architecture of Satya-Score. Claims decided by a structured source or a fact-check never reach the LLM; the remaining claims are judged by the passage reader and the LLM together."),
  H2("Claim extraction"),
  P0("For English, a spaCy {spacy} dependency parse drives the segmentation: statements joined by a conjunction are separated, each element of a list becomes its own claim, and a pronoun is rewritten as the entity the passage is about rather than the closest preceding name. A pre-registered test on 400 unseen Wikipedia lead sections showed pronoun resolution improving from 93 to 277 correct cases. For Hindi, sentence boundaries come from the Indic NLP Library {indicnlp}. Questions, greetings and pieces of advice assert nothing that could be checked and are skipped."),
  H2("Evidence retrieval and inference"),
  P0("A multilingual sentence encoder based on XLM-R {sbertml,xlmr} maps every claim and passage to a vector, and FAISS {faiss} looks up neighbours in an index which, when the evaluation ran, contained 102,069 Wikipedia passages (89,594 in English, 12,475 in Hindi); when a needed article is absent it is downloaded and added. The ten nearest passages, provided their cosine similarity is 0.3 or more, go to an mDeBERTa-v3 classifier {debertav3} fine-tuned on MultiNLI and XNLI {mnli,xnli}. For a passage p it returns e(p), the probability that p entails the claim, and c(p), the probability that p contradicts it. These are turned into the passage score s:"),
  EQ(["s = 0.5 + 0.5·max", SB("p"), " e(p),    if max", SB("p"), " e(p) ≥ 0.5"], 1),
  EQ(["s = 0.5 + 0.5·(max", SB("p"), " e(p) − max", SB("q"), " c(q)),    otherwise"], 2),
  P0("Here q is restricted to on-topic passages, meaning those whose article title appears in the claim. Any retrieved passage can therefore lend support, whereas only text describing the claim’s own subject can refute it; introducing this asymmetry eliminated most of the false alarms that unrelated passages had caused."),
  H2("Structured sources"),
  P0("Five country indicators—population, GDP, life expectancy, literacy and infant mortality—are checked against World Bank figures {worldbank}, and the two health indicators also against WHO figures {who}. Rounding follows the claim: a statement such as “about 1.4 billion” is judged at that precision, not to the last digit, and if the two agencies both hold a value they must reach the same verdict. Wikidata {wikidata} answers relational claims—place and date of birth or death, founding date, capital, authorship, office holders, quantities and currencies—through hand-written English and Hindi templates. Because many names refer to more than one entity, a single matching namesake is enough for support, whereas a refutation needs every namesake that has a value to disagree. Verdicts of professional fact-checkers are fetched via the Google Fact Check Tools API {googlefc}; such a verdict of “false” is carried over only when our claim entails the statement that was checked, and “true” only when the checked statement entails our claim; a negated claim therefore never inherits the rating of its positive form."),
  H2("Evidence-gated LLM cross-check"),
  P0("Any claim left open by the structured sources is passed to gpt-oss-20b {gptoss}. This open-weight model uses a mixture-of-experts design (21 B parameters in total, 3.6 B active for each token) and is licensed under Apache 2.0; for the evaluation it was served locally with Ollama {ollama}. In its first reading the model receives the claim together with the five highest-ranked passages, each cut to 600 characters, and may also draw on what it already knows. The reply is a JSON object holding a verdict, the probability that the claim is true, any incorrect words quoted from the claim, and a short justification; generation uses greedy decoding. Fig. 2 and Algorithm 1 show how this verdict, written j, is merged with s."),
  P("The rule contains three safeguards, each introduced to repair a failure seen during development (Section 5.4). First, when the LLM answers Hallucinated but its justification merely notes that the passages are silent on the point, the answer is treated as Uncertain: silence is not disproof. Second, a contradiction detected by the passage reader cannot flag a claim unless the LLM also calls it false. Third, a claim about to be flagged is read once more, this time against all ten passages and without the model’s own knowledge; should the passages assert the claim, it is left Uncertain. The same passages-only reading is used in reverse to promote a claim to Verified when one of the two readers considered it true and the passages assert it."),
  ...FIG("fig2_decision_v2.png", 440, "How a claim not settled by any structured source is decided. s: passage score from Eqs. (1)–(2); j: verdict of the first LLM reading; the confirmatory reading sees the ten retrieved passages and nothing else."),
  ...ALGO("Deciding the verdict of a claim c", [
    "if a structured source (statistic, Wikidata, fact-check) settles c: output its verdict with the correct value; stop",
    "s ← NLI score of the ten best passages for c (Eqs. 1–2)",
    "j ← first LLM reading of c with its five best passages and the model’s own knowledge",
    "if j says Hallucinated only because evidence is absent: j ← Uncertain",
    "if j = Verified and s > 0.65: v ← Verified",
    "elif j = Hallucinated and s ≤ 0.65:",
    "  v ← Uncertain if the passages-only reading finds c stated, otherwise Hallucinated",
    "elif j ≠ Hallucinated and (j = Verified or s > 0.65):",
    "  v ← Verified if the passages-only reading finds c stated, otherwise Uncertain",
    "else: v ← Uncertain",
    "score ← average of s and the LLM’s probability of truth, limited to the range of v (Eq. 4)",
    "highlight the incorrect value from Wikidata if any, else the words quoted by the LLM, else the full claim",
  ]),
  H2("Scoring and explanation"),
  P0("In the first version, scores came from the Composite Multilingual Hallucination Scoring Algorithm (CMHSA), a weighted sum of three signals with weights learned separately for each language:"),
  EQ("HalluScore = α·SemSim + β·NLI + γ·KG,    α + β + γ = 1", 3),
  P0("Because semantic similarity indicates that a passage is on the same topic rather than that the claim is true, α was fixed at 0; training on labelled claims gave β ≈ γ ≈ 0.5. At run time the score is taken from whichever source answers first: 1.0 or 0.0 for a statistics or Wikidata decision, 0.95 or 0.05 for an applicable fact-check, and otherwise the cross-check score of Algorithm 1. Verdicts follow fixed bands,"),
  EQ("v = Hallucinated if score < 0.35;   Uncertain if 0.35 ≤ score ≤ 0.65;   Verified if score > 0.65", 4),
  P0("and a complete text is rated Hallucinated if a third or more of its claims carry that label, Verified if every claim is Verified, and Uncertain in all other cases. The middle band is deliberate: the system may say that the evidence does not settle a claim instead of guessing. The web application underlines each claim in the colour of its verdict, marks the wrong words, and shows the deciding source, what each reader concluded, and the correct value when a structured source supplied it."),
  H2("Implementation"),
  P0("The back end is written in Python with FastAPI; the front end uses React. Accounts, saved checks and export are supported, passwords are stored as salted scrypt hashes, and sessions use HttpOnly cookies. The code base has 323 automated tests. All models are open-weight and the evaluation ran on a laptop with an RTX 4050 GPU (6 GB). For interactive use the same gpt-oss-20b weights can also be reached through hosted services, with the local model as fallback; this changes speed but not the model."),

  H1("Experimental Setup"),
  H2("Datasets"),
  P0("Table 2 summarises the data. The cross-check was assessed on seven sets labelled by others. FEVER {fever} contributes English claims marked as supported or refuted. Mu-SHROOM {mushroom} contributes chatbot answers in which annotators highlighted hallucinated character spans; after extracting claims, we call a claim false if it shares three or more characters with a highlighted span and drop it if it shares only one or two. From TruthfulQA {truthfulqa} we take, for each question, the reference answer and the first wrong answer, presented without the question itself. X-FACT {xfact} contributes Hindi rumours that professional fact-checkers judged false. Two sets are derived from Hindi Wikipedia: true items are sentences copied from articles, and each false item alters exactly one number in such a sentence. In the reworded variant, another LLM paraphrases the true sentence; a paraphrase is retained only if mutual entailment is at least 0.80 and all numbers are preserved, after which one number is altered to create the false item. Each set was divided into a development part and a sealed test part, and items were sampled at random with a ceiling of 60 true and 60 false items per set and language."),
  ...TABLE("Evaluation data", [
    ["Set", "Language", "True / false items", "Source of labels"],
    ["Held-out comparison (620 items)", "", "", ""],
    ["FEVER claims", "English", "60 / 60", "FEVER annotators"],
    ["Mu-SHROOM claims", "English", "52 / 60", "Human-marked spans"],
    ["Mu-SHROOM claims", "Hindi", "0 / 60", "Human-marked spans"],
    ["TruthfulQA answers", "English", "60 / 60", "TruthfulQA"],
    ["X-FACT rumours", "Hindi", "0 / 60", "Professional fact-checkers"],
    ["Hindi Wikipedia sentences", "Hindi", "38 / 38", "Construction (one number changed)"],
    ["Hindi Wikipedia, reworded", "Hindi", "36 / 36", "Construction (one number changed)"],
    ["Component studies (first version)", "", "", ""],
    ["Chatbot claims (Llama 3.3, five domains)", "English, Hindi", "456 claims", "Four annotators"],
    ["Relational claims", "English", "25 / 15", "Two annotators"],
    ["Country statistics", "–", "137 / 137", "Construction"],
    ["Fact-check set", "English, Hindi", "15 / 25", "Fact-checkers"],
  ], [3226, 1500, 1700, 2600], { groupRows: [1, 9] }),
  P("The 456 chatbot claims were extracted from Llama 3.3 (70B) {llama3} answers to questions in five domains: government, healthcare, science, sports and history. Each claim first received a machine-proposed label, which one of four annotators (the student authors) accepted or corrected; 79% of final labels match the proposal. Agreement between two independent labellers who did not see the proposal, measured on 56 claims, was Cohen’s κ = 0.53 (88% identical labels). These claims guided the development of the cross-check and are consequently excluded from its evaluation."),
  H2("Protocol"),
  P0("No design decision used the final sample; choices relied on development data or on held-out samples that were retired after use. The LLM came out of a bake-off on 202 development items run under rules set beforehand. Under the cross-check, gpt-oss-20b achieved the best balanced accuracy, 57% with a false-alarm rate of 7%, followed by gpt-oss-120b at 56% and 10%; a third candidate returned answers for under 90% of the items and was disqualified. Every held-out sample came from the sealed test parts, no item was reused, and both versions were run on a sample exactly once. Each run was preceded by a written record of the configuration and of the criterion for adopting it. For the final run the criterion, stated relative to the first version (V1), demanded double the catches or more, no more than half the false items accepted as Verified, a false-alarm rate no more than three points above V1, and a share of true items Verified no more than five points below V1."),
  H2("Measures"),
  P0("Let F and T be the sets of false and true items and v(x) the verdict for item x. We report"),
  EQ("Caught = |{x ∈ F : v(x) = H}| / |F|,      Passed = |{x ∈ F : v(x) = V}| / |F|", 5),
  EQ("TrueVerified = |{x ∈ T : v(x) = V}| / |T|,      FalseAlarm = |{x ∈ T : v(x) = H}| / |T|", 6),
  P0("where H and V denote Hallucinated and Verified. Uncertain is never counted as correct, so the measures are conservative. Paired differences between the versions are assessed with the exact McNemar test, and 95% confidence intervals for ratios come from 2,000 bootstrap resamples of the items. On Mu-SHROOM we additionally compute the task’s own character-level intersection over union (IoU) between predicted and annotated spans."),

  H1("Results"),
  H2("Held-out comparison"),
  P0("Table 3 and Fig. 3 give the outcome of the final run. Of 374 false items, V2 labelled 176 Hallucinated where V1 had labelled 95; 92 items were newly caught and 11 were lost (McNemar p < 0.001). False items accepted as Verified fell from 83 to 23 (p < 0.001). Among 246 true items, V2 Verified 139 (V1: 137) and flagged 32 (V1: 28); neither difference is significant (p = 0.87 and p = 0.63), and the false-alarm difference of +1.6 points has a 95% CI of −3.2 to +6.6. Three criteria were therefore satisfied. The fourth was not: the catch ratio of 1.85 (95% CI 1.61–2.19) is below 2, so by the rule we had fixed, V2 did not become the default; the deployed system makes it available as an option. We publish the outcome because the criterion predates the run and because the trade-off it reveals is itself useful."),
  ...TABLE("Held-out comparison of the first version (V1) and the evidence-gated cross-check (V2), 620 items", [
    ["Measure", "V1", "V2", "Criterion", "Met"],
    ["False items caught", "95/374 (25%)", "176/374 (47%)", "≥ 2 × V1", "No (1.85×)"],
    ["False items passed as Verified", "83/374 (22%)", "23/374 (6%)", "≤ ½ × V1", "Yes"],
    ["True items Verified", "137/246 (56%)", "139/246 (57%)", "≥ V1 − 5 points", "Yes"],
    ["False alarms on true items", "28/246 (11%)", "32/246 (13%)", "≤ V1 + 3 points", "Yes"],
  ], [2826, 1600, 1600, 1700, 1300]),
  ...FIG("fig3_overall.png", 560, "Overall results on the 620 held-out items. Used on its own the LLM detects most false items yet raises an alarm on 28% of true ones; requiring agreement with passage evidence holds false alarms near the V1 level while almost doubling detections."),
  H2("Results per dataset"),
  P0("Table 4 and Fig. 4 show each set separately. Gains are greatest where V1 had to rely on thin textual evidence: Hindi Wikipedia sentences with an altered number rose from 3% to 39% caught, Hindi Mu-SHROOM answers from 7% to 45% and TruthfulQA misconceptions from 17% to 43%. FEVER improved in both directions, with more false claims caught and fewer true claims flagged, at the cost of a small drop in true claims Verified (from 72% to 67%). The price is paid mainly on TruthfulQA, whose answers lack their question and are often too vague to check, where false alarms increased from 18% to 27%, and on the reworded Hindi sentences, from 3% to 11%. Most X-FACT rumours were already caught through published fact-checks; when that source is switched off, V1 catches just 5% of them."),
  ...TABLE("Results per dataset, V1 → V2 (percentage of items)", [
    ["Set (true / false)", "Caught", "Passed as Verified", "True Verified", "False alarms"],
    ["FEVER, English (60 / 60)", "37 → 62", "20 → 5", "72 → 67", "13 → 7"],
    ["Hindi Wikipedia (38 / 38)", "3 → 39", "13 → 5", "95 → 87", "0 → 0"],
    ["Hindi Wikipedia, reworded (36 / 36)", "28 → 47", "33 → 0", "78 → 78", "3 → 11"],
    ["Mu-SHROOM, English (52 / 60)", "13 → 20", "23 → 15", "40 → 40", "15 → 15"],
    ["Mu-SHROOM, Hindi (0 / 60)", "7 → 45", "38 → 5", "–", "–"],
    ["TruthfulQA, English (60 / 60)", "17 → 43", "27 → 8", "15 → 28", "18 → 27"],
    ["X-FACT rumours, Hindi (0 / 60)", "67 → 70", "2 → 2", "–", "–"],
  ], [2826, 1400, 1700, 1500, 1600]),
  ...FIG("fig4_perset.png", 580, "Catches and false alarms per dataset for V1 and V2. Sets without true items have no false-alarm rate (n/a)."),
  H2("Ablation"),
  P0("Table 5 and Fig. 5 take the decision rule apart step by step, reusing the cached LLM answers for the same 620 items. Since this analysis followed the main result, it is exploratory. On its own, the LLM catches 86% of false items while flagging 28% of true items. Demanding agreement with the passages lowers that rate to 22%. The filter for “no evidence” answers lowers it further to 16%, though catches drop as well. The passages-only second reading lifts the share of true items Verified back from 47% to 57%. Finally, insisting that the LLM itself call a claim false and re-checking the passages before flagging takes false alarms down to 13%. Every safeguard therefore buys fewer false alarms with some loss of catches."),
  ...TABLE("Ablation of the decision rule on the held-out items (exploratory)", [
    ["Variant", "Caught", "Passed as Verified", "True Verified", "False alarms"],
    ["V1 (no LLM)", "25%", "22%", "56%", "11%"],
    ["LLM alone", "86%", "11%", "65%", "28%"],
    ["Agreement rule only", "68%", "4%", "47%", "22%"],
    ["+ no-evidence filter", "49%", "4%", "47%", "16%"],
    ["+ second reading", "49%", "6%", "57%", "16%"],
    ["+ LLM must say false, check before flagging (V2)", "47%", "6%", "57%", "13%"],
  ], [3626, 1200, 1500, 1300, 1400], { boldRows: [6] }),
  ...FIG("fig5_ablation.png", 470, "Trade-off between catches and false alarms along the ablation path. Moving from the LLM alone towards V2, each safeguard lowers false alarms; V2 sits close to V1 in false alarms while catching almost twice as many false items."),
  H2("Development rounds"),
  P0("Table 6 lists the four configurations that reached held-out data, each tested on its own fresh sample. The first, a plain agreement rule, almost tripled catches but pushed false alarms from 9% to 17% and so broke the first criterion, which at that time capped false alarms at 5% in absolute terms. Examining the errors revealed that the LLM was rejecting claims simply because the passages were silent about them. The 5% cap had been chosen when V1 produced 3–6% false alarms on chatbot claims, but on the public sets V1 itself produces 9–12%. Before the next run we therefore restated the criterion relative to V1 and introduced the no-evidence filter. Round two met its criteria but Verified only 40% of true items, against 56% for V1, which prompted the second reading and an added criterion on true items. Round three failed on false alarms. The flagging safeguards were then selected using the three retired samples, giving the configuration evaluated in Table 3. No unused held-out sample remains."),
  ...TABLE("Held-out rounds, each on a new sample and run once", [
    ["Round", "Items", "Change tested", "Caught (V1 → V2)", "False alarms (V1 → V2)", "Outcome"],
    ["1", "201", "Plain agreement rule", "20% → 58%", "9% → 17%", "Failed"],
    ["2", "175", "+ no-evidence filter", "15% → 47%", "12% → 12%", "Passed; few true Verified"],
    ["3", "162", "+ second reading", "19% → 37%", "5% → 14%", "Failed"],
    ["4 (final)", "620", "+ LLM must say false, check before flagging", "25% → 47%", "11% → 13%", "3 of 4 criteria"],
  ], [1000, 800, 2626, 1600, 1700, 1300]),
  H2("Marking the wrong words"),
  P0("Fig. 6 gives Mu-SHROOM span overlap for the held-out answers. Highlighting only the incorrect words supplied by Wikidata or the LLM, rather than every character of a flagged claim, lifted mean IoU for Hindi from 0.010 to 0.189 and for English from 0.114 to 0.184. Both remain under the score of simply highlighting everything (0.318 and 0.307), and clearly under the leading shared-task entries on the complete test set, 0.74 for Hindi and 0.65 for English {mushroom}, which were engineered for span marking alone."),
  ...FIG("fig6_iou.png", 450, "Mean character-level IoU with the human-marked hallucinated spans of Mu-SHROOM, held-out answers."),
  H2("Structured sources"),
  P0("The structured sources were assessed for V1 and are identical in V2 (Table 7). Every one of 137 altered country statistics was detected, and none of the 137 genuine figures was rejected. In a pre-registered ablation over 40 relational claims, adding the knowledge-graph signal to the inference score improved AUC from 0.704 to 0.784 (+0.080; 95% CI +0.003 to +0.189). Across a 40-claim fact-check set, no decision based on a fact-check was wrong. On the annotated chatbot claims, V1 raised alarms on only 9 of 258 true training claims but detected only 5 of 45 hallucinations; this weakness is what prompted the cross-check."),
  ...TABLE("Component results (first version, unchanged in V2)", [
    ["Component", "Test data", "Result"],
    ["Official statistics", "137 altered and 137 true country figures", "137/137 caught; 0/137 true figures contradicted"],
    ["Knowledge graph (AUC ablation)", "40 relational claims, pre-registered", "AUC 0.704 → 0.784 (+0.080; 95% CI +0.003 to +0.189)"],
    ["Wikidata decisions", "Same 40 claims", "11 of 13 correct; 12 of 12 after a linking repair (exploratory)"],
    ["Published fact-checks", "40 claims (15 true, 25 false)", "No wrong decision"],
    ["Pronoun resolution", "400 Wikipedia introductions", "Correct resolutions 93 → 277"],
    ["V1 on chatbot claims", "258 true and 45 hallucinated training claims", "9 true flagged; 5 hallucinations caught"],
  ], [2400, 3026, 3600]),
  H2("Qualitative examples"),
  P0("Table 8 lists examples produced by the deployed system. Structured sources give the correct value; for claims that no structured source covers, the reasons given by the two readers are shown to the user."),
  ...TABLE("Examples produced by the deployed system", [
    ["Claim", "Verdict", "Deciding evidence shown to the user"],
    ["The Eiffel Tower … was completed in 1925.", "Hallucinated", "LLM: the tower opened in 1889; passages disagree; “completed in 1925” highlighted"],
    ["The Great Wall of China is visible from the Moon with the naked eye.", "Hallucinated", "LLM: a widespread myth; passages disagree"],
    ["Albert Einstein developed the theory of relativity.", "Verified", "Both readers agree"],
    ["Mahatma Gandhi was born in Delhi.", "Hallucinated", "Wikidata; correct value: Porbandar"],
    ["भारत की राजधानी मुंबई है। (India’s capital is Mumbai.)", "Hallucinated", "Wikidata; correct value: नई दिल्ली (New Delhi)"],
    ["यूनेस्को ने नरेंद्र मोदी को दुनिया का सर्वश्रेष्ठ प्रधानमंत्री घोषित किया है। (UNESCO declared Modi the world’s best prime minister.)", "Hallucinated", "Published fact-check (Vishvas News): False"],
    ["The population of India is about 500 million.", "Hallucinated", "World Bank; official figure shown"],
  ], [4026, 1300, 3700]),
  H2("Efficiency"),
  P0("Table 9 lists response times measured on the evaluation laptop. A six-claim English answer takes about 5 s when the LLM is not used. With the cross-check served locally the LLM dominates: at 13 GB the model exceeds the 6 GB of GPU memory, runs mostly on the processor and needs roughly 4 s per reading. Sending four requests in parallel slowed a six-claim answer to 202 s, so readings are issued sequentially. Hosting the identical open weights on a cloud service shortens the wait considerably, and claims seen before are served from a cache."),
  ...TABLE("Response time for one answer (laptop, RTX 4050, 6 GB)", [
    ["Configuration", "Claims", "First check", "Same text again"],
    ["V1 (no LLM)", "6", "5.1 s", "0.7 s"],
    ["V2, LLM on the laptop only", "6", "45.7 s", "under 3 s"],
    ["V2, hosted service first (Groq), laptop as fallback", "5", "18.2 s", "2.7 s"],
    ["V2, two hosted services (Groq, OpenRouter), laptop as fallback", "6", "27.3 s", "1.1 s"],
  ], [4826, 1000, 1500, 1700]),

  H1("Discussion"),
  H2("Position relative to earlier work"),
  P0("The comparison in Table 1 shows where Satya-Score differs from earlier systems: it covers Hindi as well as English, it consults structured sources before text, it returns the correct value when such a source holds the fact, and it never lets an LLM decide alone. The value of the last point is visible in our own data. The same model that caught 86% of false items flagged 28% of true ones when used as a judge, which agrees with reports that LLM confidence is a poor guide to accuracy, particularly outside English {dunning}, and that the accuracy of LLM fact-checkers varies with language and claim type {quelle}. Gating the LLM with passage evidence retained more than half of its additional catches while keeping false alarms within two points of the system without it."),
  P("The comparison also shows where the approach is weaker. On Mu-SHROOM span marking our system remains far below the systems built for that task (Section 5.6), because it prefers to leave a claim Uncertain rather than flag it without evidence, and therefore marks fewer characters. Our held-out samples are small per set and drawn from public data under our own protocol; the figures are therefore not directly comparable with leaderboard results that use complete test sets and fixed evidence snapshots. We regard Satya-Score as a transparent, multilingual checker for deployment rather than as a system that tops a single benchmark."),
  H2("Error analysis"),
  P0("Three recurring failure patterns explain most remaining errors. First, the passage reader sometimes counts a passage on the right topic as support: for a claim that a cricket team fields twelve players, passages about team size gave a high support score although the LLM correctly identified the claim as false, and the disagreement left the claim Uncertain rather than Hallucinated. Second, TruthfulQA answers stated without their question are often too vague to verify, which raises false alarms on that set. Third, paraphrased Hindi sentences lose the exact wording that retrieval relies on, so both readers see weaker evidence. Predictions and opinions are labelled Uncertain by design, since no source can verify them."),
  H2("Limitations and threats to validity"),
  P0("Several limitations apply. Altering a single number makes the constructed Hindi false items easier to detect than genuine chatbot errors. Mu-SHROOM claim labels are inferred from span overlap, and with at most 60 true and 60 false items per set, a single item shifts a per-set percentage by two to three points. We revised the acceptance criterion once following a failed round (Section 5.4), and the final configuration was tuned on samples already used. The LLM’s knowledge stops at a cut-off date, and it may hold the same misconceptions as the chatbot under review. The live sources need an internet connection, the cross-check is slow on a laptop unless a hosted model is used, Hindi pronouns are not yet resolved, and the WHO licence restricts that data to non-commercial use."),

  H1("Conclusion and Future Work"),
  P0("Satya-Score examines chatbot answers in English and Hindi one claim at a time and attaches inspectable evidence to every verdict. Where a structured source covers a claim it decides and supplies the correct value; elsewhere the open-weight LLM and the retrieved passages have to agree. On 620 held-out items this design came close to doubling the false items detected and reduced those wrongly accepted by almost three quarters, while false alarms rose by two points, a change that is not significant. Committing to adoption criteria ahead of each run made visible both what the LLM adds and where it falls short of our own target. Next, we plan a larger Hindi test set labelled independently by two annotators, support for Marathi, pronoun resolution for Hindi and a faster cross-check."),

  Hn("Declarations"),
  P0([b("Funding. "), run("The authors did not receive support from any organisation for the submitted work.")]),
  P0([b("Competing interests. "), run("The authors have no competing interests to declare that are relevant to the content of this article.")]),
  P0([b("Ethics approval. "), run("Not applicable. The study uses public datasets and claims generated by an LLM; the human annotators were the authors.")]),
  P0([b("Data availability. "), run("The public datasets are available from their original sources {fever,mushroom,truthfulqa,xfact}. The item lists, labels, constructed Hindi sets and system outputs used in this study are available from the corresponding author on reasonable request.")]),
  P0([b("Code availability. "), run("The source code of Satya-Score is available from the corresponding author on reasonable request.")]),
  P0([b("Author contributions. "), run("V. Y. Borkar: system architecture, back end, LLM cross-check and evaluation runs. P. D. Nande: retrieval, inference model and scoring. A. S. Jumade: structured sources, knowledge graph and datasets. A. T. Wankhade: web application, testing and evaluation analysis. R. R. Karwa: supervision and review of the manuscript. All authors annotated data, read and approved the final manuscript.")]),
  P0([b("Use of generative AI. "), run("AI tools assisted with code, with drafting the text of this manuscript and with drawing the figures. An AI system proposed initial verdicts that the authors reviewed (Section 4.1). The system itself contains an open-weight LLM (gpt-oss-20b), and a second LLM paraphrased Hindi test sentences. The authors verified every experiment, label and reported figure and accept full responsibility for the article.")]),
];

const refs = () => [Hn("References"),
  ...ORDER.map((k, n) => new Paragraph({ spacing: { after: 50, line: 260 }, indent: { left: 500, hanging: 500 }, alignment: AlignmentType.JUSTIFIED,
    tabStops: [{ type: TabStopType.LEFT, position: 500 }], children: [new TextRun({ text: `[${n + 1}]\t${REFS[k]}`, font: F, size: 19 })] }))];

const all = [...front, ...body];
const children = [...all, ...refs()];
const doc = new Document({
  styles: { default: { document: { run: { font: F, size: 22 } } } },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ font: F, size: 18, children: [PageNumber.CURRENT] })] })] }) },
    children }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf);
  const unused = Object.keys(NEWT).filter(k => !ORDER.includes(k));
  console.log("wrote", OUT, "| references:", ORDER.length, "| tables:", tabNo, "| figures:", figNo, "| unused new refs:", unused.join(",") || "none"); });
