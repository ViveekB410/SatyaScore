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
Open **http://localhost:5173** — the status pill should read *Online · 9,351 passages*.

Internet is needed for Wikidata (knowledge-graph checks) and web fonts; without it the app still
runs, with no KG verdicts. With an NVIDIA GPU and the CUDA build of PyTorch, a check takes a few
seconds; on CPU about 25 s per short passage.

### First-time setup
```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m spacy download en_core_web_sm
# optional GPU: CUDA build of PyTorch (match your installed torch version)
.venv\Scripts\python.exe -m pip install "torch==<version>" --index-url https://download.pytorch.org/whl/cu130
cd web; npm install
```

---

## How it works

| Stage | What it does | Code |
|---|---|---|
| Claim extraction (FR-01) | English: dependency-parse decomposition + coreference, with a sentence-level safety net. Hindi: sentence-level | `member3_backend/claim_extractor.py` |
| Retrieval (FR-02/03) | XLM-R embeddings; FAISS IVF index over **9,351 Wikipedia passages** (7,361 EN, 1,990 HI, 245 articles); top-3 passages above a relevance cut | `member1_model/embeddings.py`, `member3_backend/faiss_retriever.py` |
| NLI | `mDeBERTa-v3-base-mnli-xnli` judges each claim against each passage | `member1_model/nli_scorer.py` |
| Evidence rule | **Support first; only an on-topic passage (its article title appears in the claim) may contradict; no usable evidence → Uncertain.** Stops "about something else" being read as "false" (false alarms on fresh true statements 33 → 8 of 99), at the cost of catching fewer real hallucinations until the LLM verifier is added — a recorded product choice, `results/aggregation_eval.md`. `SATYASCORE_AGGREGATION=legacy` restores the old rule | `member3_backend/evidence_rules.py` |
| Knowledge graph | Wikidata: birthplace, place of death, capital, location, office, founder… English relation phrases and **Hindi relation templates**; place names (and all Hindi names) matched by exact name, so a place is never linked to a same-named non-place | `member2_data/entity_linker.py`, `member2_data/wikidata_connector.py` |
| Scoring (CMHSA, FR-04) | **When the KG answers, it decides the claim**; otherwise the trained weighted fusion. Verdicts: < 0.35 Hallucinated, 0.35–0.65 Uncertain, > 0.65 Verified; calibrated P(Verified) with a 95% interval | `member1_model/cmhsa.py`, `member1_model/calibration.py` |
| Whole text | Hallucinated if ≥ 1/3 of claims are Hallucinated; else Uncertain if any claim is Hallucinated or Uncertain; else Verified | `member1_model/cmhsa.py` (`aggregate_document`) |
| Wikipedia expansion | **On by default.** Searches Wikipedia for each claim and adds the articles it finds to the index without a rebuild (FR-03), so topics outside the 245-article corpus get real evidence. With the evidence rule it raised correct verdicts on train 110 → 125 of 303 with no more false alarms, and on fresh true Wikipedia sentences 43% → 78% Verified (`results/unseen_eval.md`). Needs internet; a failed lookup is skipped; a first-time topic adds a few seconds. `$env:SATYASCORE_WIKI_EXPANSION = "false"` turns it off | `member3_backend/wiki_expander.py` |
| Orchestration | Runs the stages per request and times them | `member3_backend/pipeline.py` |

## Web app and accounts

`web/` (Vite + React + TypeScript): highlighted text, whole-text verdict, claims grouped by
verdict, language auto-detection, optional scores, `.txt`/`.pdf` upload, CSV/JSON export, and
per-user history. Sign-up is open and sign-in optional: anyone can check text; signed-in checks
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
member2_data/      Wikidata connector, entity linker (EN + HI), annotation schema, IAA
member3_backend/   API, accounts (auth.py), pipeline, claim extractor, FAISS retriever
web/               web app (current)            frontend/  earlier dashboard (fallback)
round3/            pre-registration, questions, claims, annotator sheets, signals
results/           every measured result (*.md, *.csv)
tests/             193 tests
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
