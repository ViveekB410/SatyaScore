# SatyaScore — Working Session Chat Log

> Multilingual LLM hallucination detection (English/Hindi) — B.Tech capstone.
> Session date: 2026-09-10

---

## Context / Constraints established

- **Time left:** 2 weeks
- **Annotators:** 3 available (annotation compressed to ~2 days max)
- **Hardware:** RTX 4050 laptop GPU + Google Colab if needed
- **Scope:** English + Hindi only (no Marathi)
- **Current progress:** ~20–25% of the full PRD; full PRD not achievable in 2 weeks.

### Key files (live outside the repo, in `Downloads/`)
- `C:\Users\vivek\Downloads\unannotated_dataset_AI_PRELABELED.csv` — 456 rows, the file annotators use.
- `C:\Users\vivek\Downloads\CONFIRMATION_GUIDE.md` — fast confirmation workflow (15–30 sec/row, ~130–150 claims/person).
- `C:\Users\vivek\Downloads\SatyaScore_PRD_main.pdf` — product requirements.

---

## Core technical concepts

- **CMHSA (Composite Multilingual Hallucination Scoring Algorithm):**
  `HalluScore = α·SemSim + β·NLI_prob + γ·KG_conf`, with softmax-constrained weights (α+β+γ = 1).
  Thresholds: `<0.35` Hallucinated, `0.35–0.65` Uncertain, `>0.65` Verified.
- **Three verification signals:**
  - `SemSim` — FAISS cosine similarity.
  - `NLI_prob` — mDeBERTa (stand-in for a fine-tuned DeBERTa-v3 + IndicXNLI).
  - `KG_conf` — Wikidata SPARQL triple verification.
- **Ablation study** (SemSim vs SemSim+NLI vs full CMHSA) = the single most important experiment and the project's core novelty.
- **Dataset targets (FR-07):** ≥3,000 claims (have 456), balanced ~40% Hallucinated / 30% Uncertain / 30% Verified.
- **Annotation quality gate:** PRD wants 2–3 blind annotators + Cohen's κ ≥ 0.65.

---

## Known code blockers

- `dataset_pipeline/dataset_builder.py` → `to_training_csv` (lines 146–149) **skips** any row missing `gold_verdict` OR any of `sem_sim`/`nli_prob`/`kg_conf`. Since **all `kg_conf` are empty → 0 rows output.**
- `member1_model/train_weights.py` (line 43) does `float(row["kg_conf"])` → **crashes on empty `kg_conf`.**
- `member1_model/cmhsa.py` → `score_claim` (lines 119–124) **already** handles missing signals via renormalization — this is the reference pattern to port into `train_weights.py`.
- `member2_data/entity_linker.py` → `RELATION_TO_PID` has only 10 relations; expanding this table is how `kg_conf` gets populated.

`kg_conf` is a **double blocker**: empty training file **and** no ablation possible until it's filled.

---

## Chat transcript (key exchanges)

### User
> now what is to be done by me? [5-step to-do list about verifying 456 AI-prelabeled rows] … I want you to help me understand these steps.

### User
> how can you help me

### User
> (provided the PRD PDF)

### User
> verification will require time — can you estimate after verification how much work will be done in % and estimated time to complete project?

### User
> 2 weeks / 3 annotators / RTX 4050 (will use Colab if needed) / Hindi + English only

### User
> annotators' work will be done in 2 days max then

### User
> (provided `CONFIRMATION_GUIDE.md` and `unannotated_dataset_AI_PRELABELED.csv`)

---

## Verified dataset numbers (read-only scan of all 456 rows)

| AI-suggested verdict | Count | % |
|---|---|---|
| **Verified** | 436 | **95.6%** |
| Uncertain | 14 | 3.1% |
| Hallucinated | 6 | 1.3% |

| Language | Count | % |
|---|---|---|
| English | 266 | 58% |
| Hindi | 190 | 42% |

- Language split is well balanced for training two weight sets. **The class balance is the problem.**

---

## The pivotal issue

You're building a **hallucination detector**, and the dataset contains **6 hallucinated claims.**

- A model that blindly outputs "Verified" for everything scores **95.6% accuracy** — the CMHSA algorithm has to beat that, and on accuracy alone it basically can't.
- The metric that matters is **F1 on the Hallucinated class**, which would be computed on **6 examples** (~1–2 in a test split; ~3 per language). Not trainable or evaluable. The ablation would have no signal.
- Root cause: the 436 "Verified" mostly carry the generic rubber-stamp *"Consistent with well-established knowledge; no contradicting evidence found."* — the pre-labeling AI being lenient, not ground truth. A 15–30 sec/row confirmation pass mostly rubber-stamps the rubber-stamps.

**A pure κ is also impossible** with the current split design (~150/person, no overlap). Cohen's κ needs 2+ annotators labeling the *same* items.

---

## Recommendation — build balance, don't just confirm

Three things doable in parallel within ~2 annotator-days:

1. **Confirm + actively hunt** the 436 Verified — annotators' job is to *catch* errors (spot-check every number, date, name, citation), not approve.
2. **Inject known-bad claims** — deliberately author/collect genuinely false claims (wrong dates, fabricated citations, swapped entities) in EN+HI. Push Hallucinated toward ~30%, Uncertain ~20–30%.
3. **Carve a 50-claim triple-overlap set** — all 3 annotators label the same 50 items (~15–25 min each) → a real **Cohen's κ** to report.

**Options presented:**
- **A —** Confirm-only as planned (fastest; thin results section).
- **B —** Hybrid above (a dataset that actually shows the detector working).

---

## Latest user note (open thread)

> I have the claims but don't have the query text. If I have it in the file itself then it will be easy.

**Next step to address:** join the original `source_query_id` → query text back into the annotation CSV so annotators see the question each claim came from (needed for judging claim correctness in context). The `source_query_id` column already exists in the CSV; the query text needs to be looked up from the source queries file and added as a new column.

---

## Pending task list

| # | Task | Status |
|---|---|---|
| 1 | Reframe annotation kit (confirmation workflow already exists; blind kit superseded) | pending |
| 2 | Fix `kg_conf` blocker in `to_training_csv` + `train_weights` | **code done, pytest not yet run (Bash blocked)** |
| 3 | Expand `entity_linker` to populate `kg_conf` | pending |
| 4 | Merge annotations into `gold_verdict` + compute κ | blocked by #1 |
| 5 | Train CMHSA weights (en, hi) | blocked by #2, #4 |
| 6 | Run ablation + baselines + F1 evaluation | blocked by #3, #5 |
