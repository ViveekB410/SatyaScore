# LLM verifier vs Live system now (NLI, standard corpus) (openai/gpt-oss-120b, evidence: expanded)

The LLM judges evidence retrieved AFTER on-demand Wikipedia expansion (index 9,351 → 34,779 passages, +797 articles). The reference is the live system as it is now (NLI on the standard corpus). Verdict accuracy counts Uncertain as not correct. **Decision rule (fixed before running):** pooled EN+HI TRAIN AUC; a mode is adopted only if ΔAUC vs Live system now (NLI, standard corpus) has a 95% CI entirely above 0. Test and round 3 are reported only.

## round3 (n = 40, Hallucinated 15)

- Live system now (NLI, standard corpus): AUC 0.693; verdicts 14/40 (35%) · Uncertain 10 · when it commits 14/30 (47%)
- NLI on expanded evidence (reported only): AUC 0.632; verdicts 19/40 (48%) · Uncertain 6 · when it commits 19/34 (56%)
- Gated rule, standard corpus (reported only): AUC 0.573; verdicts 6/40 (15%) · Uncertain 33 · when it commits 6/7 (86%)
- Live system after 2026-09-28 (gated rule + Wikipedia expansion) (reported only): AUC 0.675; verdicts 16/40 (40%) · Uncertain 16 · when it commits 16/24 (67%)
- LLM open: AUC 0.959 (Δ vs reference +0.265 [+0.093, +0.464]); verdicts 33/40 (82%) · Uncertain 1 · when it commits 33/39 (85%); unparsable 0
  - system with KG: current (KG else NLI) 24/40 (60%) · Uncertain 7 · when it commits 24/33 (73%)
  - system with KG: new (KG else LLM open) 34/40 (85%) · Uncertain 1 · when it commits 34/39 (87%)

## test (n = 76, Hallucinated 10)

- Live system now (NLI, standard corpus): AUC 0.503; verdicts 28/76 (37%) · Uncertain 30 · when it commits 28/46 (61%)
- NLI on expanded evidence (reported only): AUC 0.433; verdicts 28/76 (37%) · Uncertain 29 · when it commits 28/47 (60%)
- Gated rule, standard corpus (reported only): AUC 0.360; verdicts 27/76 (36%) · Uncertain 41 · when it commits 27/35 (77%)
- Live system after 2026-09-28 (gated rule + Wikipedia expansion) (reported only): AUC 0.388; verdicts 31/76 (41%) · Uncertain 39 · when it commits 31/37 (84%)
- LLM open: AUC 0.591 (Δ vs reference +0.088 [-0.172, +0.385]); verdicts 59/76 (78%) · Uncertain 1 · when it commits 59/75 (79%); unparsable 0

## train (n = 303, Hallucinated 45)

- Live system now (NLI, standard corpus): AUC 0.552; verdicts 104/303 (34%) · Uncertain 137 · when it commits 104/166 (63%)
- NLI on expanded evidence (reported only): AUC 0.538; verdicts 119/303 (39%) · Uncertain 126 · when it commits 119/177 (67%)
- Gated rule, standard corpus (reported only): AUC 0.524; verdicts 110/303 (36%) · Uncertain 168 · when it commits 110/135 (81%)
- Live system after 2026-09-28 (gated rule + Wikipedia expansion) (reported only): AUC 0.538; verdicts 128/303 (42%) · Uncertain 145 · when it commits 128/158 (81%)
- LLM open: AUC 0.717 (Δ vs reference +0.165 [+0.057, +0.274]); verdicts 239/303 (79%) · Uncertain 2 · when it commits 239/301 (79%); unparsable 0

## Decision
- **Adopt LLM open** (train ΔAUC +0.165 [+0.057, +0.274]).
- Used for Hindi too (Hindi train AUC not below NLI's).

## Note added 2026-10-05: outcome and product decision

- **Scope of this decision:** open mode only. Grounded mode was not completed (Groq quota) and is not evaluated.
- **The fixed rule is met for open mode** (train ΔAUC +0.165, 95% CI [+0.057, +0.274]).
- **False alarms** (true claims marked Hallucinated), counted per claim from the cached answers (the rule above
  does not measure them):

| | Live rule (gated + expansion) | LLM open |
|---|---|---|
| train: false alarms | 9 / 258 | **35 / 258** |
| train: hallucinations caught | 5 / 45 | 18 / 45 |
| train: hallucinations Verified | 27 / 45 | 27 / 45 |
| test: false alarms | 3 / 66 | **9 / 66** |
| test: hallucinations caught | 0 / 10 | 2 / 10 |
| round 3: false alarms / caught | 2 / 25, 2 / 15 | 1 / 25, 9 / 15 |

- **Product decision: the LLM verifier stays OFF** (SATYASCORE_LLM_VERIFIER unset). It catches more hallucinations
  but marks about 1 in 7 true claims Hallucinated (live: about 1 in 30). The project's first requirement is not to
  flag genuine text, so this is recorded as a product choice overriding the rule's "adopt", as the gated evidence
  rule's adoption was recorded in results/aggregation_eval.md.
