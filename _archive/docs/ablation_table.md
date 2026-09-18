### EN (alpha=0.000, beta=0.500, gamma=0.500)

| Configuration | Cut-points | Acc (all) | Macro-F1 (all) | Hallu-F1 (all) | Acc (human) | Hallu-F1 (human) |
| --- | --- | --- | --- | --- | --- | --- |
| Full (S+N+KG) | 0.18/0.23 | 0.653 | 0.440 | 0.560 | 0.623 | 0.000 |
| SemSim only | 0.45/0.49 | 0.417 | 0.300 | 0.195 | 0.528 | 0.200 |
| NLI only | 0.18/0.23 | 0.653 | 0.440 | 0.560 | 0.623 | 0.000 |
| SemSim + NLI | 0.18/0.23 | 0.653 | 0.440 | 0.560 | 0.623 | 0.000 |
| NLI + KG | 0.18/0.23 | 0.653 | 0.440 | 0.560 | 0.623 | 0.000 |
| SemSim + KG | 0.45/0.49 | 0.417 | 0.300 | 0.195 | 0.528 | 0.200 |
| KG only | n/a | not scoreable | | | | |
| Always-Verified baseline | n/a | 0.542 | 0.234 | 0.000 | n/a | n/a |

Identical predictions on the test split: Full (S+N+KG), NLI only, SemSim + NLI, NLI + KG.

Identical predictions on the test split: SemSim only, SemSim + KG.

### HI (alpha=0.000, beta=0.502, gamma=0.498)

| Configuration | Cut-points | Acc (all) | Macro-F1 (all) | Hallu-F1 (all) | Acc (human) | Hallu-F1 (human) |
| --- | --- | --- | --- | --- | --- | --- |
| Full (S+N+KG) | 0.01/0.21 | 0.769 | 0.440 | 0.000 | 0.769 | 0.000 |
| SemSim only | 0.39/0.45 | 0.718 | 0.360 | 0.000 | 0.718 | 0.000 |
| NLI only | 0.01/0.21 | 0.769 | 0.440 | 0.000 | 0.769 | 0.000 |
| SemSim + NLI | 0.01/0.21 | 0.769 | 0.440 | 0.000 | 0.769 | 0.000 |
| NLI + KG | 0.01/0.21 | 0.769 | 0.440 | 0.000 | 0.769 | 0.000 |
| SemSim + KG | 0.39/0.45 | 0.718 | 0.360 | 0.000 | 0.718 | 0.000 |
| KG only | n/a | not scoreable | | | | |
| Always-Verified baseline | n/a | 0.750 | 0.286 | 0.000 | n/a | n/a |

Identical predictions on the test split: Full (S+N+KG), NLI only, SemSim + NLI, NLI + KG.

Identical predictions on the test split: SemSim only, SemSim + KG.

Cut-points are fitted on the training split separately for each configuration, because dropping a signal changes the scale of the fused score. The human columns cover the test claims that were annotated by hand, excluding synthetic perturbations.
