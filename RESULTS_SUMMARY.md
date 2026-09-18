# SatyaScore — Results Summary

_Auto-generated from the project artifacts by `generate_results_summary.py`. All numbers are computed, not hand-entered._

## 1. Dataset

- 456 human-verified claims (EN 266, HI 190), intact bilingual text.

- Verdict distribution (language x gold_verdict):

```
language  gold_verdict
en        Hallucinated     47
          Uncertain        26
          Verified        193
hi        Hallucinated      9
          Uncertain        18
          Verified        163
```
- Provenance: {'ai_agreed': 360, 'human_override': 93, 'human_confirmed': 3}. Convention: blank annotator field = agrees with AI; a written verdict = human override. Single annotator; no adjudication. (See ANNOTATION_PROVENANCE.md.)

## 2. Data quality (claim extraction)

- 44 claims flagged as broken extraction artifacts (all English; Hindi is sentence-level = clean).

- Well-formed working set = 412 claims. Counts {('en', 'broken'): 44, ('en', 'ok'): 222, ('hi', 'ok'): 190}.

- Finding: rule-based English decomposition degrades ~17% of English claims (fragments, glued headings, stripped symbols) — enough to corrupt some labels. Hindi (sentence-level) is clean.

## 3. Inter-annotator agreement (pilot, n≈56)

- n = 56 claims, two independent annotators (blind).
- 3-class Cohen's kappa = **0.15** (low — disagreement concentrated on the Verified/Uncertain boundary).
- Operational binary 'hallucination vs not' kappa = **0.53** (raw agreement 88%) — substantial.

## 4. Signal validity (recomputed bilingual signals)

- Mean signal by (language, verdict):

```
                       sem_sim  nli_prob
language gold_verdict                   
en       Hallucinated    0.629     0.531
         Uncertain       0.611     0.507
         Verified        0.650     0.562
hi       Hallucinated    0.717     0.536
         Uncertain       0.678     0.581
         Verified        0.686     0.564
```
- NLI points the right way (Verified > Hallucinated) in both languages but the separation is small (~0.03). SemSim tracks topicality, not truth (wrong direction for Hindi).

- Threshold-free discrimination (ROC-AUC: how well each signal ranks Verified above Hallucinated; 0.5 = chance):

| Lang | n (Verified / Hallucinated) | SemSim AUC | NLI AUC |
|---|---|---|---|
| EN | 157 / 45 | 0.580 | 0.558 |
| HI | 163 / 9 | 0.421 | 0.510 |

- Every AUC sits near 0.5 (EN ~0.56–0.58; HI noisier, n=9). SemSim is **below** chance in Hindi (anti-discriminative). Threshold-free, this corroborates the negative ablation: the signals barely separate real hallucinations from verified claims.

## 5. Ablation + baselines (clean test set, cut-points fitted on train)

| Lang | Always-Verified baseline (acc) | NLI-only acc / Hallu-F1 | SemSim-only acc / Hallu-F1 | Full CMHSA acc / Hallu-F1 |
|---|---|---|---|---|
| EN | 0.711 | 0.667 / 0.000 | 0.644 / 0.143 | 0.667 / 0.000 |
| HI | 0.868 | 0.789 / 0.000 | 0.868 / 0.000 | 0.789 / 0.000 |

- **No configuration beats the always-Verified baseline.** Full CMHSA collapses to NLI-only (KG has 0% coverage → not scoreable); adding SemSim to NLI *hurts*. Baselines: always-Verified (majority), SemSim-only (topical-similarity), NLI-only (TRUE-style entailment). SelfCheckGPT/FActScore/FactKG proper were not implemented (need multi-sample LLM output / KG-linkable claims the data lacks).

## 6. Defensible findings (the honest contribution)

1. Multi-signal fusion does **not** beat NLI alone for this task/data.
2. Knowledge-graph verification is **inapplicable** to descriptive claims (0/576 relation-phrase coverage).
3. Semantic similarity measures **topicality, not truth** (mildly anti-correlated in Hindi).
4. Detecting **naturally-occurring** hallucinations is hard; the model does not clear a trivial majority baseline.
5. Rule-based English claim decomposition degrades claim quality enough to corrupt labels — sentence-level (Hindi) is cleaner.

## 7. Limitations

- Dataset small (456) vs PRD's 3,000; single annotator; Verified-heavy; not the PRD's 40/30/30 balance.
- NLI is a pretrained mDeBERTa stand-in, not the PRD's own DeBERTa-v3+IndicXNLI fine-tune.
- KG signal non-functional on this claim type. API latency CPU-bound (~40s/call; GPU → <1s).
- Marathi out of scope; 5-baseline suite only partially implemented.

