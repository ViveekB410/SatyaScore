# Retrieval diagnostic

112 claims diagnosed against the experiment corpus (2674 passages). Per-claim rows in `results/retrieval_diagnostic.csv`.

## By language and label
| Group | n | src in top-3 | src in top-10 | mean top-1 sim | pairs neutral |
| --- | --- | --- | --- | --- | --- |
| en Hallucinated | 47 | 0.60 | 0.64 | 0.629 | 0.66 |
| en Verified | 47 | 0.81 | 0.87 | 0.638 | 0.67 |
| hi Hallucinated | 9 | 0.89 | 1.00 | 0.717 | 0.81 |
| hi Verified | 9 | 0.89 | 1.00 | 0.649 | 0.63 |

## Conclusion (decision rule: top-3 recall <0.5 ⇒ C1; else neutral >0.6 ⇒ C2; else C3)
**EVIDENCE-GRANULARITY problem → Task C2.** The source article is usually found (top-3 73%), but 67% of claim–passage NLI pairs land in neutral — long passages dilute the signal. Try sentence-level premises + a contradiction signal.

