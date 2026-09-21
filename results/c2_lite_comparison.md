# C2-lite comparison — sentence-level NLI premises

Change: `member3_backend/pipeline.py` can split each retrieved passage into sentences before NLI (cap 8/passage), behind `SATYASCORE_SENTENCE_PREMISES` (**default off** — the live API keeps the whole-passage behaviour until this comparison justifies flipping it). Switch off = the current default; switch on = C2-lite.

- Claims: 112 (56 Hallucinated, 56 Verified), experiment corpus (2674 passages), top-3 retrieval, MIN_RELEVANCE_THRESHOLD=0.3.
- Device: **cuda**. NLI premise units scored: 333 (off) vs 1682 (on).
- Baseline NLI AUC on record (RESULTS_SUMMARY.md): EN 0.558, HI 0.51.

## NLI AUC — does the change separate Hallucinated from Verified better?
(AUC 0.5 = chance; higher = better. This is the metric that decides the change.)

| Group | switch OFF (passage) | switch ON (sentence) | Δ (on − off) |
| --- | --- | --- | --- |
| EN | 0.518 | 0.506 | -0.012 |
| HI | 0.519 | 0.605 | +0.086 |
| Overall | 0.531 | 0.533 | +0.002 |

## ΔAUC 95% CI — paired bootstrap (2000 resamples of claims)
(ΔAUC = AUC(on) − AUC(off). The decision rests on this CI, not the point estimate: the change is only worth turning on if the improvement is larger than the sampling noise. **Rule: flip the default only if the EN CI lower bound is above 0.**)

| Group | ΔAUC (point) | 95% CI | valid resamples |
| --- | --- | --- | --- |
| EN | -0.012 | [-0.121, +0.094] | 2000/2000 |
| HI | 0.086 | [-0.136, +0.333] | 2000/2000 |
| Overall | 0.002 | [-0.097, +0.094] | 2000/2000 |

## Neutral rate — fraction of NLI units landing in neutral
(A drop here is necessary but NOT sufficient — a lower neutral rate can also mean confident *wrong* answers. Read it alongside the AUC above.)

| switch OFF (passage) | switch ON (sentence) |
| --- | --- |
| 0.670 | 0.798 |

## Verdict
**No significant change on English.** NLI AUC 0.518 → 0.506 (ΔAUC -0.012), but the 95% CI [-0.121, +0.094] straddles 0 — the effect is within sampling noise. The rule (flip only if the EN CI lower bound is above 0) is not met, so **the default stays off**. The honest reading is that sentence-level premises are not a reliable win at this sample size; the neutral rate may move without NLI actually separating hallucinated from verified claims any better.

_Hindi has only 9 Hallucinated claims; any HI movement here is noise, not an effect, and is reported for completeness only._
_NLI is deterministic, so these AUC/neutral numbers are the same on CPU or GPU — a full run (no `--limit`) is authoritative; GPU is only faster. A small `--limit` run is a mechanism smoke test only and its numbers are not meaningful._
_This file does not regenerate RESULTS_SUMMARY.md or re-run recompute_signals.py — diagnostic comparison only._

