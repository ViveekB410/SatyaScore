# Regrouped split — old vs new ablation

**Old:** plain stratified `train_test_split` (claims from the same LLM answer on both sides). **New:** `StratifiedGroupKFold` grouped by `source_query_id`, fold 0 as test (chosen before running; no other fold tried). Cut-points refit on each train split. The new well-formed set is 418 claims (was 412) after task 1.1's corrected quality rules.

## The splits
| | old | new |
| --- | --- | --- |
| train / test claims | 329 / 83 | 334 / 84 |
| test source questions also in train | **43 of 52** | **0 of 21** |
| EN Hallucinated train / test | 36 / 9 | 38 / 8 |
| HI Hallucinated train / test | 7 / 2 | 7 / 2 |

## Ablation — `no_semsim` (test accuracy / Hallu-F1)

### EN — test Hallucinated: old 9, new 8
| Configuration | Acc old | Acc new | Hallu-F1 old | Hallu-F1 new |
| --- | --- | --- | --- | --- |
| Full (S+N+KG) | 0.667 | 0.689 | 0.000 | 0.167 |
| SemSim only | 0.644 | 0.711 | 0.143 | 0.182 |
| NLI only | 0.667 | 0.689 | 0.000 | 0.167 |
| SemSim + NLI | 0.667 | 0.689 | 0.000 | 0.167 |
| Always-Verified baseline | 0.711 | 0.733 | 0.000 | 0.000 |

### HI — test Hallucinated: old 2, new 2
| Configuration | Acc old | Acc new | Hallu-F1 old | Hallu-F1 new |
| --- | --- | --- | --- | --- |
| Full (S+N+KG) | 0.789 | 0.846 | 0.000 | 0.000 |
| SemSim only | 0.868 | 0.821 | 0.000 | 0.000 |
| NLI only | 0.789 | 0.846 | 0.000 | 0.000 |
| SemSim + NLI | 0.789 | 0.846 | 0.000 | 0.000 |
| Always-Verified baseline | 0.868 | 0.846 | 0.000 | 0.000 |

## Ablation — `with_semsim` (test accuracy / Hallu-F1)

### EN — test Hallucinated: old 9, new 8
| Configuration | Acc old | Acc new | Hallu-F1 old | Hallu-F1 new |
| --- | --- | --- | --- | --- |
| Full (S+N+KG) | 0.600 | 0.578 | 0.000 | 0.273 |
| SemSim only | 0.644 | 0.711 | 0.143 | 0.182 |
| NLI only | 0.667 | 0.689 | 0.000 | 0.167 |
| SemSim + NLI | 0.600 | 0.578 | 0.000 | 0.273 |
| Always-Verified baseline | 0.711 | 0.733 | 0.000 | 0.000 |

### HI — test Hallucinated: old 2, new 2
| Configuration | Acc old | Acc new | Hallu-F1 old | Hallu-F1 new |
| --- | --- | --- | --- | --- |
| Full (S+N+KG) | 0.789 | 0.692 | 0.000 | 0.000 |
| SemSim only | 0.868 | 0.821 | 0.000 | 0.000 |
| NLI only | 0.789 | 0.846 | 0.000 | 0.000 |
| SemSim + NLI | 0.789 | 0.692 | 0.000 | 0.000 |
| Always-Verified baseline | 0.868 | 0.846 | 0.000 | 0.000 |

## Reading it
- The leak is gone: the new test split shares no source question with training.
- Both splits have fewer than 10 Hallucinated test claims per language, so every Hallu-F1 above is too few positives to interpret (the new ablation tables print 95% CIs; English Hallu-F1 spans roughly 0.00-0.46).
- The qualitative result is unchanged: no configuration beats the always-Verified baseline on accuracy, and the NLI-based configurations remain identical to each other (KG never fires; SemSim does not vote).
- Numbers moved in both directions between splits; per the ground rules they are reported as they came out, with no other fold or seed tried.

