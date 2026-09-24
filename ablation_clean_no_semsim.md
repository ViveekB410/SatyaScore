### EN (alpha=0.000, beta=0.500, gamma=0.500)

Test split: **n = 45**, of which **Hallucinated = 8** — too few positives to interpret Hallu-F1.

| Configuration | Cut-points | Acc [95% CI] | Macro-F1 | Hallu-F1 [95% CI] |
| --- | --- | --- | --- | --- |
| Full (S+N+KG) | 0.23/0.43 | 0.689 [0.56, 0.82] | 0.435 | 0.167 [0.00, 0.46] † |
| SemSim only | 0.54/0.55 | 0.711 [0.58, 0.84] | 0.336 | 0.182 [0.00, 0.50] † |
| NLI only | 0.23/0.43 | 0.689 [0.56, 0.82] | 0.435 | 0.167 [0.00, 0.46] † |
| SemSim + NLI | 0.23/0.43 | 0.689 [0.56, 0.82] | 0.435 | 0.167 [0.00, 0.46] † |
| NLI + KG | 0.23/0.43 | 0.689 [0.56, 0.82] | 0.435 | 0.167 [0.00, 0.46] † |
| SemSim + KG | 0.54/0.55 | 0.711 [0.58, 0.84] | 0.336 | 0.182 [0.00, 0.50] † |
| KG only | n/a | not scoreable | | |
| Always-Verified baseline | n/a | 0.733 [0.60, 0.87] | 0.282 | 0.000 [0.00, 0.00] † |

Identical predictions on the test split: Full (S+N+KG), NLI only, SemSim + NLI, NLI + KG.

Identical predictions on the test split: SemSim only, SemSim + KG.

### HI (alpha=0.000, beta=0.498, gamma=0.502)

Test split: **n = 39**, of which **Hallucinated = 2** — too few positives to interpret Hallu-F1.

| Configuration | Cut-points | Acc [95% CI] | Macro-F1 | Hallu-F1 [95% CI] |
| --- | --- | --- | --- | --- |
| Full (S+N+KG) | 0.00/0.00 | 0.846 [0.72, 0.95] | 0.306 | 0.000 [0.00, 0.00] † |
| SemSim only | 0.49/0.53 | 0.821 [0.69, 0.92] | 0.300 | 0.000 [0.00, 0.00] † |
| NLI only | 0.00/0.00 | 0.846 [0.72, 0.95] | 0.306 | 0.000 [0.00, 0.00] † |
| SemSim + NLI | 0.00/0.00 | 0.846 [0.72, 0.95] | 0.306 | 0.000 [0.00, 0.00] † |
| NLI + KG | 0.00/0.00 | 0.846 [0.72, 0.95] | 0.306 | 0.000 [0.00, 0.00] † |
| SemSim + KG | 0.49/0.53 | 0.821 [0.69, 0.92] | 0.300 | 0.000 [0.00, 0.00] † |
| KG only | n/a | not scoreable | | |
| Always-Verified baseline | n/a | 0.846 [0.72, 0.95] | 0.306 | 0.000 [0.00, 0.00] † |

Identical predictions on the test split: Full (S+N+KG), NLI only, SemSim + NLI, NLI + KG.

Identical predictions on the test split: SemSim only, SemSim + KG.

Cut-points are fitted on the training split separately for each configuration, because dropping a signal changes the scale of the fused score. CIs are 95% bootstrap intervals (2,000 resamples of test claims).
† Fewer than 10 Hallucinated test claims: the Hallu-F1 is printed but is too few positives to interpret.
Every test claim is human-annotated (no synthetic perturbations), so a separate human-only column would repeat these numbers and is omitted; it remains in the JSON.
