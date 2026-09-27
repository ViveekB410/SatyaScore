# Wikipedia index expansion (FR-03 incremental indexing)

Demo corpus 9,351 passages → **33,757** after expansion (+795 Wikipedia articles, +24,406 passages; 0 failed lookups). Same embedder, index type, top-3 and relevance cut (0.3) in both conditions; NLI = current model (net). **Decision rule (fixed before running):** switch expansion on only if the pooled EN+HI TRAIN ΔAUC (expanded − baseline) has a 95% CI entirely above 0.

## train (n = 303, Hallucinated 45)

- Evidence: claims with a relevant passage 100% → 100%; mean top-1 similarity 0.681 → 0.711; claims whose top-3 includes a new article 90%.
- NLI AUC 0.552 → 0.532 (Δ -0.020 [-0.072, +0.031]).
- Verdicts, baseline: 104/303 (34%) · Uncertain 137 · when it commits 104/166 (63%)
- Verdicts, expanded: 119/303 (39%) · Uncertain 125 · when it commits 119/178 (67%)

## test (n = 76, Hallucinated 10)

- Evidence: claims with a relevant passage 100% → 100%; mean top-1 similarity 0.688 → 0.715; claims whose top-3 includes a new article 91%.
- NLI AUC 0.503 → 0.428 (Δ -0.075 [-0.320, +0.154]).
- Verdicts, baseline: 28/76 (37%) · Uncertain 30 · when it commits 28/46 (61%)
- Verdicts, expanded: 28/76 (37%) · Uncertain 29 · when it commits 28/47 (60%)

## round3 (n = 40, Hallucinated 15)

- Evidence: claims with a relevant passage 100% → 100%; mean top-1 similarity 0.488 → 0.622; claims whose top-3 includes a new article 98%.
- NLI AUC 0.693 → 0.605 (Δ -0.088 [-0.342, +0.161]).
- Verdicts, baseline: 14/40 (35%) · Uncertain 10 · when it commits 14/30 (47%)
- Verdicts, expanded: 19/40 (48%) · Uncertain 6 · when it commits 19/34 (56%)
- Live rule (KG decides, else NLI), baseline: 24/40 (60%) · Uncertain 7 · when it commits 24/33 (73%)
- Live rule (KG decides, else NLI), expanded: 27/40 (68%) · Uncertain 3 · when it commits 27/37 (73%)

## Decision
- **Not switched on by default**: pooled train ΔAUC -0.020 [-0.072, +0.031] does not have a CI above 0. Expansion stays available (off by default).
