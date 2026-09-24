### EN (alpha=0.495, beta=0.194, gamma=0.310)

| Configuration | Cut-points | Acc (all) | Macro-F1 (all) | Hallu-F1 (all) | Acc (human) | Hallu-F1 (human) |
| --- | --- | --- | --- | --- | --- | --- |
| Full (S+N+KG) | 0.49/0.53 | 0.600 | 0.261 | 0.000 | 0.600 | 0.000 |
| SemSim only | 0.54/0.55 | 0.644 | 0.307 | 0.143 | 0.644 | 0.143 |
| NLI only | 0.23/0.43 | 0.667 | 0.356 | 0.000 | 0.667 | 0.000 |
| SemSim + NLI | 0.49/0.53 | 0.600 | 0.261 | 0.000 | 0.600 | 0.000 |
| NLI + KG | 0.23/0.43 | 0.667 | 0.356 | 0.000 | 0.667 | 0.000 |
| SemSim + KG | 0.54/0.55 | 0.644 | 0.307 | 0.143 | 0.644 | 0.143 |
| KG only | n/a | not scoreable | | | | |
| Always-Verified baseline | n/a | 0.711 | 0.277 | 0.000 | n/a | n/a |

Identical predictions on the test split: Full (S+N+KG), SemSim + NLI.

Identical predictions on the test split: SemSim only, SemSim + KG.

Identical predictions on the test split: NLI only, NLI + KG.

### HI (alpha=0.199, beta=0.489, gamma=0.312)

| Configuration | Cut-points | Acc (all) | Macro-F1 (all) | Hallu-F1 (all) | Acc (human) | Hallu-F1 (human) |
| --- | --- | --- | --- | --- | --- | --- |
| Full (S+N+KG) | 0.32/0.36 | 0.789 | 0.294 | 0.000 | 0.789 | 0.000 |
| SemSim only | 0.51/0.53 | 0.868 | 0.314 | 0.000 | 0.868 | 0.000 |
| NLI only | 0.18/0.22 | 0.789 | 0.294 | 0.000 | 0.789 | 0.000 |
| SemSim + NLI | 0.32/0.36 | 0.789 | 0.294 | 0.000 | 0.789 | 0.000 |
| NLI + KG | 0.18/0.22 | 0.789 | 0.294 | 0.000 | 0.789 | 0.000 |
| SemSim + KG | 0.51/0.53 | 0.868 | 0.314 | 0.000 | 0.868 | 0.000 |
| KG only | n/a | not scoreable | | | | |
| Always-Verified baseline | n/a | 0.868 | 0.310 | 0.000 | n/a | n/a |

Identical predictions on the test split: Full (S+N+KG), NLI only, SemSim + NLI, NLI + KG.

Identical predictions on the test split: SemSim only, SemSim + KG.

Cut-points are fitted on the training split separately for each configuration, because dropping a signal changes the scale of the fused score. The human columns cover the test claims that were annotated by hand, excluding synthetic perturbations.
