# Contradiction as a hallucination signal (Phase 3.3)

NLI components recomputed exactly as `recompute_signals.py` did (top-1 XLM-R passage, experiment corpus, 192-token cap). **Reproduction check** — recomputed net vs stored `nli_prob`: max |diff| = **0.0004**, median 0.0001 (fp16 noise is ~1e-3).

**Decision rule (fixed before running):** adopt contradiction as a separate signal only if its English AUC beats the net score with a paired-bootstrap 95% CI entirely above 0.

AUC = how well the score ranks Verified above Hallucinated (0.5 = chance); for contradiction the score is 1 − P(contradiction). Well-formed claims.

| Lang | n V / H | net (current) | 1 − P(contra) | P(entail) | ΔAUC contra − net [95% CI] |
| --- | --- | --- | --- | --- | --- |
| EN | 161 / 46 | 0.552 | 0.629 | 0.492 | +0.078 [-0.013, +0.173] |
| HI | 163 / 9 | 0.510 | 0.584 | 0.526 | +0.074 [-0.067, +0.243] |

## Decision
- **Not adopted, but suggestive.** English ΔAUC is +0.078, and its CI crosses 0 (lower bound -0.013), so the gain is not established at this sample size. Entailment alone is at chance (AUC 0.492), which fits the net score diluting the contradiction probability with entailment noise. Re-test with the same fixed rule once more Hallucinated claims are annotated.
- Hindi has 9 Hallucinated claims; its row is noise and does not decide anything.
- KG (γ): 0 of 456 claims get a KG signal. The PRD requires the three-signal formula (FR-04), so γ stays in the formula and is reported as non-functional on these descriptive claims, not silently dropped.

