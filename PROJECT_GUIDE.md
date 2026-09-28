# SatyaScore — How the Project Works

*A complete walkthrough for reviewers: what it does, how every part works, why each choice was
made, what the results are, and what its limits are. Every number here comes from a file in
`results/` and can be re-run.*

---

## 1. In one paragraph

Large language models (ChatGPT-style chatbots) often state false facts confidently — this is called
**hallucination**. **SatyaScore** takes an AI-generated answer in **English or Hindi**, splits it into
individual factual **claims**, checks each claim against **Wikipedia** passages, the **Wikidata**
knowledge graph and **professional fact-checks**, and marks every claim **Verified**, **Uncertain** or **Hallucinated** — highlighted
in place in the original text, with a verdict for the whole text and a link to the source that
decided each claim. It runs as a full web application with accounts and history, on a laptop GPU,
in a few seconds per check.

---

## 2. Why this problem, and what is new

- **Hallucinations are local.** A 10-sentence answer can be 9 sentences correct and 1 wrong. A single
  "trust score" for the whole answer hides that one error. So SatyaScore works **claim by claim**
  and shows exactly *which* sentence is wrong.
- **Hindi is under-served.** Existing checkers are English-only. SatyaScore is **bilingual**
  (English + Hindi) end to end: Hindi claims, Hindi Wikipedia evidence, Hindi knowledge-graph lookups.
- **Three kinds of evidence, one score (CMHSA).** The PRD's design fuses three signals into one
  claim score: semantic similarity, natural-language inference and knowledge-graph verification.
- **Transparent.** Every verdict links to its evidence, so a user can verify it themselves.

---

## 3. How to run it (demo)

Two terminals in the project folder:

```powershell
.venv\Scripts\python.exe -m uvicorn member3_backend.api:app --port 8000     # backend (~30 s to load)
cd web; npm run dev                                                           # web app
```

Open **http://localhost:5173**. The status pill shows *Online · 102,069 passages*. Internet is needed
(Wikipedia/Wikidata lookups). Try: *"Cricket is a bat-and-ball sport played between two teams usually
with 11 players per team. The capital of Japan is Beijing. Mahatma Gandhi was born in Delhi."*
→ Verified, Hallucinated, Hallucinated, each with its source.

---

## 4. The big picture

```
 Browser (web/)                       Backend (FastAPI, member3_backend/api.py)
 ──────────────                       ─────────────────────────────────────────
 paste text / upload .txt .pdf        1. Claim extraction ........ split text into claims
 language auto-detected      ──────►  2. Embedding (XLM-R) ....... claim → vector
 (English / Hindi)                    3. Wikipedia expansion ..... fetch missing articles live
                                      4. Retrieval (FAISS) ....... top-10 evidence passages
                                      5. NLI (mDeBERTa) .......... does each passage support /
                                                                   contradict the claim?
                                      6. Evidence rule ........... combine passages safely
                                      7. Knowledge graph ......... Wikidata check (people,
                                                                   places, capitals…)
                                      7b. Fact-checks ............ professional fact-checks of
                                                                   the same claim (Google API)
                                      8. Scoring (CMHSA) ......... claim verdict
                                      9. Whole-text verdict, P(Verified), sources
 highlighted text, verdicts,  ◄──────
 sources, history, export             Sources: 102,069 Wikipedia passages (EN + HI, on disk)
                                               + live Wikipedia + live Wikidata
                                               + professional fact-checks
```

Code map: `member1_model/` (embeddings, NLI, scoring, calibration, LLM verifier) ·
`member2_data/` (Wikidata connector, entity linker) · `member3_backend/` (API, accounts, pipeline,
claim extractor, retriever, Wikipedia expander, evidence rules) · `web/` (the web app) ·
`results/` (every measured result) · `tests/` (200 automated tests).

---

## 5. The algorithm, step by step (with the "why")

### Step 1 — Claim extraction (`member3_backend/claim_extractor.py`)
**What:** splits the answer into short, checkable claims, and records where each came from in the
text (character positions) so the web page can highlight it in place.

- **English:** uses **spaCy** dependency parsing. A long sentence is decomposed into simple claims
  ("Gandhi was born in Porbandar and led the independence movement" → two claims). Pronouns are
  replaced by the person they refer to ("He led…" → "Mahatma Gandhi led…"; "her research" →
  "Marie Curie's research").
- **Hindi:** sentence-level (split on "।"), because no reliable Hindi dependency parser is wired in.
- **Lists:** a lead-in line ending in ":" followed by items becomes one claim per item
  ("Seek urgent medical care if there is: Severe abdominal pain" → *"Seek urgent medical care if there
  is severe abdominal pain."*), each highlighted on its own line.
- **Cleaning:** bracketed asides (dates, abbreviations) and markdown symbols are ignored; a blank line
  always ends a sentence (so headings are not glued to the next sentence).

**Why:** a checker can only judge a claim if the claim is clean and self-contained. Broken fragments
("Ambedkar is 14.") used to create false alarms; these rules removed them.

### Step 2 — Language and embeddings (`member1_model/embeddings.py`)
**What:** each claim becomes a 768-number vector using **XLM-R**
(`paraphrase-xlm-r-multilingual-v1`). The web app detects the language from the script
(Devanagari → Hindi).

**Why XLM-R:** it puts English and Hindi text **in the same vector space**, so a Hindi claim can find
English evidence and vice versa (cross-lingual retrieval). The PRD's MuRIL fallback was built and
measured: it found the right article far less often (Hindi 57% vs 87%), so it is off.

### Step 3 — Evidence index and Wikipedia expansion
**What:** **102,069 Wikipedia passages** (89,594 English, 12,475 Hindi) are pre-embedded and stored
(`build_corpus_expanded.py`): 245 core-topic articles, Wikipedia's **Vital Articles** (~1,000 core
topics chosen by Wikipedia editors) with their Hindi versions, and articles fetched earlier.
For each new claim, the system also **searches Wikipedia live** and adds any missing article to the
index (`member3_backend/wiki_expander.py`) — so unseen topics get real evidence.

**Why:** a checker is only as good as its evidence. Measured: with live expansion, true statements on
topics the index had not seen went from 43% Verified to 78% (`results/unseen_eval.md`).

### Step 4 — Retrieval (`member3_backend/faiss_retriever.py`)
**What:** **FAISS IVF** vector search returns the **10 passages** most similar to the claim.

**Why FAISS IVF:** it searches 100,000+ vectors in ~5 ms. Measured against exact search: same recall,
~7× faster (`results/ivf_vs_flat.md`). **Why 10:** with a large index the confirming passage is often
not in the top 3 (the cricket example was at rank 8; `results/topk_eval.md`).

### Step 5 — Natural Language Inference (`member1_model/nli_scorer.py`)
**What:** for every (passage, claim) pair, the model **mDeBERTa-v3-base-mnli-xnli** outputs three
probabilities: the passage **entails** (supports) the claim, **contradicts** it, or is **neutral**.

**Why NLI:** it checks *meaning*, not word overlap: "Paris is France's capital" supports "The capital
of France is Paris". The model is multilingual (English + Hindi). Three alternative models were tested
against it (including a larger one trained for fact-checking): none was better
(`results/nli_model_search.md`).

### Step 6 — The evidence rule (`member3_backend/evidence_rules.py`) — the key fix
**Problem found:** NLI models output "contradiction" when a passage is simply about **something else**.
Example (real): *"Cricket is … 11 players per team"* — a **football** passage gave contradiction 0.93
and out-shouted a **cricket** passage that supported it (0.92). The old rule ("the most extreme passage
wins") marked this true claim **Hallucinated**. On true sentences about unseen topics, 41% were
wrongly flagged (`results/diagnosis_true_claims.md`).

**The rule now:**
1. **Support first** — if any passage clearly supports the claim (entailment ≥ 0.5), it is supported.
2. **Only an on-topic passage may contradict** — the passage's Wikipedia article title must appear in
   the claim (a football article cannot contradict a cricket claim).
3. **No usable evidence → Uncertain**, never Hallucinated.

Result: the cricket claim → Verified (0.958); false alarms on fresh true statements fell from 33 to 8
of 99 (`results/aggregation_eval.md`).

### Step 7 — Knowledge graph (`member2_data/`)
**What:** for claims about **people, places, capitals, offices, founders** ("X was born in Y",
"X is the capital of Y"), the system looks the fact up in **Wikidata** live:
- the entity linker finds the Wikidata items (English phrases; **Hindi templates** such as
  "X का जन्म Y में हुआ"); places are matched by **exact name** (so "Erode" is the town, not a given name);
- it follows the place hierarchy (born in Agra ⇒ born in India);
- three outcomes: **supported**, **contradicted** (a different value for a one-value fact like
  birthplace), or **unknown** (no signal — never counted as false).

**KG decides when it answers:** when Wikidata gives a definite answer, it decides the claim.
**Why:** it is structured, curated data — in the round-3 study it was right on every claim it
answered (12/12), while NLI was wrong on 9 claims where they disagreed (`results/round3_kg_decides.md`).

### Step 7b — Professional fact-checks (`member2_data/factcheck.py`, `member3_backend/factcheck_rules.py`)
**What:** each claim the KG did not decide is searched in the **Google Fact Check Tools API**, which
collects verdicts published by professional fact-checkers (PIB Fact Check, Factly, Vishvas News,
BOOM, AFP, Snopes…), in English and Hindi. A fact-check decides the claim only when its rating
logically carries over, judged by the NLI model:
- rated **False** → our claim must *entail* the checked claim (if ours implies a false statement, ours is false);
- rated **True** → the checked claim must entail ours;
- **no contradiction** in either direction, so "hot water does **not** cure COVID" is never marked
  false because "hot water cures COVID" was;
- qualified ratings ("Misleading", "Partly false", "Mostly true") and disagreeing fact-checks decide nothing.

**Why:** Wikipedia rarely discusses viral rumours, so the NLI step leaves them Uncertain; fact-checkers
exist for exactly these. **Measured** (`results/factcheck_eval.md`, rule fixed before running):
0 wrong decisions on every set (including 8 negated true claims with 7–10 fact-checks found each);
rumours caught **3 → 10 of 25**; true claims marked Hallucinated unchanged (1 of 15). On the annotated
chatbot claims no fact-check applied (they are not rumours), so those results are unchanged.
Needs a free Google API key in the backend's environment (`GOOGLE_FACTCHECK_KEY`).

### Step 8 — Scoring (CMHSA, `member1_model/cmhsa.py`)
The PRD formula: **HalluScore = α·SemSim + β·NLI + γ·KG**, weights learned per language
(`weights_en.json`, `weights_hi.json`). Training set α (semantic similarity) to **0**: similarity
measures *topic*, not *truth* (below chance in Hindi). When the KG answers, it overrides the fusion.

**Verdict tiers (PRD FR-04):** score **< 0.35 → Hallucinated**, **0.35–0.65 → Uncertain**,
**> 0.65 → Verified**.

### Step 9 — Whole-text verdict, confidence and sources
- **Whole text:** Hallucinated if **one third or more** of its claims are hallucinated; otherwise
  Uncertain if any claim is hallucinated/uncertain; Verified only if every claim is verified.
- **P(Verified) with a 95% interval** (PRD FR-04; `member1_model/calibration.py`): the share of
  training claims with a similar score that were truly Verified. Honestly reported: for English the
  score adds little beyond the base rate (`results/calibration.md`).
- **Sources:** each claim shows the article, Wikidata check or fact-check that decided it, linked.

### Optional, not yet switched on — LLM verifier (`member1_model/llm_verifier.py`)
A large language model (gpt-oss-120b via Groq) reads the claim and its passages and gives a verdict.
**Why:** it can tell "false" from "about something else" — the NLI weakness. It is built and tested
in code; its evaluation is waiting on the API quota, under a decision rule fixed in advance.

---

## 6. Worked example (real numbers)

Text: *"Cricket is a bat-and-ball sport played between two teams usually with 11 players per team."*

| Step | Result |
|---|---|
| Claim extraction | 1 claim (the whole sentence) |
| Retrieval | 10 passages; #1 Cricket article, … #8 Cricket: "between two teams of eleven players each" |
| NLI | #8 entails 0.92; a football passage contradicts 0.94 (off-topic: title "Association football" not in the claim) |
| Evidence rule | support first → score 0.96 |
| Verdict | **Verified**, source: **Cricket (Wikipedia)** |

*"The capital of Japan is Beijing."* → the **Beijing** article contradicts it → **Hallucinated**.
*"Mahatma Gandhi was born in Delhi."* → Wikidata: birthplace Porbandar → **Hallucinated** (knowledge graph).

---

## 7. Backend engineering (`member3_backend/`)

| Part | Details |
|---|---|
| Framework | **FastAPI** (Python); automatic API docs at `/docs` |
| Endpoints | `GET /health`; `POST /detect` (text → claims, verdicts, scores, sources); `POST /extract-text` (.txt/.pdf upload); `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me`; `/history` (list, open, delete) |
| Accounts & security | passwords hashed with **scrypt** + random salt (never stored in plain text); sessions in **HttpOnly, SameSite cookies** (JavaScript cannot read them; only a hash is stored; expire in 7 days); **CSRF** protection (requests from other websites refused); **5 failed sign-ins → 15-minute lock**; same message for "wrong password" and "no such email" (no account guessing); security headers |
| Data | SQLite (`instance/satyascore.db`, never committed): users, sessions, each user's saved checks |
| Rate limits | 100 checks/min per signed-in user or API key; 20/min per network when anonymous |
| Speed | NVIDIA GPU (RTX 4050): typically **1–5 s per check**; a topic seen for the first time can take 10–15 s (live Wikipedia/Wikidata lookups) |
| Quality | **206 automated tests** (`pytest`) covering extraction, scoring, evidence rules, KG, security, API |

---

## 8. Frontend (`web/`)

| Part | Details |
|---|---|
| Stack | **React + TypeScript**, built with **Vite**; **Tailwind CSS**; **Radix/shadcn** primitives (dialogs, menus); Framer Motion (subtle transitions); React Router |
| Pages | Connecting (waits for the backend), **Analyse**, **History**, Sign in, Create account |
| Analyse page | text box (paste or upload), language **Auto / English / हिन्दी**, examples, Clear; results: whole-text verdict, the text with each claim highlighted (red / amber / green), claims grouped by verdict with their evidence, optional scores table, one-line sources, export CSV/JSON |
| Design | quiet "research instrument" style (Lora + Inter fonts, Noto for Hindi), accessible (keyboard, focus rings, contrast, verdicts never by colour alone), works on phone-sized screens |
| Details | highlights are exact even after emoji; saved checks reopen without re-running |

---

## 9. Data sources — what and why

| Source | Used for | Why |
|---|---|---|
| **Wikipedia (English + Hindi)** | evidence passages (102,069 stored + live search) | largest open, multilingual, citable encyclopedia; covers Hindi; free official API; the PRD names it |
| **Wikidata** | knowledge-graph facts (birthplace, capital, location, office, founder…) | structured, curated facts with Hindi labels; free official API; the PRD names it |
| **Google Fact Check Tools API** | professional fact-checks of viral claims (EN + HI) | verdicts by accredited fact-checkers (PIB, Factly, Vishvas News, AFP…) in the open ClaimReview standard; free official API; each result links to the fact-check article |
| **Wikipedia Vital Articles** | which articles to pre-load | ~1,000 core topics chosen by Wikipedia editors: broad, neutral coverage |
| Groq (llama-3.3-70b, gpt-oss-120b, qwen3.8-27b) | generating the chatbot answers used as **test data** | real LLM output, as the system will see in use |

**Why not scrape arbitrary websites:** scraping breaks many sites' terms of use, web pages contain
errors and AI-written text (we could "verify" a hallucination with another hallucination), and pages
change, which makes results irreproducible. Only official, open APIs are used.

---

## 10. How it was evaluated

**Method (research practice):**
- **Rules fixed before running** each experiment and committed to git first, so results could not be
  tuned after seeing them (`round3/PREREGISTRATION.md`). Where a product choice overrode a rule, it is
  recorded as such.
- **Grouped train/test split** (claims from the same question never in both); decisions made on the
  **train** split, test reported only.
- **Bootstrap 95% confidence intervals** on every comparison.

**Datasets:**
- **456 labelled claims** (English 266: 193 Verified / 47 Hallucinated / 26 Uncertain; Hindi 190:
  163 / 9 / 18) from llama-3.3-70b answers; inter-annotator agreement measured.
- **Round 3:** 40 labelled relational claims (people, places, capitals) from two newer LLMs.
- **True-by-construction sets:** lead sentences of Wikipedia articles (seen and unseen topics).

**Current system (`results/topk_eval.md`, `results/unseen_eval.md`):**

| Measure | Result |
|---|---|
| True Wikipedia sentences marked Verified (fresh set) | **92 / 106 (87%)**; wrongly Hallucinated 3 (3%) |
| Real chatbot claims (train, 303): correct verdicts | **170 / 303** (Uncertain counts as not correct) |
| True claims wrongly marked Hallucinated (train) | **11 / 258 (4.3%)** — down from 47 (18%) with the original rule |
| Real hallucinations caught (train) | **5 / 45** — the main open weakness |
| Knowledge graph, when it answers (round 3) | **12 / 12 correct** |
| Round 3 (relational claims) | 25 / 40 correct |
| Speed on GPU | ~1–5 s per check (was ~25 s on CPU) |

**Improvement history:** the original pipeline wrongly flagged 33% of true statements and could not
beat a trivial "call everything Verified" baseline. Diagnosis showed *why* (Step 6), and the fixes —
evidence rule, Wikipedia expansion, larger index, top-10 retrieval, extraction fixes — were each
measured before adoption.

---

## 11. Honest limitations

1. **It catches few real hallucinations** outside what the knowledge graph can check (5 of 45 on train).
   Most unsupported false claims come out **Uncertain** rather than Hallucinated. The design choice is
   deliberate: never wrongly accuse genuine text; the LLM verifier is the planned fix.
2. **"Research prototype. Verdicts are indicative, not authoritative."** — verdicts are strong hints;
   important claims (especially medical) should be confirmed at the linked source.
3. **Hindi** has too few labelled hallucinations (9) to measure Hindi accuracy reliably.
4. **Round-3 labels were AI-assisted** and checked by annotators (recorded as a deviation).
5. The knowledge graph covers relational facts only; other facts depend on Wikipedia text and NLI.
6. Needs internet for live Wikipedia/Wikidata; the dataset is smaller than the PRD's 3,000-claim target.

---

## 12. Questions a reviewer may ask

**Q: Why not just ask ChatGPT whether the answer is correct?**
An LLM checking an LLM can hallucinate too, gives no evidence, and is not reproducible. SatyaScore
checks against sources and shows them. (An LLM *reading our retrieved evidence* is being evaluated as
an extra signal — grounded in sources, not replacing them.)

**Q: Why claim-level instead of a whole-answer score?**
One false sentence in a long correct answer is the typical hallucination; a single score hides it.

**Q: What does "Uncertain" mean?**
No evidence found that clearly supports or contradicts the claim. It is not "false" — it means
"check this yourself".

**Q: How do you avoid calling true text false?**
Only evidence *about the claim's subject* can contradict it; any supporting evidence wins; no
evidence → Uncertain. False alarms on unseen true text: 33% → 3%.

**Q: What is NLI?** Natural Language Inference: given a premise (passage) and a hypothesis (claim),
decide entails / contradicts / neutral.

**Q: What is FAISS / IVF?** A library for fast similarity search over vectors; IVF clusters vectors so
only nearby clusters are searched (~5 ms over 100,000 passages).

**Q: Why Wikipedia and Wikidata?** Open, multilingual (Hindi), broad, citable, free official APIs,
named in the PRD. No scraping.

**Q: Why is semantic similarity's weight zero?** Similarity measures whether a passage is on the same
*topic*, not whether it says the same *thing*; training gave it no weight.

**Q: How accurate is it?** See §10: it rarely wrongly flags true text (≈3–4%) and verifies most true
text, but it catches few hallucinations outside knowledge-graph facts. We report this openly.

**Q: Is it secure?** Hashed passwords, HttpOnly session cookies, CSRF protection, sign-in throttling,
per-user private history, rate limits (§7).

**Q: What would you do next?** Evaluate and enable the LLM verifier; annotate more hallucinations
(especially Hindi); fine-tune the NLI model (PRD: DeBERTa + IndicXNLI); broaden knowledge-graph relations.

---

## 13. Glossary

| Term | Meaning |
|---|---|
| Claim | one checkable factual statement extracted from the text |
| Hallucination | a false or unsupported statement produced by an AI model |
| HalluScore | 0–1 support score for a claim (0 = contradicted, 1 = supported) |
| Embedding | a vector representing meaning; similar meanings → nearby vectors |
| NLI | natural language inference: entail / neutral / contradict |
| Knowledge graph (KG) | structured facts as (subject, relation, object), here Wikidata |
| CMHSA | the PRD's fused score of semantic similarity, NLI and KG |
| Calibration / P(Verified) | how often claims with a given score were truly verified in training data |
| Pre-registration | fixing the decision rule before running an experiment |

---

*Details and every number: `README.md` (setup), `RESULTS_SUMMARY.md` (all results, generated from
`results/`), `web/README.md` (web app and security), `round3/PREREGISTRATION.md` (study protocol).*
