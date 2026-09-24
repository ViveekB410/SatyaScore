# Is retrieval the bottleneck? (Phase 2 decision test)

NLI ROC-AUC (Verified vs Hallucinated; 0.5 = chance) on well-formed claims whose source article is in the experiment corpus. The stored NLI signal was computed on each claim's top-1 retrieved passage, so the split below is exactly "NLI saw a passage from the claim's own source article" vs "it did not".

## EN
| Group | n Verified / Hallucinated | NLI AUC | 95% CI |
| --- | --- | --- | --- |
| all | 151 / 33 | 0.540 | [0.427, 0.653] |
| top-1 passage FROM source article | 119 / 25 | 0.568 | [0.429, 0.699] |
| top-1 passage NOT from source article | 32 / 8 | 0.477 | [0.206, 0.749] |
| top-1 cosine >= 0.66 | 87 / 15 | 0.567 | [0.408, 0.723] |
| top-1 cosine < 0.66 | 64 / 18 | 0.496 | [0.317, 0.671] |

## HI
| Group | n Verified / Hallucinated | NLI AUC | 95% CI |
| --- | --- | --- | --- |
| all | 157 / 9 | 0.507 | [0.357, 0.659] |
| top-1 passage FROM source article | 119 / 6 | 0.521 | [0.304, 0.745] |
| top-1 passage NOT from source article | 38 / 3 | 0.447 | [0.237, 0.676] |
| top-1 cosine >= 0.66 | 106 / 6 | 0.561 | [0.400, 0.736] |
| top-1 cosine < 0.66 | 51 / 3 | 0.399 | [0.057, 0.769] |

## Decision (English; Hindi has too few Hallucinated claims to read)
- Even when NLI saw a passage from the claim's own source article, its AUC is 0.568 [0.429, 0.699] — **not distinguishable from chance**.
- Perfect retrieval would put every claim in that group: best-case AUC 0.568 vs 0.540 today (+0.028). **A better encoder cannot fix detection**; the limit is NLI's use of the evidence (and the labels), not retrieval. Phase 2.1 (E5/LaBSE) is not pursued.
- Relevance threshold: claims with top-1 cosine >= 0.66 score AUC 0.567 (CI low 0.408) — no demonstrated gain, while the cut drops 45% of claims. Keep `MIN_RELEVANCE_THRESHOLD = 0.3` (documented as effectively no filter).
- Caveat: "from the source article" is article-level, not the exact evidence passage.

