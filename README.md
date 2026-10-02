# SatyaScore

**Claim-level, bilingual (English + Hindi) hallucination detection for LLM output.**
Paste an AI-generated answer: SatyaScore splits it into factual claims, checks each one against
retrieved Wikipedia evidence and the Wikidata knowledge graph, and marks every claim
**Verified**, **Uncertain** or **Hallucinated**, with a verdict for the whole text.

Research prototype (B.Tech capstone). Results and limits are measured, not assumed:
see **`RESULTS_SUMMARY.md`**.

---

## Run it (demo)

Two terminals, from the project folder.

**1. Backend (API)** — loads the evidence corpus and models, about a minute:
```powershell
.venv\Scripts\python.exe -m uvicorn member3_backend.api:app --port 8000
```
Ready when it prints `Application startup complete`. API docs: http://localhost:8000/docs

**2. Web app:**
```powershell
cd web
npm run dev
```
**On a phone** (same Wi-Fi): run `npm run dev:phone` instead and open the *Network* address it prints
(e.g. `http://192.168.x.x:5173`). The phone reaches the backend through the web server's `/api`
forwarding; the backend itself stays on localhost. Details: `PROJECT_GUIDE.md` §3.2a.

Open **http://localhost:5173** — the status pill should read *Online · 102,069 passages* (or *9,351* if the
expanded corpus has not been built on this machine; see First-time setup).

Internet is needed for Wikidata (knowledge-graph checks) and web fonts; without it the app still
runs, with no KG verdicts. Professional fact-checks need a free Google API key with the
"Fact Check Tools API" enabled, set in the backend's terminal before starting it (never commit or
share it): `$env:GOOGLE_FACTCHECK_KEY = "..."`; without it the app runs with no fact-checks. With an NVIDIA GPU and the CUDA build of PyTorch, a check takes a few
seconds; on CPU about 25 s per short passage.

### First-time setup
```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m spacy download en_core_web_sm
# optional GPU: CUDA build of PyTorch (match your installed torch version)
.venv\Scripts\python.exe -m pip install "torch==<version>" --index-url https://download.pytorch.org/whl/cu130
cd web; npm install; cd ..
# the 102,069-passage index (git-ignored, ~380 MB; ~45 min, mostly polite Wikipedia downloads)
.venv\Scripts\python.exe build_corpus_expanded.py
```

---

## How it works

| Stage | What it does | Code |
|---|---|---|
| Claim extraction (FR-01) | English: dependency-parse decomposition + coreference, with a sentence-level safety net. Hindi: sentence-level | `member3_backend/claim_extractor.py` |
| Retrieval (FR-02/03) | XLM-R embeddings; FAISS IVF index over **102,069 Wikipedia passages** (89,594 EN, 12,475 HI): the 245-article base corpus + 3,021 more articles (Wikipedia Vital Articles and their Hindi versions, plus articles fetched by expansion) built by `build_corpus_expanded.py`; **top-10 passages** per claim above a relevance cut (a recorded product choice, `results/topk_eval.md`) | `member1_model/embeddings.py`, `member3_backend/faiss_retriever.py` |
| NLI | `mDeBERTa-v3-base-mnli-xnli` judges each claim against each passage | `member1_model/nli_scorer.py` |
| Evidence rule | **Support first; only an on-topic passage (its article title appears in the claim; long titles such as "Comparison of X and Y" must match in full) may contradict; no usable evidence → Uncertain.** Stops "about something else" being read as "false" (false alarms on fresh true statements 33 → 8 of 99), at the cost of catching fewer real hallucinations until the LLM verifier is added — a recorded product choice, `results/aggregation_eval.md`. `SATYASCORE_AGGREGATION=legacy` restores the old rule | `member3_backend/evidence_rules.py` |
| Knowledge graph | Wikidata: birthplace, place of death, capital, location, office, founder… English relation phrases and **Hindi relation templates**; place names (and all Hindi names) matched by exact name, so a place is never linked to a same-named non-place | `member2_data/entity_linker.py`, `member2_data/wikidata_connector.py` |
| Professional fact-checks | **On by default** (needs `GOOGLE_FACTCHECK_KEY`, see below). Google Fact Check Tools API (PIB, Factly, Vishvas News, BOOM, AFP, Snopes…). A fact-check decides a claim only if its rating logically carries over, judged by NLI: rated False → our claim must entail the checked claim; rated True → the checked claim must entail ours; any contradiction (e.g. a negation) or a qualified rating ("Misleading", "Partly false") → no decision. Met its fixed rule: 0 wrong decisions on all sets, rumours caught 3 → 10 of 25 (`results/factcheck_eval.md`). `$env:SATYASCORE_FACTCHECK = "false"` turns it off | `member2_data/factcheck.py`, `member3_backend/factcheck_rules.py` |
| Scoring (CMHSA, FR-04) | **When the KG answers, it decides the claim**; otherwise the trained weighted fusion. Verdicts: < 0.35 Hallucinated, 0.35–0.65 Uncertain, > 0.65 Verified; calibrated P(Verified) with a 95% interval | `member1_model/cmhsa.py`, `member1_model/calibration.py` |
| Whole text | Hallucinated if ≥ 1/3 of claims are Hallucinated; else Uncertain if any claim is Hallucinated or Uncertain; else Verified | `member1_model/cmhsa.py` (`aggregate_document`) |
| Wikipedia expansion | **On by default.** Searches Wikipedia for each claim and adds the articles it finds to the index without a rebuild (FR-03), so topics outside the 245-article corpus get real evidence. With the evidence rule it raised correct verdicts on train 110 → 125 of 303 with no more false alarms, and on fresh true Wikipedia sentences 43% → 78% Verified (`results/unseen_eval.md`). Needs internet; a failed lookup is skipped; a first-time topic adds a few seconds. `$env:SATYASCORE_WIKI_EXPANSION = "false"` turns it off | `member3_backend/wiki_expander.py` |
| Orchestration | Runs the stages per request and times them | `member3_backend/pipeline.py` |

## Web app and accounts

`web/` (Vite + React + TypeScript): highlighted text, whole-text verdict, claims grouped by
verdict, language auto-detection, optional scores, `.txt`/`.pdf` upload, CSV/JSON export,
per-user history, and a **Sources** list: every Wikipedia article (English/Hindi) and Wikidata check
behind the verdicts, linked, with the one that decided each claim marked. Sign-up is open and sign-in optional: anyone can check text; signed-in checks
are saved to the user's own history on the server. Passwords are scrypt-hashed, sessions use
HttpOnly cookies, cross-site requests and repeated failed sign-ins are refused — details in
**`web/README.md`**. User data lives in `instance/satyascore.db` (git-ignored).

`frontend/` is the earlier React dashboard, kept as a fallback (same port; run one at a time).

## API

| Endpoint | Purpose |
|---|---|
| `GET /health` | status and number of evidence passages |
| `POST /detect` | `{text, language}` → claims, verdicts, scores, whole-text verdict |
| `POST /extract-text` | `.txt` / `.pdf` upload → text |
| `POST /auth/register`, `/auth/login`, `/auth/logout`; `GET /auth/me` | accounts (session cookie) |
| `GET /history`, `GET` / `DELETE /history/{id}` | the signed-in user's saved checks |

Callers: the web app (session cookie or anonymous, 20 checks/min per IP), or scripts with the
`X-API-Key` header (dev key `dev-key-satyascore-2026`; never sent by the web app).

## Results in one paragraph

On relational claims (round 3) the knowledge graph is right whenever it answers and, letting it
decide, raises verdict accuracy well above NLI alone — though overall still only around an
"always Verified" baseline, because claims it cannot check fall back to NLI. On the descriptive
456-claim dataset, no configuration beats that baseline; stronger NLI models did not help, so
the limit is evidence coverage and claim type, not the judging model. Round-3 labels were
AI-assisted and annotator-verified. Every figure, with confidence intervals and limitations:
**`RESULTS_SUMMARY.md`**.

## Repository map

```
member1_model/     embeddings, NLI, CMHSA scoring + calibration, LLM verifier (under evaluation)
member2_data/      Wikidata connector, entity linker (EN + HI), fact-check client, annotation schema, IAA
member3_backend/   API, accounts (auth.py), pipeline, claim extractor, FAISS retriever
web/               web app (current)            frontend/  earlier dashboard (fallback)
round3/            pre-registration, questions, claims, annotator sheets, signals
results/           every measured result (*.md, *.csv)
tests/             225 tests
```

## Reproducing the results

```powershell
# the 456-claim experiment
python build_gold_final.py; python build_corpus.py; python recompute_signals.py
python flag_quality.py; python make_clean_split.py
python -m member1_model.train_weights --csv gold_train_clean.csv --languages en hi
python honest_ablation.py --train gold_train_clean.csv --test gold_test_clean.csv --out results/ablation_clean_no_semsim.json --table ablation_clean_no_semsim.md
# round 3 (see round3/PREREGISTRATION.md for the order and every deviation)
python analyze_round3.py; python round3_kg_fix.py; python round3_kg_decides.py
# model comparisons
python nli_model_search.py          # GPU recommended
python llm_verifier_eval.py         # needs GROQ_API_KEY in your own shell; resumable
python wiki_expansion_eval.py       # Wikipedia index expansion; GPU recommended
python factcheck_eval.py            # professional fact-checks; needs GOOGLE_FACTCHECK_KEY in your own shell
python diagnose_true_claims.py; python aggregation_eval.py; python unseen_eval.py; python topk_eval.py
python build_calibration_live.py --expansion   # P(Verified) tables on live scores
# the summary (reads everything above)
.venv\Scripts\python.exe generate_results_summary.py
```
Run `.xlsx`-reading scripts with `.venv\Scripts\python.exe` (needs `openpyxl`).

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```

## Known gaps

No email verification or password reset; rate limits are in-memory (single process); the
`Dockerfile` packages the API only and has not been re-tested since accounts and the KG changes;
Marathi is out of scope. Full list: `RESULTS_SUMMARY.md` §12.
