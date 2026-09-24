# SatyaScore — Project Status

**As of:** 2026-09-24 · PRD status per requirement: see the traceability table in
`IMPROVEMENT_PLAN.md` (FR-01–FR-06 met, with recorded deviations; FR-07 dataset and the
accuracy goals not met).

Claim-level, bilingual (English + Hindi) LLM hallucination detector using the CMHSA
score (`HalluScore = α·SemSim + β·NLI + γ·KG`, per-language softmax weights; verdicts
Hallucinated / Uncertain / Verified). B.Tech capstone, 4 members.

---

## Headline

The **system is built and tested; the detection result is an honest negative one.** The
signals sit near chance and no configuration beats an always-"Verified" baseline. The cause
is **not proven**. The leading hypothesis is **label reliability**, supported by the IAA
findings. Retrieval was tested as a cause (Phase 2) and is **not** the main limiter at the
article level: the source article is in the top 3 for 87.5% of claims, yet English NLI stays
near chance even when it sees that article. How well NLI uses the evidence remains open. The
PRD pre-registered a negative result (§15) as acceptable.

---

## Status by workstream

| Workstream | Owner | Notes |
| --- | --- | --- |
| **Backend / model** | Vivek (M1+M3) | PRD FR-01–FR-05 met; 137 tests green |
| **Frontend** | teammate | React dashboard with FR-06 features (PRD specifies Streamlit) |
| **Paper / patent** | teammate | Owner to report status |
| **Dataset / annotation** | shared | FR-07 not met — see below |

---

## Backend — what's done

- CMHSA pipeline + `/detect` API; three verdict tiers; threshold override; ablation mode.
- **Whole-text verdict** (worst-claim rule) and per-claim scores in the API and UI.
- **FR-04 confidence interval:** each claim returns P(Verified) with a 95% Wilson interval,
  fitted on the train split (`results/calibration.md`).
- **FR-06 dashboard:** red/amber/green highlighting, HalluScore bar chart, CSV/JSON export,
  .txt/.pdf upload.
- **English claim extraction fixed:** broken claims 14.3% → 0% on the source answers
  (`results/extraction_quality.md`).
- **Leak-free evaluation:** train/test grouped by source question (0 shared, was 43 of 52);
  every metric carries its hallucinated count and a 95% CI.
- NLI batching and chunking (bounds GPU memory), stage timings, warm-up; Docker; Colab runbook.
- **Latency — met on median, on GPU:** median 104 ms/claim (target < 500 ms), 2,414 ms per
  10-claim document (target < 3 s). The mean (1,171 ms) misses the target, driven by the KG
  network call; NLI averages 80 ms.

**Remaining:** the PRD's *fine-tuned* DeBERTa on IndicXNLI was never trained (a pretrained
multilingual stand-in is used; needs a GPU and more labels). FR-02's MuRIL fallback is built
but **off by default**: measured, it retrieves far worse than XLM-R (`results/retrieval_comparison.md`).

---

## Key findings

- **Signals are near chance.** ROC-AUC ≈ 0.56–0.58 (EN), ≈ 0.42–0.51 (HI). No fusion
  configuration beats an always-"Verified" baseline; fusion collapses to NLI; KG is
  inapplicable (0% coverage on this data).
- **The test set is too small to measure detection:** 8 English and 2 Hindi hallucinated
  test claims. Hallucination-F1 is reported but marked "too few positives to interpret".
- **Retrieval is not the main limiter** (`results/retrieval_bottleneck.md`): English NLI AUC
  when it saw the source article is 0.568 [0.429, 0.699]; BM25, hybrid and MuRIL all
  retrieve worse than the current encoder.
- **C2-lite did not help:** sentence-level premises, English ΔAUC −0.012, 95% CI
  [−0.121, +0.094]. Kept behind an off-by-default switch.
- **Calibration:** the score adds no information over the base rate on the test split
  (Brier EN 0.217 vs 0.197), and the confidence intervals show it.

---

## Dataset / annotation

- 456 gold claims: **EN** 193 Verified / 47 Hallucinated / 26 Uncertain; **HI** 163 / 9 / 18.
  All answers come from one LLM (`llama-3.3-70b-versatile`).
- Protocol: every AI verdict was reviewed; 79% of labels are reviewed-and-agreed, reviewed
  with the AI verdict visible (**anchoring**).
- **IAA, round 1 (n = 56):** binary "hallucination vs not" **κ = 0.53** (the headline
  figure; 0.61 on the well-formed subset, n = 49). 3-class κ = 0.15: annotator B never used
  "Uncertain", so the annotators applied different label schemes.
- **Round 2 (n = 50, blind):** where the two annotators agree, the gold label is reproduced
  45/46 (98%). κ = 0.30 on a ~96%-Verified sample, where kappa is unstable.
- **Severe class imbalance — only 9 Hindi hallucinated claims.**

---

## Risks & blockers

1. **Detection accuracy is unproven either way on this data** — too few hallucinated test
   claims to measure it. More balanced annotation is the lever that makes it measurable.
2. **PRD novelty claim at risk:** the KG ablation (PRD: "crux of the novelty claim") cannot
   pass with 0% KG coverage. The paper must report it honestly or the team must add coverage.
3. **Paper/patent status is unknown to the backend lane** — needs an owner update.
4. **Nothing is deployed live** (frontend + API) — a demo needs a GPU host for PRD latency.

## Next steps (in order)

1. **Annotate more claims** toward FR-07: balanced, 2–3 annotators, especially Hindi hallucinations.
2. Fine-tune NLI (DeBERTa + IndicXNLI) once labels exist — the remaining accuracy lever.
3. Write the paper around the honest methodology and negative results.
4. GPU-host the API + frontend for a live demo.

---

_Numbers trace to: `gold_final.csv`, `RESULTS_SUMMARY.md`, `results/*.md`, `iaa/`,
`annotation_round2/`, `ANNOTATION_PROVENANCE.md`, and the 137-test suite._
