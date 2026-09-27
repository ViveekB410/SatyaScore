# NLI model search

Scored as the live system does (demo corpus, top-3 passages, relevance ≥ 0.3). ROC-AUC with 95% bootstrap CI (0.5 = chance). **Selection rule (fixed before running): per language, highest TRAIN AUC wins; test and round 3 are reported only.**

## EN
| model | variant | train AUC | test AUC [95% CI] | round-3 AUC |
| --- | --- | --- | --- | --- |
| deberta_large_fever | net | 0.575 | 0.256 [0.118, 0.412] | 0.635 |
| deberta_large_fever | support | 0.589 | 0.267 [0.083, 0.473] | 0.627 |
| mdeberta_base_2mil7 | net | 0.586 | 0.523 [0.287, 0.737] | 0.621 |
| mdeberta_base_2mil7 **←** | support | 0.602 | 0.489 [0.259, 0.717] | 0.605 |
| mdeberta_base_xnli | net | 0.539 | 0.428 [0.150, 0.701] | 0.708 |
| mdeberta_base_xnli | support | 0.548 | 0.409 [0.142, 0.691] | 0.715 |
| xlmr_large_xnli | net | 0.480 | 0.398 [0.206, 0.601] | 0.552 |
| xlmr_large_xnli | support | 0.465 | 0.428 [0.256, 0.614] | 0.544 |

- Chosen for EN (train n = 166, Hallucinated 38): **mdeberta_base_2mil7 / support**.

## HI
| model | variant | train AUC | test AUC [95% CI] | round-3 AUC |
| --- | --- | --- | --- | --- |
| mdeberta_base_2mil7 | net | 0.609 | 0.939 [0.844, 1.000] | — |
| mdeberta_base_2mil7 | support | 0.601 | 0.909 [0.794, 1.000] | — |
| mdeberta_base_xnli | net | 0.507 | 0.803 [0.618, 0.941] | — |
| mdeberta_base_xnli | support | 0.546 | 0.758 [0.606, 0.902] | — |
| xlmr_large_xnli **←** | net | 0.685 | 0.576 [0.382, 0.758] | — |
| xlmr_large_xnli | support | 0.680 | 0.515 [0.294, 0.708] | — |

- Chosen for HI (train n = 137, Hallucinated 7): **xlmr_large_xnli / net**.


## Decision (recorded 2026-09-27, after review)
- **No model change.** The live system keeps `mdeberta_base_xnli` / net for both languages.
- **English:** the train-AUC pick (`mdeberta_base_2mil7` / support, 0.602 [0.498, 0.700]) does
  not beat the current model on train beyond noise (0.539 [0.430, 0.646]; intervals overlap,
  lower bound below 0.5), is no better on test (0.489 vs 0.428, both near chance, 8
  Hallucinated), and is worse on round 3 (0.605 vs 0.708). The FEVER-trained large model is
  below chance on test (0.256). A stronger NLI model does not help: NLI is not the bottleneck.
- **Hindi:** 7 Hallucinated claims in train and 2 in test, below the 10-positive floor used
  throughout; the Hindi rows are not interpretable and decide nothing.
- Reproduction check: the current model's round-3 AUC here (0.708) matches
  `analyze_round3.py` (0.704; 256- vs 192-token passage cap).
- Run on Colab T4 (`device: cuda`), fp32.
