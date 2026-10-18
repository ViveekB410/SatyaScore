# LLM verifier vs NLI (openai/gpt-oss-120b)

Same claims and evidence as the live system (demo corpus, top-3 passages). Verdict accuracy counts Uncertain as not correct. **Decision rule (fixed before running):** pooled EN+HI TRAIN AUC; a mode replaces NLI only if ΔAUC vs NLI has a 95% CI entirely above 0. Test and round 3 are reported only.

## round3 (n = 40, Hallucinated 15)

- NLI (current): AUC 0.704; verdicts 14/40 (35%) · Uncertain 9 · when it commits 14/31 (45%)
- LLM grounded: AUC 0.540 (Δ vs NLI -0.164 [-0.365, +0.056]); verdicts 4/40 (10%) · Uncertain 36 · when it commits 4/4 (100%); unparsable 0
  - system with KG: current (KG else NLI) 24/40 (60%) · Uncertain 6 · when it commits 24/34 (71%)
  - system with KG: new (KG else LLM grounded) 16/40 (40%) · Uncertain 24 · when it commits 16/16 (100%)
- LLM open: incomplete (0/40 answered)

## test (n = 76, Hallucinated 10)

- NLI (current): AUC 0.503; verdicts 28/76 (37%) · Uncertain 30 · when it commits 28/46 (61%)
- LLM grounded: AUC 0.532 (Δ vs NLI +0.029 [-0.200, +0.276]); verdicts 46/76 (61%) · Uncertain 23 · when it commits 46/53 (87%); unparsable 0
- LLM open: incomplete (0/76 answered)

## train (n = 303, Hallucinated 45)

- NLI (current): AUC 0.547; verdicts 104/303 (34%) · Uncertain 137 · when it commits 104/166 (63%)
- LLM grounded: incomplete (153/303 answered)
- LLM open: incomplete (0/303 answered)

## Decision
- **Pending:** the train split is not complete for every mode (quota); re-run the same command to finish. No change to the live system.
