# More sources — effect on the evidence NLI sees (Phase 4)

NLI AUC (Verified vs Hallucinated; 0.5 = chance) when NLI reads the top-1 passage from the **experiment** corpus (stored signal) vs the **demo** corpus (experiment + extra topics). Well-formed claims.

**Decision rule (fixed before running):** the expansion is harmful if the English paired ΔAUC (demo − experiment) has a 95% CI entirely below 0.

| Lang | n V / H | top-1 from a new topic | AUC experiment | AUC demo | ΔAUC [95% CI] |
| --- | --- | --- | --- | --- | --- |
| EN | 161 / 46 | 26% | 0.552 | 0.526 | -0.026 [-0.087, +0.036] |
| HI | 163 / 9 | 29% | 0.510 | 0.597 | +0.087 [-0.042, +0.233] |

## Decision
- **No demonstrated harm** to NLI's discrimination (English ΔAUC -0.026, CI [-0.087, +0.036] includes 0), even though article-level recall drops. Either the new articles often hold equally usable evidence, or NLI is too weak for the difference to show. More sources for the demo are acceptable on this evidence; retrieval must still be re-measured after any expansion.
- Hindi has 9 Hallucinated claims; its row is noise.

