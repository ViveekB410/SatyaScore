# Retrieval comparison — source-article recall (Phase 2)

417 gold claims whose source article is in the experiment corpus (236 EN, 181 HI), 9351 passages. Recall@k = share of claims with a passage from their own source article in the top k. Baseline = `dense:xlmr` (the current retrieval).

**Decision rule (fixed before running):** a method replaces the baseline only if its recall@3 gain has a paired-bootstrap 95% CI entirely above 0.

| Method | R@1 all | R@3 all | R@10 all | R@3 EN | R@3 HI | ΔR@3 vs baseline [95% CI] | adopt? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `dense:xlmr` | 0.602 | 0.775 | 0.906 | 0.784 | 0.762 | — | baseline |
| `bm25` | 0.520 | 0.676 | 0.808 | 0.754 | 0.575 | -0.098 [-0.144, -0.055] | no |
| `hybrid:xlmr` | 0.561 | 0.753 | 0.863 | 0.822 | 0.663 | -0.022 [-0.060, +0.017] | no |

## By language and label (R@3)
| Method | EN Verified | EN Hallucinated | HI Verified | HI Hallucinated |
| --- | --- | --- | --- | --- |
| `dense:xlmr` | 0.79 (n=181) | 0.79 (n=34) | 0.77 (n=157) | 0.67 (n=9) |
| `bm25` | 0.77 (n=181) | 0.74 (n=34) | 0.59 (n=157) | 0.67 (n=9) |
| `hybrid:xlmr` | 0.82 (n=181) | 0.88 (n=34) | 0.67 (n=157) | 0.67 (n=9) |

## Relevance threshold (Phase 2.2)
`MIN_RELEVANCE_THRESHOLD` decides when retrieved evidence counts as "no relevant evidence found". For each claim: the best cosine of any passage from its **source article** (relevant) vs the best cosine of any passage from **another article** (irrelevant). The cut-off is fitted on the TRAIN split's claims by Youden's J and reported on TEST. Proxy caveat: another article can still be relevant, so the "irrelevant" rate is an upper bound on true false positives.

### dense:xlmr — fitted cut-off **0.69** (current 0.3)
| cut-off | relevant kept (train) | irrelevant kept (train) | relevant kept (test) | irrelevant kept (test) |
| --- | --- | --- | --- | --- |
| 0.30 | 0.98 | 1.00 | 0.99 | 1.00 |
| 0.69 | 0.42 | 0.28 | 0.38 | 0.22 |

- Median best cosine: relevant 0.665, irrelevant 0.634 (train+test).

## Conclusion and caveats
- **No method beats the baseline** under the decision rule; `dense:xlmr` stays.
- The baseline already finds the source article in the top 3 for 77.5% of claims and the top 10 for 90.6%. Article-level retrieval leaves little headroom; the weak detector results are not mainly a retrieval failure at this level.
- This is **article-level** recall: a passage from the right article is not necessarily the passage stating the fact, so it is an upper bound on evidence recall. Measuring the exact evidence passage would need passage-level relevance labels (human annotation).
- Claims whose source article is missing from the corpus are excluded (27 of 444 claims with a recorded source) — a coverage gap, not a ranking one (Phase 4).
- Any variant chosen after seeing these numbers (e.g. hybrid for English only) would be fitted to this evaluation and is not adopted here.

