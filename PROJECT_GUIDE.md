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

### 3.1 One-time setup: the fact-check key
Professional fact-checks need a free Google API key (Google Cloud Console → enable **Fact Check
Tools API** → Credentials → Create API key). Save it once for your Windows account, in your own
terminal, then close and reopen the terminal:

```powershell
[Environment]::SetEnvironmentVariable("GOOGLE_FACTCHECK_KEY", "your-key", "User")
[bool][Environment]::GetEnvironmentVariable("GOOGLE_FACTCHECK_KEY", "User")   # True = saved (key not shown)
```

The key is never stored in the project or on GitHub. Without it, the app runs normally with no
fact-checks.

### 3.2 Start it
Two terminals in the project folder:

```powershell
.venv\Scripts\python.exe -m uvicorn member3_backend.api:app --port 8000     # backend (~30 s to load)
cd web; npm run dev                                                           # web app
```

The backend is ready when it prints `Application startup complete`. It should also print
`fact-checks ON; GOOGLE_FACTCHECK_KEY set`. Open **http://localhost:5173**; the status pill shows
*Online · 102,069 passages*. Internet is needed (Wikipedia, Wikidata and fact-check lookups).

**Before the audience arrives:** sign in and run each example below once. Lookups are then cached
(faster), and every check is saved in **History**: a backup if the internet is slow.

### 3.2a On a phone (same Wi-Fi)
Start the web app with `npm run dev:phone` instead of `npm run dev`; the backend command is unchanged.
The web app prints two addresses:

```
➜  Local:   http://localhost:5173/
➜  Network: http://192.168.x.x:5173/     ← open this one on the phone
```

- **Connection:** the phone must be on the same Wi-Fi as the laptop. The first time, Windows asks
  whether Node.js may use the network: allow it on **Private networks**. If the phone cannot connect,
  set the laptop's Wi-Fi to *Private* (Settings → Network → Wi-Fi → network properties).
- **Security:** the phone talks only to the web app, which forwards checks to the backend inside
  the laptop. The backend itself stays private to the laptop, and requests from other websites are
  still refused.
- **Sign-in:** works on the phone, but it is a separate sign-in from the laptop's.
- **Both at once:** the laptop can keep using http://localhost:5173 at the same time.

### 3.3 Demo script (about 10 minutes)
The results below were checked on the live system.

| # | Paste this | Expected result | What it shows |
|---|---|---|---|
| 1 | *Cricket is a bat-and-ball sport played between two teams usually with 11 players per team. The capital of Japan is Beijing. Mahatma Gandhi was born in Delhi.* | **Verified** (Cricket, Wikipedia, with the supporting sentence) · **Hallucinated**, *Correct fact: Japan · capital: Tokyo* · **Hallucinated**, *Correct fact: Mahatma Gandhi · place of birth: Porbandar*; whole text Hallucinated, overall score 0.32 | claim-by-claim checking, in-place highlights, Wikipedia and Wikidata evidence, the correct fact for each error |
| 2 | *UNESCO declared Narendra Modi the best prime minister in the world.* | **Hallucinated**, "fact-checked by FACTLY (fact-check: FALSE)", linked | professional fact-checks; click the link to show the real article |
| 3 | *Drinking hot water does not kill the coronavirus.* | **not** Hallucinated (Verified), although fact-checks exist for "hot water kills coronavirus" | safety: a fact-check counts only if it is about the same claim; negations are blocked |
| 4 | *यूनेस्को ने नरेंद्र मोदी को दुनिया का सर्वश्रेष्ठ प्रधानमंत्री घोषित किया है।* (language on **Auto**) | **Hallucinated**, fact-checked by विश्वास न्यूज (Vishvas News) | Hindi end to end; language detected automatically |
| 5 | a short answer from any chatbot, or a built-in example | claims grouped by verdict | **Show scores**, **Export** (CSV/JSON), **History** |

Then walk through the pipeline diagram (§4) and, optionally, the API docs at
http://localhost:8000/docs.

**What to say at each step:**
1. *The problem:* "Chatbots state false facts confidently, and usually only one sentence of an
   answer is wrong. SatyaScore checks each claim separately, in English and Hindi, and shows the
   source for every verdict."
2. *Live growth:* the passage count in the status pill rises during the demo. When a claim is about
   a topic the index lacks, the matching Wikipedia article is fetched and added on the spot. The text
   users paste is never added as evidence.
3. *Numbers* (all in `results/`):
   - fresh true sentences wrongly flagged: 33% → 3%;
   - the knowledge graph was right on 12/12 claims it answered;
   - fact-checks: 0 wrong decisions, rumours caught 3 → 10 of 25;
   - every rule was fixed before its test was run.
4. *Limits (say them openly):* hallucinations are caught reliably only where Wikidata or a
   fact-checker covers them. Otherwise the answer is usually **Uncertain**, a deliberate choice not
   to call true text false. Hindi has less evidence. The LLM verifier is built but not yet evaluated.

### 3.4 If something goes wrong

| Problem | Fix |
|---|---|
| A check takes 10–15 s | normal for a topic seen for the first time (live Wikipedia lookup); or open the saved check from **History** |
| Page stuck on "Connecting" | the backend is not running or still loading: check its terminal |
| Phone cannot open the Network address | same Wi-Fi? laptop network set to *Private*? web app started with `npm run dev:phone`? |
| Page goes blank after an edit to the code | restart the web app (`npm run dev`) and reload with Ctrl + Shift + R |
| No fact-checks shown | the backend was started from a terminal opened before the key was saved: open a new terminal and restart it |
| No internet | stored passages still work; Wikidata and fact-checks do not. Use saved checks in **History** |

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
`results/` (every measured result) · `tests/` (245 automated tests).

---

## 5. The algorithm, step by step (with the "why")

### Step 1 — Claim extraction (`member3_backend/claim_extractor.py`)
**What:** splits the answer into short, checkable claims, and records where each came from in the
text (character positions) so the web page can highlight it in place.

- **English:** uses **spaCy** dependency parsing. A long sentence is decomposed into simple claims
  ("Gandhi was born in Porbandar and led the independence movement" → two claims). Pronouns are
  replaced by what they refer to, following the **topic** (the sentence subject), not the last name
  mentioned: in *"The Taj Mahal is located in Agra, Uttar Pradesh. It was completed in 1653."* the
  second claim is *"The Taj Mahal was completed in 1653"*. The old nearest-name rule produced
  *"Uttar Pradesh was completed in 1653"*, a false claim made from true text. Measured on 400
  held-out Wikipedia introductions (`results/coref_eval.md`, rule fixed before the run): pronouns
  resolved to the article's subject 93 → 277, wrong 206 → 128.
- **Only factual sentences are checked:** questions, pleasantries ("I hope this helps!"), advice
  ("You should visit it in winter"), opinions ("I think…") and commands are skipped. They cannot be
  verified and only made the whole-text verdict Uncertain. None of the 419 annotated claims is skipped.
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
- **capital claims**, in either phrasing ("The capital of X is Y", "Y is the capital of X", and the Hindi
  forms), are checked from the country's side: a country has one current capital on Wikidata, so a
  different city is a clear contradiction ("The capital of Australia is Sydney" → Canberra). A capital
  lying inside the claimed city counts as support ("Delhi is the capital of India": New Delhi is in Delhi);
- **dates** after "born in / died in / founded in" (and "born on…", and the Hindi forms) are checked
  against Wikidata's date of birth / death / founding, as precisely as the claim states them
  ("1869" to the year, "2 October 1869" to the day). Before, a year was read as a *place*: Wikidata
  has an item for the year 1869, so *"Mahatma Gandhi was born in 1869"* was marked Hallucinated.
  The subject is matched by exact name; if several items share it (two Michael Jordans), any match
  supports and only all disagreeing contradicts. Early dates where the old and new calendars
  disagree are not judged;
- **more fact types** (`member2_data/kg_extra.py`), each a common chatbot error, in English and Hindi:
  **authorship** ("Premchand wrote Gitanjali" → *author: Rabindranath Tagore*), **current office**
  (a former holder is not "is": "Pratibha Patil is the President of India" → *Droupadi Murmu*),
  **quantities** (height, length, population, area, with units and tolerances: "Mount Everest is
  7,200 metres tall" → *8,849 m*) and **currency** ("जापान की मुद्रा यूरो है" → *जापानी येन*). On a probe
  of 30 unseen claims, wrong verdicts went from 6 to 0 (2 left Uncertain); no annotated claim changed;
- **official statistics** (`member2_data/official_stats.py`): a country's population, GDP, life expectancy,
  literacy rate and infant mortality, in English and Hindi, are checked against **World Bank Open Data** and the
  **WHO Global Health Observatory** (most recent year). The country is identified by its ISO code on Wikidata;
  where both agencies have a figure, both must agree, otherwise there is no verdict. A rounded figure is
  accepted at the precision it is written to. Tested on 40 random countries the checks were not built on, with
  the rule fixed in advance: false claims caught 137 of 137, true claims contradicted 0
  (`results/official_sources_eval_stats_seed6.md`). The first attempt failed the rule on one rounded figure and
  is recorded too (`…_seed5.md`);
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
- **Overall score** (shown beside the whole-text verdict; the PRD's `overall_score`): the average
  support score of the claims, 0 = contradicted, 1 = supported. Example: the cricket/Japan/Gandhi
  text scores **0.32** (0.96, 0.00 and 0.00 averaged). The verdict, not the average, is the result.
  An average can hide one false claim among true ones, which is why the verdict uses the share rule.
- **P(Verified) with a 95% interval** (PRD FR-04; `member1_model/calibration.py`): the share of
  training claims with a similar score that were truly Verified. Returned by the API and included in
  the CSV/JSON export; not shown on the results page. Honestly reported: for English the
  score adds little beyond the base rate (`results/calibration.md`).
- **Sources:** each claim shows the article, Wikidata check or fact-check that decided it, linked.
- **Explanations** (shown with each claim; they never change a verdict):
  - *Correct fact* (knowledge graph): the value Wikidata holds, in English or Hindi, e.g.
    *"Correct fact: Mahatma Gandhi · place of birth: **Porbandar**"*.
  - *Evidence sentence* (Wikipedia): the one sentence of the deciding passage that most supports
    or contradicts the claim (chosen by NLI). It is quoted only if it visibly addresses the claim:
    it must share a word with the claim beyond the article's name. Otherwise only the article is
    named. Example (measured before capital claims went to Wikidata): for *"The capital of Japan is
    Beijing"* the deciding passage was about Beijing's ring roads. The verdict was right, but the
    evidence was weak, so no sentence was quoted.
  - *Checked claim* (fact-checks): the claim the fact-checker rated.

### Evaluated and kept off — LLM verifier (`member1_model/llm_verifier.py`)
A large language model (gpt-oss-120b via Groq) reads the claim and its passages and gives a verdict.
**Measured** (`results/llm_verifier_expanded.md`, open mode, rule fixed in advance): it met its ranking rule
(train AUC 0.72 vs 0.55) and caught far more hallucinations (train 5 → 18 of 45; round 3 2 → 9 of 15), **but it
marked about 1 in 7 true claims Hallucinated** (train false alarms 9 → 35 of 258; test 3 → 9 of 66). Not flagging
genuine text is the project's first requirement, so it stays **off**, a recorded product choice. It would also
make the system depend on an external AI service at run time.

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

*"The capital of Japan is Beijing."* → Wikidata: Japan's capital is Tokyo → **Hallucinated** (knowledge graph).
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
| Quality | **245 automated tests** (`pytest`) covering extraction, scoring, evidence rules, KG, security, API |

---

## 8. Frontend (`web/`)

| Part | Details |
|---|---|
| Stack | **React + TypeScript**, built with **Vite**; **Tailwind CSS**; **Radix/shadcn** primitives (dialogs, menus); Framer Motion (subtle transitions); React Router |
| Pages | Connecting (waits for the backend), **Analyse**, **History**, Sign in, Create account |
| Analyse page | text box (paste or upload), language **Auto / English / हिन्दी**, examples, Clear; results: whole-text verdict with the overall score beside it, the text with each claim highlighted (red / amber / green), claims grouped by verdict with their evidence (the deciding sentence, the correct fact, or the fact-checked claim), optional scores table, one-line sources, export CSV/JSON |
| Design | quiet "research instrument" style (Lora + Inter fonts, Noto for Hindi), accessible (keyboard, focus rings, contrast, verdicts never by colour alone), works on phone-sized screens |
| Details | highlights are exact even after emoji; saved checks reopen without re-running |

---

## 9. Data sources — what and why

| Source | Used for | Why |
|---|---|---|
| **Wikipedia (English + Hindi)** | evidence passages (102,069 stored + live search) | largest open, multilingual, citable encyclopedia; covers Hindi; free official API; the PRD names it |
| **Wikidata** | knowledge-graph facts (birthplace, capital, location, office, founder…) | structured, curated facts with Hindi labels; free official API; the PRD names it |
| **World Bank Open Data**, **WHO Global Health Observatory** | official country statistics (population, GDP, life expectancy, literacy, infant mortality) | the official figures; free official APIs; two agencies cross-check each other |
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
7. **The NLI model largely ignores numbers:** "India became independent in 1950" can be Verified from a
   passage saying 1947. Dates of birth, death and founding are checked exactly by Wikidata, but other
   numbers are not. A "number guard" (Verified only if the evidence contains the claim's numbers) was
   built and tested under a rule fixed in advance (`results/number_guard_eval.md`). It cut wrongly
   Verified false-number claims from 27 to 3, but also removed Verified from too many true claims
   (−12% on Wikipedia, −29% on the annotated claims), so it was **not adopted** and stays off.
   Version 2 (years and numbers ≥ 100 only, the whole article as evidence; fresh test data,
   `results/number_guard_eval_v2.md`) cut wrongly Verified claims from 36 to 11 with **no** loss on
   the annotated chatbot claims, but true Wikipedia claims lost Verified 109 → 103 (−5.5%, limit 5%).
   It missed the fixed rule by one claim, so it is also **off**.
8. **MedlinePlus** (US National Library of Medicine health topics) was built as a second evidence source and
   tested under a rule fixed in advance (`results/official_sources_eval_medline.md`): on the training claims it gave
   more correct verdicts (160 → 166) but 2 more false alarms (9 → 11), so it was **not adopted** and stays off
   (`SATYASCORE_MEDLINE`). Health claims still rely on Wikipedia.
9. **Missed hallucinations, analysed** (`results/missed_hallucinations_analysis.md`): of the 45 train
   hallucinations, about 31 are artifacts of the old claim extractor (mostly wrong pronoun substitutions, since
   fixed) rather than chatbot errors, and about 14 are genuine reasoning errors (misconceptions,
   over-generalisations) that no lookup source can check. A stricter rule (only passages about the claim's subject
   may verify it) cut hallucinations wrongly Verified from 28 to 7 but removed Verified from most true claims
   (152 → 47) and added false alarms, so it was **not adopted** (`results/strict_support_eval.md`). An LLM judge
   catches more of them but was not adopted: it raises false alarms about four-fold (`results/llm_verifier_expanded.md`).
10. **Simple false common-sense statements can be Verified.** A user test found "Humans can breathe naturally
    underwater" Verified. On 15 common-sense statements (`results/evidence_rule_eval.md`, reported only) the live rule
    Verified **all 9 false ones** ("The Sun revolves around the Earth", "Humans have three lungs"): Wikipedia passages
    that describe or mention the idea are read by the NLI model as supporting it. Two fixes (Verified only with a
    supporting passage; strong support required from unrelated articles) were tested under a rule fixed in advance on
    fresh unseen sentences and **not adopted**: they removed Verified from too many true claims. This is the main
    weakness of NLI-based checking for general statements.
11. **Pronoun resolution is rule-based:** much better since following the sentence topic (93 → 277 right
   on held-out text), but still wrong sometimes ("Mumbai is its financial hub" → "Mumbai's").

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
