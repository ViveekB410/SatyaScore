# Round-2 label audit

Human–human agreement and an anchoring check on 50 claims labelled by both annotators (of 50 issued). The private key (gold + AI verdicts) is git-ignored and not reproduced here.

## 1. Human–human agreement
| Scheme | kappa | 95% CI (bootstrap) | valid resamples | raw agreement |
| --- | --- | --- | --- | --- |
| 3-class (V/U/H) | 0.296 | [-0.061, 0.790] | 1991/2000 | 92% |
| Binary (Hallucinated vs not) | 0.296 | [-0.061, 0.790] | 1991/2000 | 92% |

- **Binary kappa 0.296 is BELOW the guideline target of 0.65.** Raw agreement is high (92%) but the labels are heavily skewed to Verified, so chance agreement is high and kappa stays low — read the two together, and note the wide CI on this n.
- Claims **both** annotators called Hallucinated: **1**.
- Confusion matrix (rows = A, cols = B; order Verified / Uncertain / Hallucinated):
```
[[45  0  1]
 [ 0  0  0]
 [ 3  0  1]]
```

## 2. Label-scheme check
| Label | A used | B used |
| --- | --- | --- |
| Verified | 46 | 48 |
| Uncertain | 0 | 0 |
| Hallucinated | 4 | 2 |

> **FLAG: annotator A never used "Uncertain".**
> **FLAG: annotator B never used "Uncertain".**
> Context: this round-2 set is drawn from `ai_agreed` claims — ones clear enough that the reviewer and the AI already agreed — which are mostly unambiguous. So an unused "Uncertain" here most likely means no genuinely ambiguous claims appeared in this sample, not that the annotators used the wrong scheme. It does mean the Verified/Uncertain boundary was never exercised, so the 3-class and binary kappa coincide and this sample cannot measure 3-class agreement — it measures the binary hallucinated-vs-not call.

## 3. Anchoring check (where the two humans agree)
How often the existing gold label — and the AI verdict — matches the humans' agreed label. A gold match rate well below 1.0 is evidence of anchoring in round 1 (labels reviewed with the AI verdict visible).

| Split | vs | match | n | rate | 95% CI (Wilson) |
| --- | --- | --- | --- | --- | --- |
| overall | gold | 45 | 46 | 98% | [89%, 100%] |
| overall | ai | 45 | 46 | 98% | [89%, 100%] |
| en | gold | 26 | 27 | 96% | [82%, 99%] |
| en | ai | 26 | 27 | 96% | [82%, 99%] |
| hi | gold | 19 | 19 | 100% | [83%, 100%] |
| hi | ai | 19 | 19 | 100% | [83%, 100%] |

_n = 50 both-labelled claims; agreement subset = 46. Small n — read the CIs, not the point rates. Hindi round-2 was drawn from `ai_agreed` claims that are almost all Verified, so Hindi mainly tests anchoring, not disagreement._

