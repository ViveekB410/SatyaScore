# Round 3 — KG relational pilot: results

Pre-registered in `round3/PREREGISTRATION.md` (committed before any answer or label). Signals from `round3/signals_round3.csv`, computed before the labels existed.

## Labels
> **Label provenance (Deviation 3):** both annotators used an AI assistant and then checked each verdict themselves. Labels are *AI-assisted, annotator-verified*, not independent human judgements; κ may be inflated by a shared tool. All results below are suggestive only.

- 45 claims labelled by both annotators. Gold (both agree, Verified or Hallucinated): **40** — Verified 25, **Hallucinated 15**. Excluded (disagreement or Uncertain): 5.
- Agreement: binary κ = 0.86 [0.67, 1.00]; 3-class κ = 0.82 [0.64, 0.96].

## KG coverage and correctness (H2)
- KG answered (supported or contradicted) for **29%** of all pilot claims; status counts: {'unlinked': 17, 'unknown': 15, 'supported': 8, 'contradicted': 5}.
- KG **supported** → gold Verified: 8/8 (100%, 95% CI [68%, 100%])
- KG **contradicted** → gold Hallucinated: 3/5 (60%, 95% CI [23%, 88%])

## Primary analysis — all claims (pre-registered)
n = 40 gold claims (Verified 25, Hallucinated 15).

| Score | AUC | Hallucinated-F1 @0.35/0.65 |
| --- | --- | --- |
| NLI only (semantic+NLI, SemSim weight 0) | 0.704 | 0.512 |
| KG only | 0.688 | 0.300 |
| **Fused NLI + KG (full CMHSA)** | 0.784 | 0.615 |
| 1 − P(contradiction) | 0.771 | 0.533 |

- **H1 (PRD KG ablation):** ΔAUC fused − NLI = +0.080 [+0.003, +0.189]; ΔHallucinated-F1 = +0.104 [+0.027, +0.199] (PRD target ≥ +0.03).
  → **KG helps on relational claims** (CI above 0).
- **H3 (contradiction re-test):** ΔAUC = +0.067 [-0.107, +0.235] → not adopted.

## Sensitivity — without the 3 coreference-garbled claims (Deviation 2)
n = 38 gold claims (Verified 25, Hallucinated 13).

| Score | AUC | Hallucinated-F1 @0.35/0.65 |
| --- | --- | --- |
| NLI only (semantic+NLI, SemSim weight 0) | 0.763 | 0.500 |
| KG only | 0.698 | 0.333 |
| **Fused NLI + KG (full CMHSA)** | 0.825 | 0.611 |
| 1 − P(contradiction) | 0.778 | 0.571 |

- **H1 (PRD KG ablation):** ΔAUC fused − NLI = +0.062 [-0.009, +0.161]; ΔHallucinated-F1 = +0.111 [+0.029, +0.217] (PRD target ≥ +0.03).
  → KG's gain is not established (CI includes 0).
- **H3 (contradiction re-test):** ΔAUC = +0.015 [-0.165, +0.195] → not adopted.

## Excluded claims (for adjudication)
| claim | A | B |
| --- | --- | --- |
| Subramania Bharati died in Madras present‑day Chennai India on 11 September 1921 at Chenna | Uncertain | Uncertain |
| The Deccan Education Society was founded in 1884 in Pune by a group of Indian reformers le | Verified | Uncertain |
| Tipu Sultan died in Srirangapatna also spelled Seringapatam in present-day Karnataka India | Hallucinated | Verified |
| While the company has significant global operations and a major European headquarters in I | Hallucinated | Verified |
| Specifically India is situated in the town of Konark within the Puri district on the east  | Hallucinated | Verified |
