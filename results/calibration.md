# Calibration — FR-04 confidence interval (live scores)

Scores from the live pipeline: aggregation=gated, expansion=on, top-10 passages, strict titles=True, index 102,743 passages (retrieval, NLI, evidence rule exactly as the API). Each HalluScore is reported with **P(Verified)** and a **95% Wilson interval**: the share of TRAIN claims in the same score bin (equal-count bins) that were Verified; checked on the grouped test split.

## EN — train n = 166, test n = 41
| score bin | train n | P(Verified) [95% CI] | test n | test Verified rate | inside CI? |
| --- | --- | --- | --- | --- | --- |
| [−∞, 0.512) | 33 | 0.64 [0.47, 0.78] | 6 | 1.00 | no |
| [0.512, 0.677) | 33 | 0.88 [0.73, 0.95] | 8 | 0.88 | yes |
| [0.677, 0.876) | 34 | 0.68 [0.51, 0.81] | 6 | 0.83 | no |
| [0.876, 0.981) | 32 | 0.84 [0.68, 0.93] | 12 | 0.67 | no |
| [0.981, ∞) | 34 | 0.82 [0.66, 0.92] | 9 | 0.78 | yes |

- Test Brier score **0.177** vs **0.158** for always predicting the train Verified rate (0.77): **the score adds no calibrated information over the base rate**; the overlapping intervals say so honestly.
- 2 of 5 test bin rates fall inside their train 95% CI.

## HI — train n = 137, test n = 35
| score bin | train n | P(Verified) [95% CI] | test n | test Verified rate | inside CI? |
| --- | --- | --- | --- | --- | --- |
| [−∞, 0.537) | 28 | 0.93 [0.77, 0.98] | 6 | 1.00 | no |
| [0.537, 0.739) | 27 | 1.00 [0.88, 1.00] | 8 | 1.00 | yes |
| [0.739, 0.979) | 28 | 0.93 [0.77, 0.98] | 12 | 0.83 | yes |
| [0.979, 0.998) | 26 | 0.96 [0.81, 0.99] | 2 | 1.00 | no |
| [0.998, ∞) | 28 | 0.93 [0.77, 0.98] | 7 | 1.00 | no |

- Test Brier score **0.053** vs **0.054** for always predicting the train Verified rate (0.95): the score adds calibrated information.
- 2 of 5 test bin rates fall inside their train 95% CI.

