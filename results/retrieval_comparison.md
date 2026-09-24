# Retrieval comparison — source-article recall (Phase 2)

417 gold claims whose source article is in the experiment corpus (236 EN, 181 HI), 2674 passages. Recall@k = share of claims with a passage from their own source article in the top k. Baseline = `dense:xlmr` (the current retrieval).

**Decision rule (fixed before running):** a method replaces the baseline only if its recall@3 gain has a paired-bootstrap 95% CI entirely above 0.

| Method | R@1 all | R@3 all | R@10 all | R@3 EN | R@3 HI | ΔR@3 vs baseline [95% CI] | adopt? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `dense:xlmr` | 0.767 | 0.875 | 0.950 | 0.877 | 0.873 | — | baseline |
| `dense:muril` | 0.552 | 0.681 | 0.851 | 0.763 | 0.575 | -0.194 [-0.240, -0.146] | no |
| `bm25` | 0.647 | 0.775 | 0.866 | 0.856 | 0.669 | -0.101 [-0.144, -0.060] | no |
| `hybrid:xlmr` | 0.729 | 0.842 | 0.923 | 0.886 | 0.785 | -0.034 [-0.065, -0.002] | no |
| `hybrid:muril` | 0.631 | 0.775 | 0.878 | 0.860 | 0.663 | -0.101 [-0.141, -0.062] | no |

## By language and label (R@3)
| Method | EN Verified | EN Hallucinated | HI Verified | HI Hallucinated |
| --- | --- | --- | --- | --- |
| `dense:xlmr` | 0.89 (n=181) | 0.82 (n=34) | 0.89 (n=157) | 0.89 (n=9) |
| `dense:muril` | 0.79 (n=181) | 0.68 (n=34) | 0.61 (n=157) | 0.33 (n=9) |
| `bm25` | 0.87 (n=181) | 0.85 (n=34) | 0.69 (n=157) | 0.67 (n=9) |
| `hybrid:xlmr` | 0.89 (n=181) | 0.88 (n=34) | 0.80 (n=157) | 0.78 (n=9) |
| `hybrid:muril` | 0.86 (n=181) | 0.85 (n=34) | 0.68 (n=157) | 0.67 (n=9) |

## Relevance threshold (Phase 2.2)
`MIN_RELEVANCE_THRESHOLD` decides when retrieved evidence counts as "no relevant evidence found". For each claim: the best cosine of any passage from its **source article** (relevant) vs the best cosine of any passage from **another article** (irrelevant). The cut-off is fitted on the TRAIN split's claims by Youden's J and reported on TEST. Proxy caveat: another article can still be relevant, so the "irrelevant" rate is an upper bound on true false positives.

### dense:xlmr — fitted cut-off **0.66** (current 0.3)
| cut-off | relevant kept (train) | irrelevant kept (train) | relevant kept (test) | irrelevant kept (test) |
| --- | --- | --- | --- | --- |
| 0.30 | 0.98 | 1.00 | 0.99 | 1.00 |
| 0.66 | 0.52 | 0.22 | 0.54 | 0.22 |

- Median best cosine: relevant 0.665, irrelevant 0.581 (train+test).

### dense:muril — fitted cut-off **0.05** (current 0.3)
| cut-off | relevant kept (train) | irrelevant kept (train) | relevant kept (test) | irrelevant kept (test) |
| --- | --- | --- | --- | --- |
| 0.30 | 1.00 | 1.00 | 1.00 | 1.00 |
| 0.05 | 1.00 | 1.00 | 1.00 | 1.00 |

- Median best cosine: relevant 0.996, irrelevant 0.996 (train+test).

## Conclusion and caveats
- **No method beats the baseline** under the decision rule; `dense:xlmr` stays.
- The baseline already finds the source article in the top 3 for 87.5% of claims and the top 10 for 95.0%. Article-level retrieval leaves little headroom; the weak detector results are not mainly a retrieval failure at this level.
- This is **article-level** recall: a passage from the right article is not necessarily the passage stating the fact, so it is an upper bound on evidence recall. Measuring the exact evidence passage would need passage-level relevance labels (human annotation).
- Claims whose source article is missing from the corpus are excluded (27 of 444 claims with a recorded source) — a coverage gap, not a ranking one (Phase 4).
- Any variant chosen after seeing these numbers (e.g. hybrid for English only) would be fitted to this evaluation and is not adopted here.

