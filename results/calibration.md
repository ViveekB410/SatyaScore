# Calibration — FR-04 confidence interval

Each HalluScore is reported with **P(Verified)** and a **95% Wilson interval**: the share of training claims in the same score bin (equal-count bins) that were Verified. Fitted on the train split only, checked on the grouped test split.

## EN — train n = 183, test n = 45
| score bin | train n | P(Verified) [95% CI] | test n | test Verified rate | inside CI? |
| --- | --- | --- | --- | --- | --- |
| [−∞, 0.485) | 37 | 0.59 [0.43, 0.74] | 11 | 0.64 | yes |
| [0.485, 0.500) | 36 | 0.61 [0.45, 0.75] | 7 | 1.00 | no |
| [0.500, 0.518) | 37 | 0.86 [0.72, 0.94] | 5 | 0.60 | no |
| [0.518, 0.722) | 36 | 0.67 [0.50, 0.80] | 14 | 0.79 | yes |
| [0.722, ∞) | 37 | 0.76 [0.60, 0.87] | 8 | 0.62 | yes |

- Test Brier score: **0.217** vs **0.197** for always predicting the train Verified rate (0.70). **The score adds no calibrated information over the base rate** — consistent with the near-chance AUC; the intervals say so honestly by overlapping.
- 3 of 5 test bin rates fall inside their train 95% CI.

## HI — train n = 151, test n = 39
| score bin | train n | P(Verified) [95% CI] | test n | test Verified rate | inside CI? |
| --- | --- | --- | --- | --- | --- |
| [−∞, 0.497) | 31 | 0.94 [0.79, 0.98] | 8 | 0.75 | no |
| [0.497, 0.500) | 31 | 0.84 [0.67, 0.93] | 4 | 0.75 | yes |
| [0.500, 0.502) | 28 | 0.75 [0.57, 0.87] | 10 | 1.00 | no |
| [0.502, 0.583) | 31 | 0.84 [0.67, 0.93] | 4 | 1.00 | no |
| [0.583, ∞) | 30 | 0.93 [0.79, 0.98] | 13 | 0.77 | no |

- Test Brier score: **0.152** vs **0.130** for always predicting the train Verified rate (0.86). **The score adds no calibrated information over the base rate** — consistent with the near-chance AUC; the intervals say so honestly by overlapping.
- 1 of 5 test bin rates fall inside their train 95% CI.

_Caveat: fitted on evaluation signals (NLI on the top-1 passage, experiment corpus); the live API uses the most decisive of the top-3 passages, so live scores are only approximately on this scale._
