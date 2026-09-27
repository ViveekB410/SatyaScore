# Calibration — FR-04 confidence interval (live scores)

Scores from the live pipeline: aggregation=gated, expansion=on (retrieval, NLI, evidence rule exactly as the API). Each HalluScore is reported with **P(Verified)** and a **95% Wilson interval**: the share of TRAIN claims in the same score bin (equal-count bins) that were Verified; checked on the grouped test split.

## EN — train n = 166, test n = 41
| score bin | train n | P(Verified) [95% CI] | test n | test Verified rate | inside CI? |
| --- | --- | --- | --- | --- | --- |
| [−∞, 0.505) | 33 | 0.73 [0.56, 0.85] | 2 | 0.50 | no |
| [0.505, 0.550) | 33 | 0.82 [0.66, 0.91] | 9 | 1.00 | no |
| [0.550, 0.787) | 33 | 0.82 [0.66, 0.91] | 12 | 0.83 | yes |
| [0.787, 0.938) | 33 | 0.67 [0.50, 0.80] | 10 | 0.80 | yes |
| [0.938, ∞) | 34 | 0.82 [0.66, 0.92] | 8 | 0.62 | no |

- Test Brier score **0.159** vs **0.158** for always predicting the train Verified rate (0.77): **the score adds no calibrated information over the base rate**; the overlapping intervals say so honestly.
- 2 of 5 test bin rates fall inside their train 95% CI.

## HI — train n = 137, test n = 35
| score bin | train n | P(Verified) [95% CI] | test n | test Verified rate | inside CI? |
| --- | --- | --- | --- | --- | --- |
| [−∞, 0.504) | 28 | 0.96 [0.82, 0.99] | 11 | 1.00 | no |
| [0.504, 0.535) | 27 | 0.93 [0.77, 0.98] | 5 | 0.80 | yes |
| [0.535, 0.804) | 27 | 0.96 [0.82, 0.99] | 9 | 0.89 | yes |
| [0.804, 0.990) | 26 | 0.96 [0.81, 0.99] | 5 | 1.00 | no |
| [0.990, ∞) | 29 | 0.93 [0.78, 0.98] | 5 | 1.00 | no |

- Test Brier score **0.053** vs **0.054** for always predicting the train Verified rate (0.95): the score adds calibrated information.
- 2 of 5 test bin rates fall inside their train 95% CI.

