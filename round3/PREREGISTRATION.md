# Round 3 — KG relational pilot: pre-registration

**Written and committed before any answer is generated or any claim is labelled.** Nothing below
may change after results are seen; any deviation is reported as a deviation.

## Why
The PRD calls the KG ablation "the single most important experiment". On the existing 456 gold
claims it cannot be measured: none contains a relation the KG can link (`results/kg_ablation.md`).
The team can annotate ~60–70 more claims, so this pilot tests KG **in its own domain — relational
facts** — with a scoped claim: "does KG help on relational claims?", not "in general".

## Data
- **Questions:** the 31 fixed English questions in `round3/questions.json` (birthplace, place of
  death, capital, headquarters, founder, location, membership), mixing well-known and moderately
  obscure entities.
- **Answers:** one answer per question from `llama-3.3-70b-versatile` via Groq, with the unchanged
  dataset generator (`dataset_pipeline.response_collector.OpenAICompatibleGenerator`: system
  prompt "Answer factually and concisely. Answer in English.", temperature 0.7).
- **Claims:** extracted with the current `ClaimExtractor`. A claim enters the pilot if it contains a
  relation phrase from `RELATION_TO_PID` (a text rule, applied before any KG lookup). If more than
  70 qualify, 70 are sampled with seed 42.
- **Labels:** two annotators label every claim **blind** (no AI verdict, no scores), Verified /
  Uncertain / Hallucinated, following `annotation_round2/INSTRUCTIONS.md`.
- **Gold for analysis:** claims both annotators label the same, as Verified or Hallucinated.
  Uncertain and disagreements are excluded and reported (counts + the disagreement list).

## Signals (computed by `round3_signals.py`, before labels exist)
The live system's settings: demo corpus, top-3 retrieval, relevance threshold 0.3.
- **NLI:** net score, most decisive of the top-3 passages (as the API).
- **Contradiction:** 1 − P(contradiction) on the top-1 passage (as Phase 3).
- **KG:** the fixed verifier — 1.0 supported, 0.0 contradicted, none if unknown.
- **Fused (the PRD's full CMHSA vs semantic+NLI):** mean of NLI and KG where KG exists, else
  NLI alone (the shipped weights: SemSim 0, NLI and KG 0.5 each, renormalised).

## Hypotheses and decision rules (95% CIs, 2,000 paired bootstrap resamples of claims)
- **H1 — KG ablation (PRD):** AUC(fused) − AUC(NLI-only). KG **helps** if the CI lower bound is
  above 0. Also reported against the PRD metric: Hallucinated-F1 at the shipped 0.35/0.65
  cut-offs, fused − NLI-only, with its CI, compared with the PRD target of +0.03.
- **H2 — KG correctness:** among claims where KG answers, the share where "supported" matches
  Verified and "contradicted" matches Hallucinated, with Wilson CIs; plus KG coverage (the share
  of claims with a KG answer).
- **H3 — contradiction signal (Phase 3 re-test):** AUC(1 − P(contra)) − AUC(net). Adopted only if
  the CI lower bound is above 0.
- **Agreement:** binary and 3-class Cohen's κ between the annotators, with bootstrap CIs.
- If fewer than 10 gold Hallucinated claims result, every AUC/F1 is reported but marked
  "too few positives to interpret", and no hypothesis is declared supported.
