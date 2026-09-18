# SatyaScore — Backend Handoff

Status as of 2026-09-17. The backend (Members 1 & 3 scope) is built, tested, and
reproducible. This doc says what's done, what each teammate consumes, and the
honest limitations. Numbers live in `RESULTS_SUMMARY.md` (auto-generated).

## What's built and working
- **Full pipeline**: text → claim extraction → XLM-R embedding → FAISS retrieval
  (bilingual corpus) → NLI + SemSim + KG → CMHSA fusion → verdict.
- **Real bilingual signals** recomputed on EN+Hindi Wikipedia evidence (`gold_final_scored.csv`).
- **Trained per-language CMHSA weights** (`weights_{en,hi}.json`, softmax-constrained).
- **The core ablation** (SemSim vs NLI vs full CMHSA) — the PRD's central experiment — run
  on the clean test set (`ablation_clean_*.md`, `results/`).
- **`/detect` REST API** — auth, rate limiting, ablation mode, custom threshold; loads
  trained weights + cached bilingual corpus at startup. Correct on in-domain claims.
- **Docker** (`docker compose up --build`), **108 passing tests**, full run-order in `README.md`.

## What each teammate consumes
- **Paper / report author (Member 4):** `RESULTS_SUMMARY.md` (all headline numbers +
  findings + limitations), `ablation_clean_*.md` (full ablation), `ANNOTATION_PROVENANCE.md`
  (dataset provenance proof). Regenerate numbers anytime: `python generate_results_summary.py`.
- **Frontend (dashboard):** the running API. `POST /detect` with header
  `X-API-Key: dev-key-satyascore-2026`, body `{"text","language":"en|hi","threshold?","active_signals?"}`.
  Returns `{claims:[{verdict,hallu_score,active_signals,note}], overall_score, processing_time_ms}`.
  Swagger at `/docs`. Start: `uvicorn member3_backend.api:app --reload`.
- **Data lead (Member 2):** IAA pilot kit in `iaa/` (two annotators fill the xlsx; run
  `python compute_iaa.py`).

## The result (one line)
Multi-signal fusion does **not** beat NLI alone; KG verification is inapplicable to
descriptive claims; naturally-occurring hallucination detection is weak (no config beats a
trivial always-Verified baseline). This is the **honest negative result the PRD §15
pre-registered** — publishable, with emphasis shifted to the fusion methodology, the
real-time claim-level architecture, and the evaluation-validity findings.

## Known limitations (state these in the paper)
- Dataset 456 claims (not 3,000), single-annotator, Verified-heavy; IAA pilot κ=0.15 (3-class) /
  0.53–0.61 (hallucination-vs-not, the operational metric).
- NLI is a pretrained mDeBERTa stand-in, not the PRD's DeBERTa-v3+IndicXNLI fine-tune.
- KG signal 0% coverage. Rule-based English claim decomposition degrades ~17% of EN claims.
- API latency ~40s/call on CPU (NLI is compute-bound); GPU → <1s.
- Baselines: majority, SemSim-only, NLI-only (TRUE-style) implemented; SelfCheckGPT/FActScore
  not (need multi-sample LLM output / infra the data lacks).

## Reproduce end-to-end
See `README.md` → "Reproducing the current results". All artifacts are present and tests pass.
```
python -m pytest            # 108 passing
python generate_results_summary.py
uvicorn member3_backend.api:app --reload
```
