# SatyaScore — Staged Improvement Plan

**Author:** Claude (Opus 4.8), from `FABLE_PLANNING_BRIEF.md`, verified against the code.
**Status (2026-09-24):** Phase 0 done (`a31c411`). Phase 1 done (`ccad2e2`, `1f65a35`).
Phase 2 done — **negative result: retrieval is not the bottleneck** (see the Phase 2 outcome
below). Next: Phase 3. The original plan text is kept below unedited; outcomes are added
beneath each phase.

## PRD traceability (checked against the PRD text, 2026-09-24)

| PRD requirement | Status | Where |
|---|---|---|
| FR-01 extraction, coref, spans | Met; the Phase 1 safety net emits whole-sentence claims where splitting broke (less atomic) | `claim_extractor.py` |
| FR-02 XLM-R primary + **MuRIL fallback** (transliterated Hindi) | Implemented compliantly (MuRIL queries search a MuRIL-embedded corpus, `build_muril_index.py`) but **off by default** (`SATYASCORE_MURIL_FALLBACK`): measured, MuRIL retrieval is far worse (Hindi R@3 0.575 vs 0.873, overall −0.194 [−0.240, −0.146], `results/retrieval_comparison.md`). Evidence-based deviation; measured on Devanagari Hindi (no transliterated eval set exists) | `embeddings.py`, `pipeline.py`, `api.py` |
| FR-03 FAISS, Wikidata + English fallback, 24h cache | Met (index is the experiment/demo corpus, not Wikipedia-scale) | `faiss_retriever.py`, `wikidata_connector.py` |
| FR-04 HalluScore **with confidence interval**, 3 tiers, threshold, ablation | Met: P(Verified) + 95% Wilson CI per claim, fitted on train (`results/calibration.md`) | `calibration.py`, `api.py` |
| FR-05 REST API | Met | `api.py` |
| FR-06 dashboard: red/amber/green, **bar chart, CSV/JSON export, .txt/.pdf upload** | Met in React (PRD says Streamlit). PDF needs `pdfminer.six` in the API's Python | `frontend/` |
| FR-07 ≥3,000 claims, 40/30/30, 2–3 annotators, HF release | **Not met** (456, ~78% Verified, 1 annotator) — team work | — |
| Goals: F1 ≥0.78 EN / ≥0.72 HI; beat 3/5 baselines; κ ≥0.65 | **Not met** (see `RESULTS_SUMMARY.md`) | — |
| Goal: KG ablation ≥ +0.03 ("crux of the novelty claim") | **Not met**: KG coverage 0% on these claims | — |
| NFR latency <500 ms/claim, <3 s/doc (GPU); fixed seeds | Met (median 104 ms; 2,414 ms/doc) | `results/latency_benchmark.md` |

**Honest ceiling (state this to the guide):** near-chance detector accuracy is *data-bound*.
Phases 0–4 make the system correct, calibrated, honest, and presentable, and they set up the
one thing that actually raises the accuracy ceiling — **annotation + NLI fine-tuning (Phase 5)**.
No algorithm change in 0–4 is expected to move headline AUC much on the current 456-claim set;
they make it *measurable, trustworthy, and demoable*, which is what a capstone review needs.

---

## What I verified in the code (corrections to the brief)

- **3-class verdicts: fully implemented, backend + frontend.** `cmhsa.py` thresholds 0.35/0.65;
  `frontend/src/lib/verdicts.js` renders all three. Guide ask #4 is **done**.
- **Whole-text + per-claim scores: already computed and returned by the API.** `DetectResponse`
  has `overall_score`; each claim has `hallu_score`. The **frontend hides them by design.** Guide
  ask #3 is a *surfacing* task, not new work.
- **BUG — mixed embedding spaces:** `embeddings.py` sends transliterated Hindi to MuRIL while the
  corpus is all XLM-R → invalid cosine at query time. Real correctness defect.
- **`overall_score` semantics are weak:** it's the *mean* of per-claim scores where higher = more
  *Verified*. One hallucination among many true claims gets averaged away, and the name reads
  backwards (it's "mean supportedness," not a hallucination score). Needs a better document metric.
- **`threshold` override collapses to binary** (`api.py _verdict`) — drops "Uncertain". Fine for
  ablation, wrong if the guide wants 3-class always-on.
- **Retrieval is pure dense cosine** (FAISS inner-product, `n_clusters=1` → flat); **no lexical/
  BM25**; SemSim uses only the top-1 passage. **No score calibration** anywhere.
- **KG path exists but yields nothing:** no Hindi NER (entities = []), English NER → Wikidata, but
  measured coverage is 0%. γ is dead weight today.

---

## Principles (apply to every phase)

1. **Integrity:** never fabricate labels/scores; never overwrite `gold_final.csv` (new files only);
   `RESULTS_SUMMARY.md` is generated, never hand-edited; keys stay git-ignored.
2. **Measure the same way before and after.** Each task names the *one metric* that decides it,
   computed with an existing tool, reported with its n and a bootstrap/Wilson CI.
3. **Experiment corpus for eval, demo corpus for the API — never mixed.**
4. **`pytest` green before and after each task** (baseline 114).
5. **Gate "more sources" behind retrieval quality** — more sources on weak ranking = more noise.

---

## Phase 0 — Quick wins + the correctness bug (≈1–2 days) · do first

Visible progress for the guide, plus one real fix. Low risk, high signal.

| Task | Files | Approach | Acceptance |
|---|---|---|---|
| **0.1 Surface scores** | `frontend/src/*`, `frontend/src/lib/api.js` | Show per-claim `hallu_score` and the document score (already in the API response) behind a small "show detail" toggle; keep the clean default. | Demo shows a document score + per-claim scores + all three verdict labels. |
| **0.2 Document-level metric** | `member3_backend/pipeline.py`, `api.py` | Add `document_verdict` + `supported_fraction` (share of claims Verified) and `n_claims_flagged` alongside `overall_score`. Don't remove `overall_score`. | `/detect` returns a document verdict that reflects the *worst*/aggregate, not a mean that hides one false claim. |
| **0.3 Fix mixed embedding spaces** | `member1_model/embeddings.py`, `pipeline.py` | Force a single encoder for both corpus and query (drop MuRIL routing, or embed corpus with the same routing). Simplest correct fix: XLM-R for everything, matching the eval scripts. | A transliterated-Hindi claim and a Devanagari claim retrieve from the same space; add a test asserting query/corpus use one model. |

*Impact: visible + one correctness fix. Won't move AUC.*

## Phase 1 — Foundations for trustworthy measurement (≈3–5 days)

Nothing downstream is believable until these hold.

| Task | Files | Approach | Acceptance (metric) |
|---|---|---|---|
| **1.1 Fix English claim extraction** | `claim_extractor.py`, `flag_quality.py`, `claim_quality.csv` | Add an English **sentence-level fallback** when decomposition produces a malformed fragment (reuse the quality checks in `flag_quality.py`); Hindi already does this. Report broken-fragment rate before/after. | Broken-EN rate drops from 17% (44/266) toward ~0; per-claim spans still exact (existing span test passes). |
| **1.2 Group train/test split** | `make_clean_split.py` | Replace `train_test_split` with `StratifiedGroupKFold` grouped by `source_query_id` (kills the leakage where 43/52 test questions also appear in train). Fold 0 as test, decided up front. | Assert train∩test share **zero** `source_query_id`; print Hallucinated counts per language/split. (Corrections spec Part B1.) |
| **1.3 Uncertainty in results** | `honest_ablation.py`, `generate_results_summary.py` | Every test metric prints its Hallucinated-count and a 2,000-resample bootstrap CI; mark any language with <10 positive test claims "too few to interpret". Regenerate the result set as a whole. | `RESULTS_SUMMARY.md` shows CIs + counts; no bare F1 on 2 examples. (Part B2/B3.) |

*Impact: credibility. This is what makes the guide trust every later number.*

## Phase 2 — Retrieval: the real accuracy bottleneck (≈4–6 days)

Do in order; re-run `diagnose_retrieval.py` after each and compare **source-article top-3 recall**
(not accuracy) — that's the metric that says whether retrieval improved.

| Task | Files | Approach | Acceptance (metric) |
|---|---|---|---|
| **2.1 Stronger encoder** | `embeddings.py`, `recompute_signals.py`, rebuild `corpus_vectors.npy` | Swap `paraphrase-xlm-r` → `intfloat/multilingual-e5-base` (or `LaBSE`). **Re-embed corpus AND claims with the same model** (E5 needs its `query:`/`passage:` prefixes). | Top-3 source-article recall (via `diagnose_retrieval.py`) rises vs the XLM-R baseline, per language. |
| **2.2 Calibrate the relevance threshold** | `pipeline.py` (`MIN_RELEVANCE_THRESHOLD`) | Plot the cosine distribution of known-relevant vs unrelated pairs on the experiment set; pick the threshold from data, not the current guessed 0.3. | Threshold chosen from a stated separation criterion; report claims gained/lost. |
| **2.3 Hybrid retrieval (BM25 + dense)** | new `member3_backend/lexical_retriever.py`, `pipeline.py` | Add BM25 over the same corpus; fuse ranks (RRF) with dense. Dense misses exact entities/dates/numbers — exactly what claims hinge on. | Top-3 recall improves over dense-only, especially on numeric/date claims. |

*Impact: highest technical lever. Prerequisite for "more sources".*

> **Phase 2 outcome (measured — the premise above was wrong).**
> Harness: `retrieval_eval.py` → `results/retrieval_comparison.md`, on all 417 gold claims whose
> source article is in the corpus. Decision rule fixed before running: adopt only if R@3 gain has
> a paired-bootstrap CI entirely above 0.
> - Current XLM-R retrieval already finds the source article in the top 3 for **87.5%** of
>   claims (top 10: 95%).
> - 2.3 BM25 −0.101 and hybrid −0.034 (both CIs below 0) → **rejected**.
> - 2.2 The threshold 0.3 filters nothing; the train-fitted 0.66 drops ~half the relevant
>   evidence → **0.3 kept**, documented in `pipeline.py`.
> - 2.1 Decided by `retrieval_bottleneck.py` → `results/retrieval_bottleneck.md`: even when NLI
>   was given a passage from the claim's own source article, English NLI AUC is 0.568
>   [0.429, 0.699] — not distinguishable from chance. Perfect retrieval would gain at most
>   +0.03 AUC. **E5/LaBSE not pursued; no download needed.**
>
> **Implication:** the detector's limit is NLI's use of the evidence and the labels, not
> retrieval. The levers that remain are calibration (Phase 3) and annotation + NLI fine-tuning
> (Phase 5). Phase 4's gate is met at article level, but more sources must be re-measured with
> `retrieval_eval.py` (distractors can lower recall).

## Phase 3 — Scoring & calibration (≈4–6 days)

Makes the 3-class output *mean* something.

| Task | Files | Approach | Acceptance (metric) |
|---|---|---|---|
| **3.1 Probability calibration** | new `member1_model/calibration.py`, `cmhsa.py`, `train_weights.py` | Fit isotonic/Platt on the *training* split so `hallu_score` is a calibrated probability; set the Uncertain band from calibrated confidence, not fixed 0.35/0.65. | Reliability curve + Brier score on the test split reported; thresholds fit on train only. |
| **3.2 Real abstention** | `pipeline.py`, `cmhsa.py` | When no passage clears the (calibrated) relevance bar or confidence is low, return **Uncertain "insufficient evidence"** explicitly rather than a mid score. | Uncertain becomes a principled abstention; measured share of abstentions. |
| **3.3 Contradiction signal + honest KG call** | `nli_scorer.py`, `pipeline.py`, `cmhsa.py` | Add contradiction-probability as its own signal (hallucination ≈ contradiction). Decide KG: either give it real coverage or **drop γ** and rename the fusion honestly. | Ablation reports the contradiction signal separately; the "multi-signal" claim matches reality. |

*Impact: directly serves the guide's 3-class/trustworthiness ask.*

## Phase 4 — More sources (≈3–5 days) · **gated behind Phase 2**

| Task | Files | Approach | Acceptance |
|---|---|---|---|
| **4.1 Expand the demo corpus** | `build_demo_corpus.py` | Add Wikipedia dump / news / domain passages; keep experiment corpus frozen for eval. Switch FAISS to real IVF once the corpus is large. | Live-demo coverage up; eval corpus untouched; retrieval latency still < target. |
| **4.2 (Optional) live retrieval** | new module, `pipeline.py` | Query-time Wikipedia/web fetch for out-of-corpus claims, behind a flag. | Out-of-corpus claims get evidence; caching + timeout so latency stays bounded. |

*Impact: coverage, not accuracy. Only pays off after Phase 2.*

## Phase 5 — The ceiling-raiser (gated on annotation)

| Task | Depends on | Approach | Acceptance |
|---|---|---|---|
| **5.1 More balanced annotation** | team | Scale claims, over-sample hallucinations (esp. Hindi, currently n=9), ≥2 annotators + adjudication, on clean extractions, blind. | A test split with real positive counts per language; trustworthy kappa. |
| **5.2 Fine-tune NLI** | 5.1 | Fine-tune DeBERTa on IndicXNLI + project data (the PRD's actual plan; a pretrained stand-in is used now). One-line `MODEL_NAME` swap once the checkpoint exists. | NLI AUC on the held-out split rises vs the pretrained baseline — the real accuracy gain. |

---

## Recommended first move (capstone-sized)

**Phase 0 → Phase 1 → Phase 2.1+2.2.** That sequence gives the guide, in order: visible
document + per-claim scores and 3 classes (0), a real bug fixed (0.3), trustworthy evaluation
(1), and a measured improvement on the actual bottleneck (2) — a coherent, honest arc you can
defend. Calibration (3) is the natural follow-on if time allows.

**What it will move:** correctness, retrieval recall, evaluation credibility, demo quality.
**What it won't move without Phase 5:** headline detector AUC on the current tiny dataset. Say
this plainly — a plan that admits the data ceiling is stronger than one that pretends otherwise.

## Effort summary

| Phase | Focus | Rough effort | Moves accuracy? |
|---|---|---|---|
| 0 | Surface scores, doc metric, embedding bug | 1–2 d | No (1 bugfix) |
| 1 | Extraction, split, CIs | 3–5 d | Enables measurement |
| 2 | Retrieval encoder + threshold + BM25 | 4–6 d | **Yes (biggest lever pre-annotation)** |
| 3 | Calibration, abstention, contradiction/KG | 4–6 d | Trustworthiness > raw AUC |
| 4 | More sources | 3–5 d | Coverage only (gate on 2) |
| 5 | Annotation + fine-tuning | team + 3–5 d | **Yes (the ceiling)** |
