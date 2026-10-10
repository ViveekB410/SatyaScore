# SatyaScore — Backend Handoff

Status as of 2026-09-24. The backend (Members 1 & 3 scope) is built, tested, and
reproducible. This doc says what's done, what each teammate consumes, and the
honest limitations. Numbers live in `RESULTS_SUMMARY.md` (auto-generated). PRD status per
requirement: the traceability table in `IMPROVEMENT_PLAN.md`.

## What's built and working
- **Full pipeline**: text → claim extraction → XLM-R embedding → FAISS retrieval
  (bilingual corpus) → NLI + SemSim + KG → CMHSA fusion → verdict → whole-text verdict.
- **Real bilingual signals** recomputed on EN+Hindi Wikipedia evidence (`gold_final_scored.csv`).
- **Trained per-language CMHSA weights** (`weights_{en,hi}.json`, softmax-constrained).
- **The core ablation** (SemSim vs NLI vs full CMHSA) — the PRD's central experiment — on a
  test split grouped by source question (no leakage), with 95% CIs (`ablation_clean_*.md`).
- **`/detect` REST API** — auth, rate limiting, ablation mode, custom threshold, per-claim
  confidence interval (FR-04), whole-text verdict. **`/extract-text`** for .txt/.pdf upload.
- **Dashboard** (`frontend/`, React): red/amber/green highlighting, score chart, CSV/JSON
  export, file upload, per-claim scores with P(Verified) intervals.
- **Docker** (`docker compose up --build`), **137 passing tests**, full run-order in `README.md`.

## What each teammate consumes
- **Paper / report author (Member 4):** `RESULTS_SUMMARY.md` (all headline numbers +
  findings + limitations), `ablation_clean_*.md`, `results/*.md` (regroup, retrieval,
  calibration, extraction, round-2 label audit), `ANNOTATION_PROVENANCE.md`. Regenerate:
  `.venv/Scripts/python.exe generate_results_summary.py` (needs openpyxl, which is in `.venv`).
- **Frontend (dashboard):** the running API. `POST /detect` with header
  `X-API-Key: dev-key-satyascore-2026`, body `{"text","language":"en|hi","threshold?","active_signals?"}`.
  Returns `{claims:[{claim_id,text,verdict,hallu_score,active_signals,note,start_char,end_char,
  extraction_method,p_verified,p_verified_ci95,calibration_n}], document:{verdict,n_claims,
  n_verified,n_uncertain,n_hallucinated,supported_fraction}, overall_score, processing_time_ms}`.
  `POST /extract-text` (multipart `file`, .txt/.pdf) returns `{text}`. Swagger at `/docs`.
  Start: `python -m uvicorn member3_backend.api:app --port 8000`.
- **Data lead (Member 2):** round-1 IAA in `iaa/` (`compute_iaa.py`); round-2 kit in
  `annotation_round2/` (`compute_round2.py` → `results/label_audit.md`).

## The result (one line)
Multi-signal fusion does **not** beat NLI alone; KG cannot be evaluated here (0 of 456 gold
claims contain a linkable relation, `results/kg_ablation.md`); no configuration beats a trivial
always-Verified baseline. The cause is
not proven: the leading hypothesis is label reliability (IAA findings); retrieval was tested
and is not the main limiter at article level. This is the **honest negative result the PRD
§15 pre-registered**.

## Known limitations (state these in the paper)
- Dataset 456 claims (not 3,000), four annotators (the authors) sharing the claims, one per claim, Verified-heavy, all answers from
  one LLM. Grouped test split has only 8 EN / 2 HI hallucinated claims — too few to interpret
  Hallucinated-F1.
- IAA round 1: binary "hallucination vs not" **κ = 0.53** (headline; 0.61 on the well-formed
  subset, n = 49); 3-class κ = 0.15 because the annotators used different label schemes.
- NLI is a pretrained mDeBERTa stand-in, not the PRD's DeBERTa-v3 + IndicXNLI fine-tune.
- KG: the verifier is fixed (supported / contradicted / unknown — a failed or missing lookup is
  no longer scored as false; polite rate-limited Wikidata access), but no gold claim contains a
  linkable relation, so its effect is unmeasured. English claim extraction fixed for new text (broken 14.3% → 0%);
  the annotated gold claims keep 38 broken rows (excluded as not well-formed).
- **Latency, measured on a T4 GPU:** median 104 ms/claim (PRD < 500 ms met), 2,414 ms per
  10-claim document (< 3 s met); mean 1,171 ms (missed, driven by the KG network call). CPU
  is several times slower.
- FR-02 MuRIL fallback is built but off by default (`SATYASCORE_MURIL_FALLBACK`): measured,
  it retrieves far worse than XLM-R. The dashboard is React, not the PRD's Streamlit.
- Baselines: majority, SemSim-only, NLI-only (TRUE-style) implemented; SelfCheckGPT/FActScore
  not (need multi-sample LLM output / infra the data lacks).

## Reproduce end-to-end
See `README.md` → "Reproducing the current results". All artifacts are present and tests pass.
```
python -m pytest                                   # 137 passing
.venv/Scripts/python.exe generate_results_summary.py
python -m uvicorn member3_backend.api:app --port 8000
```
