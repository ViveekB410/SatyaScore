// Phase 3 review guide for the project guide: demo, working, APIs/models, scoring, roles, Q&A. Usage: node phase3_guide.js <out.docx>
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType, WidthType, BorderStyle,
  ShadingType, LevelFormat, Footer, PageNumber } = require("docx");
const OUT = process.argv[2];
const F = "Times New Roman";
const W = 9412; // A4 11906 - 2 x 1247
const run = (t, o = {}) => new TextRun({ text: t, font: o.font || F, size: o.size || 22, bold: o.bold, italics: o.italics, color: o.color });
const R = (parts) => (Array.isArray(parts) ? parts : [parts]).map(x => typeof x === "string" ? run(x) : x);
const p = (parts, o = {}) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: o.after ?? 100, line: 288 }, keepNext: o.keepNext, children: R(parts) });
const h1 = (t) => new Paragraph({ spacing: { before: 300, after: 120 }, keepNext: true, pageBreakBefore: false,
  border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: "1F5FBF", space: 2 } }, children: [run(t, { bold: true, size: 30, color: "1F3864" })] });
const h2 = (t) => new Paragraph({ spacing: { before: 180, after: 80 }, keepNext: true, children: [run(t, { bold: true, size: 24, color: "1F3864" })] });
const li = (ref, parts, lvl = 0) => new Paragraph({ numbering: { reference: ref, level: lvl }, alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 276 }, children: R(parts) });
const b = (t) => run(t, { bold: true });
const i = (t) => run(t, { italics: true });
const say = (t) => new Paragraph({ spacing: { before: 40, after: 100, line: 276 }, indent: { left: 360 },
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: "9DB7E0", space: 8 } }, children: [run("Say: ", { bold: true, color: "1F5FBF" }), run(t, { italics: true })] });
const line = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
function table(rows, widths, o = {}) {
  if (widths.reduce((a, c) => a + c, 0) !== W) throw new Error("widths");
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: widths, rows: rows.map((cells, r) => new TableRow({ tableHeader: r === 0, cantSplit: true,
    children: cells.map((c, j) => new TableCell({ width: { size: widths[j], type: WidthType.DXA }, borders: { top: line, bottom: line, left: line, right: line },
      margins: { top: 50, bottom: 50, left: 90, right: 90 }, shading: r === 0 ? { fill: "DCE6F2", type: ShadingType.CLEAR, color: "auto" } : undefined,
      children: [new Paragraph({ alignment: (o.center || []).includes(j) && r > 0 ? AlignmentType.CENTER : AlignmentType.LEFT, children: R(r === 0 ? [b(c)] : c).map(x => x) })] })) })) });
}
const gap = () => new Paragraph({ spacing: { after: 60 }, children: [] });
const qa = (q, a) => [new Paragraph({ spacing: { before: 100, after: 30 }, keepNext: true, children: [run("Q. ", { bold: true, color: "C0392B" }), run(q, { bold: true })] }),
  new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 80, line: 276 }, indent: { left: 360 }, children: [run("A. ", { bold: true, color: "1F7A3A" }), run(a)] })];

const children = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [run("Satya-Score: Phase 3 Review", { bold: true, size: 40, color: "1F3864" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [run("An AI Hallucination Detection & Scoring Framework", { italics: true, size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [run("Group 10 · Guide: Dr. R. R. Karwa · Dept. of AI & DS, PRMIT&R, Badnera-Amravati", { size: 20 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [run("Demo plan · how the system works · APIs and models · scoring · results · team roles · questions and answers", { size: 20, color: "555555" })] }),

  // 1
  h1("1. Before the Review (10 minutes earlier)"),
  li("num1", "Start the system (backend and website) at least 3 minutes before the meeting; it needs about 25 seconds to load the models."),
  li("num1", "Open http://localhost:5173/analyse and run one short check to warm it up."),
  li("num1", "Keep the four demo texts of Section 2 in a Notepad file, ready to copy and paste."),
  li("num1", "Close Chrome tabs and heavy apps (the local AI model needs memory); keep the laptop on charge and connected to the internet."),
  li("num1", "Keep the report, the IEEE paper and the results PDF open in another window, in case the guide asks for numbers."),

  // 2
  h1("2. Demo Plan (about 8 minutes)"),
  h2("Step 1: The problem in one sentence"),
  say("AI chatbots like ChatGPT and Gemini sometimes give wrong facts that look completely real. Our system checks an answer claim by claim, in English and Hindi, and shows which claims are true, false or uncertain, with evidence."),
  h2("Step 2: English answer (knowledge graph + AI cross-check)"),
  p([b("Paste: "), i("The capital of Australia is Sydney. Mahatma Gandhi was born in Porbandar. The Great Wall of China is visible from the Moon with the naked eye. Water boils at 100 degrees Celsius at sea level.")]),
  table([["Claim", "Result (checked live)", "Point out"],
    ["Capital of Australia is Sydney", "Hallucinated, score 0.00", "Wikidata decided it and shows the correct value: Canberra"],
    ["Gandhi born in Porbandar", "Verified, score 1.00", "Confirmed by Wikidata"],
    ["Great Wall visible from Moon", "Hallucinated, score 0.02", "No database has this; the passages and the AI both say false"],
    ["Water boils at 100 °C", "Verified", "Passages + AI + second reading"]], [2700, 2500, 4212]),
  gap(),
  p("Then open one claim card and explain the chips: Passages (Wikipedia evidence score), LLM (the AI's verdict and reason), Second reading / Check before flagging, and the wrong words underlined in the text."),
  h2("Step 3: Hindi answer"),
  p([b("Paste: "), i("भारत की राजधानी मुंबई है। ताजमहल आगरा में स्थित है।")]),
  p("Result: the first claim is Hallucinated, with the correct value नई दिल्ली from Wikidata; the second is Verified. Say that the whole pipeline works in Hindi."),
  h2("Step 4: Official statistics"),
  p([b("Paste: "), i("The population of India is about 500 million.")]),
  p("Result: Hallucinated, decided by the World Bank, which shows the official figure (about 1,46,38,65,525 for 2025). Say: numbers are checked against World Bank and WHO data, at the precision the claim is written in."),
  h2("Step 5: Published fact-check (Hindi rumour)"),
  p([b("Paste: "), i("यूनेस्को ने नरेंद्र मोदी को दुनिया का सर्वश्रेष्ठ प्रधानमंत्री घोषित किया है।")]),
  p("Result: Hallucinated, “fact-checked by Vishvas News: rated False”, found through the Google Fact Check Tools API."),
  h2("Step 6: The rest of the application"),
  li("bul", "Upload a .txt or .pdf file instead of pasting (Upload button)."),
  li("bul", "Sign in: the check is saved in History; open it again; export results as CSV or JSON."),
  li("bul", "Mention security: hashed passwords, secure cookies, limits on repeated sign-in attempts."),
  h2("Step 7 (optional): a long answer"),
  p("Paste a long chatbot answer (e.g. about cricket, about 26 claims) to show grouping into Hallucinated, Uncertain and Verified. Explain that predictions (“India will win the next World Cup”) are Uncertain on purpose, because no source can prove them."),

  h2("When the guide types his own text"),
  p("Let him type freely; these are the results we checked on the live system, so you know what he will see:"),
  table([["What he types", "What happens", "What to say"],
    ["Simple facts (capitals, birthplaces, founders, dates)", "Decided by Wikidata in a few seconds, with the correct value", "“A trusted source decided this, so its answer is final.”"],
    ["Current office holders (“Joe Biden is the current President of the US”)", "Hallucinated: Wikidata holds today’s office holder", "“The knowledge graph is updated continuously, unlike the AI model’s training data.”"],
    ["Numbers (population, GDP, life expectancy)", "Checked against World Bank / WHO", "“Numbers are compared at the precision the claim is written in.”"],
    ["Local facts (“Amravati University is in Pune”)", "Hallucinated through the passages + AI cross-check", "“No database row, so both readers had to agree.”"],
    ["Hindi, or Hindi and English mixed", "Each sentence is checked in its own language", "“The whole pipeline is bilingual.”"],
    ["Predictions or opinions (“India will win the next World Cup”)", "Uncertain", "“No source can prove the future, so the system does not guess.”"],
    ["Only a question or an opinion (“Who is the PM of India?”)", "Message: no claims could be extracted", "“Questions and opinions are not factual claims, so there is nothing to check.”"],
    ["A true claim that is rare or ambiguous", "May show Uncertain", "“Uncertain is not wrong: it means the evidence was not strong enough. We prefer that to a false alarm.”"]], [2900, 3100, 3412]),
  gap(),
  p([b("If a result looks wrong: "), run("open the claim card and read what the passages and the AI said. Explain which reader disagreed and why; the guide values an honest explanation of a limitation more than a perfect result. Keep long texts under about 25 claims so each check stays under about 30 seconds.")]),

  // 3
  h1("3. How the System Works"),
  li("num2", [b("Input: "), run("the user pastes text or uploads a .txt/.pdf file in the web app (React). The language is detected from the script (Devanagari means Hindi).")]),
  li("num2", [b("Claim extraction: "), run("the text is split into separate factual claims. English uses the spaCy parser (it also replaces “it/he” with the name it refers to); Hindi uses the Indic NLP Library. Questions, greetings and opinions are skipped.")]),
  li("num2", [b("Evidence retrieval: "), run("each claim is turned into a vector by the XLM-R sentence encoder; FAISS finds the 10 most similar of about 1 lakh Wikipedia passages (English + Hindi). Missing articles are fetched from Wikipedia on demand.")]),
  li("num2", [b("Trusted sources first: "), run("World Bank / WHO statistics and Wikidata facts are checked in parallel; then published fact-checks (Google Fact Check API). If a source answers, it decides, and the correct value is shown.")]),
  li("num2", [b("Inference: "), run("the mDeBERTa model reads the passages and gives a passage score s (0 = contradicted, 1 = supported). Only passages about the claim’s own subject may contradict it.")]),
  li("num2", [b("LLM cross-check (Version 2): "), run("for claims no source decided, the AI model gpt-oss-20b reads the claim with the top 5 passages and gives a verdict and a reason. The agreement rule (Section 5) combines it with s. A second reading of all 10 passages is done before flagging a claim, or to confirm a claim that leans true.")]),
  li("num2", [b("Output: "), run("each claim gets a verdict, a score, its evidence, the readers’ verdicts and the wrong words marked; the whole text gets an overall verdict. Signed-in users’ checks are saved in SQLite.")]),

  // 4
  h1("4. Technologies, APIs and Models"),
  table([["Part", "What we use", "Purpose"],
    ["Frontend", "React + TypeScript, Vite, Tailwind CSS", "Web application"],
    ["Backend", "Python 3.13, FastAPI, Uvicorn; SQLite", "REST API (/detect, /auth, /history), accounts and history"],
    ["Claim extraction", "spaCy (en_core_web_sm); Indic NLP Library", "Split English / Hindi text into claims"],
    ["Sentence encoder", "paraphrase-xlm-r-multilingual-v1 (XLM-R)", "Turn claims and passages into vectors"],
    ["Vector search", "FAISS, about 1 lakh Wikipedia passages (EN + HI)", "Find the 10 most relevant passages"],
    ["Inference model", "mDeBERTa-v3-base-mnli-xnli", "Does a passage support or contradict a claim?"],
    ["LLM", "gpt-oss-20b (OpenAI open weights, Apache 2.0, 21B parameters)", "Second reader for claims no source decides"],
    ["LLM services", "Groq API → OpenRouter API → Ollama on the laptop (in this order)", "Fast cloud answers; local model as backup"],
    ["Knowledge graph", "Wikidata (entity search + SPARQL)", "Capitals, birthplaces, dates, authors…"],
    ["Statistics", "World Bank API; WHO Global Health Observatory API", "Population, GDP, life expectancy, literacy, infant mortality"],
    ["Fact-checks", "Google Fact Check Tools API", "Published ratings (e.g. Vishvas News, BOOM)"],
    ["Text source", "Wikipedia API (English and Hindi)", "Fetch articles missing from the index"],
    ["Testing", "pytest (323 automated tests)", "Every module tested"]], [1900, 3900, 3612]),

  // 5
  h1("5. How Scoring Works"),
  p("The first source that can decide a claim sets its score:"),
  table([["Situation", "Score", "Verdict"],
    ["Statistics or Wikidata confirm / contradict the claim", "1.0 / 0.0 (correct value shown)", "Verified / Hallucinated"],
    ["A published fact-check matches", "0.95 / 0.05", "Verified / Hallucinated"],
    ["Otherwise: passages + LLM (agreement rule below)", "mean of the passage score and the LLM’s confidence, kept inside the verdict’s range", "depends on agreement"]], [3900, 3112, 2400]),
  gap(),
  p([b("Verdict ranges: "), run("score below 0.35 = Hallucinated; 0.35 to 0.65 = Uncertain; above 0.65 = Verified.")]),
  p([b("Agreement rule (the novelty): ", )]),
  li("bul", [b("Verified "), run("only if the passages support the claim (s above 0.65) AND the LLM says Verified.")]),
  li("bul", [b("Hallucinated "), run("only if the LLM names a wrong fact AND the passages do not support it AND a second reading of all 10 passages does not find the claim stated.")]),
  li("bul", [b("Uncertain "), run("if they disagree, or if the LLM only says “no evidence” (missing evidence is not proof of a false claim).")]),
  p([b("Whole text: "), run("Hallucinated if at least one third of its claims are Hallucinated; otherwise Uncertain if any claim is not Verified; otherwise Verified. The overall score is the average of the claim scores.")]),
  p([b("CMHSA formula (designed): "), run("HalluScore = α·SemSim + β·NLI + γ·KG with α = 0 (similarity measures topic, not truth) and trained β ≈ γ ≈ 0.5; in practice a structured source overrides the formula.")]),

  // 6
  h1("6. Results to Quote"),
  table([["Measure (620 held-out public items, run once)", "Version 1", "Version 2"],
    ["False claims caught", "25%", "47%"],
    ["False claims wrongly passed as Verified", "22%", "6%"],
    ["False alarms on true claims", "11%", "13% (not significant)"],
    ["LLM alone: caught / false alarms", "–", "86% / 28%"]], [5212, 2100, 2100], { center: [1, 2] }),
  gap(),
  li("bul", "Altered country statistics caught: 137 of 137, no true figure contradicted. Knowledge graph raised AUC from 0.704 to 0.784 (pre-registered)."),
  li("bul", "Biggest gains in Hindi: Hindi Wikipedia errors caught 3% → 39%; Mu-SHROOM Hindi 7% → 45%."),
  li("bul", "3 of 4 targets fixed in advance were met; the target of doubling catches reached 1.85×."),
  li("bul", "Speed: about 5–10 s for a short answer with the cloud AI services; the system starts in about 25 s."),

  // 7
  h1("7. Team Roles and Responsibilities"),
  p([i("Suggested split, following the project’s code modules; adjust it to match who actually did what.")]),
  table([["Member", "Role", "Responsibilities"],
    ["Vivek Yeshwantrao Borkar", "Project lead; backend and LLM cross-check", "Overall architecture; FastAPI pipeline (member3_backend); claim extraction; LLM cross-check and agreement rule; Groq/OpenRouter/Ollama integration; deployment and demo"],
    ["Piyush Devidas Nande", "Models and scoring", "Sentence encoder and FAISS search; mDeBERTa inference and the evidence rule; CMHSA scoring, weight training and calibration (member1_model)"],
    ["Aasawari Sahebrao Jumade", "Data sources and knowledge graph", "Wikidata linking (English and Hindi templates); World Bank / WHO statistics; Google Fact Check matching; evidence corpus; datasets and annotation (member2_data)"],
    ["Arunima Tridip Wankhade", "Web application, testing and evaluation", "React web app (claim cards, highlights, history, export); accounts and security; automated tests; evaluation on FEVER, Mu-SHROOM and Hindi sets; reports and documentation"]], [2300, 2300, 4812]),

  // 8
  h1("8. Questions and Answers"),
  h2("Vivek: architecture, backend, LLM"),
  ...qa("Why do you check claim by claim instead of the whole answer?", "A wrong fact is usually one sentence inside a correct answer. Checking claims separately tells the reader exactly which statement is wrong and why."),
  ...qa("Why is an LLM used, and why not trust it alone?", "Inference models miss many errors, so an LLM adds knowledge. But used alone it flagged 28% of true claims as false, so its verdict counts only when the evidence agrees; false alarms dropped to 13%."),
  ...qa("Why gpt-oss-20b?", "It won our comparison on development data (balanced accuracy 57%, false alarms 7%); it is open-source (Apache 2.0) and can run on our laptop, so results are reproducible."),
  ...qa("What happens if the internet or the cloud AI is down?", "The LLM falls back from Groq to OpenRouter to the local Ollama model. If no LLM answers, the claim keeps its Version 1 verdict. Wikidata, statistics and fact-checks need internet."),
  ...qa("Why does a check take several seconds?", "Each claim needs web look-ups and one or two AI readings. With the cloud services it takes about 5–10 s; on the laptop alone the 13 GB model runs mostly on the CPU, so it is slower."),
  h2("Piyush: models and scoring"),
  ...qa("What does the sentence encoder do?", "It converts each claim and each Wikipedia passage into a vector (list of numbers) so that FAISS can find the passages with the closest meaning, in English and Hindi."),
  ...qa("What is NLI / the inference model?", "Natural Language Inference decides whether a passage entails (supports), contradicts or is neutral to a claim. We use mDeBERTa, trained on MultiNLI and XNLI, which covers Hindi."),
  ...qa("What is the evidence rule?", "Support from any relevant passage counts, but only a passage about the claim’s own subject may contradict it. This removed most false alarms caused by unrelated passages."),
  ...qa("Explain CMHSA and why α is zero.", "HalluScore = α·SemSim + β·NLI + γ·KG with trained weights. Similarity only shows a passage is on the same topic, not that it is true, so α was fixed at 0; training gave β ≈ γ ≈ 0.5."),
  ...qa("How are the 0.35 and 0.65 thresholds used?", "Below 0.35 is Hallucinated, above 0.65 Verified, in between Uncertain. The middle band lets the system say “not sure” instead of guessing."),
  h2("Aasawari: data sources and knowledge graph"),
  ...qa("What is Wikidata and how do you use it?", "An open knowledge graph of facts. We link names in the claim to Wikidata items and check relations such as capital, birthplace, founding date and author, in English and Hindi."),
  ...qa("What if two people share the same name?", "One matching namesake is enough to support a claim, but a contradiction needs every namesake with a value to disagree. This avoids false alarms."),
  ...qa("How do the statistics checks work?", "Population, GDP, life expectancy, literacy and infant mortality are compared with World Bank (and WHO) figures at the precision the claim is written in; if both agencies have a value they must agree."),
  ...qa("How is a published fact-check applied?", "We search the Google Fact Check Tools API; a “false” rating is used only if our claim means the same as the checked claim, so a negated claim does not inherit the wrong rating."),
  ...qa("Which datasets did you use?", "456 labelled chatbot claims (English and Hindi), and public sets: FEVER, Mu-SHROOM, TruthfulQA, X-FACT, plus Hindi Wikipedia sentences with one number changed."),
  h2("Arunima: web application, testing and evaluation"),
  ...qa("What does the user see for each claim?", "A verdict chip, the claim, the evidence source with a link, what the passages and the AI said, the correct value if a source has it, and the wrong words underlined in the text."),
  ...qa("How are user accounts kept secure?", "Passwords are hashed with scrypt and a salt; sessions use HttpOnly cookies; requests from other websites are refused; repeated failed sign-ins are blocked for 15 minutes."),
  ...qa("How did you test the software?", "323 automated tests (pytest) cover extraction, scoring, sources, the LLM rule, the API and accounts; all pass."),
  ...qa("How did you evaluate accuracy fairly?", "620 public test items never used during development, run once, with targets fixed in advance. We report all four criteria, including the one narrowly missed."),
  ...qa("What are the limitations?", "About half of false claims are left Uncertain; checks take seconds, not milliseconds; look-ups need internet; Hindi pronouns are not yet resolved; WHO data is for non-commercial use."),
];

const doc = new Document({
  styles: { default: { document: { run: { font: F, size: 22 } } } },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
    { reference: "num1", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
    { reference: "num2", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
  ] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1247, right: 1247 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Satya-Score · Phase 3 review · page ", font: F, size: 18, color: "666666" }), new TextRun({ font: F, size: 18, color: "666666", children: [PageNumber.CURRENT] })] })] }) },
    children }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT); });
