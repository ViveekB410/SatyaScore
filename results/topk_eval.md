# Passages per claim and title strictness (102,069-passage index)

Index: 102,069 passages. Gated evidence rule throughout. **Decision rule (fixed before running):** the candidate (top-10, strict) replaces the current live setup (top-3, loose) only if on TRAIN (a) false alarms are not more, (b) real hallucinations caught are not fewer, (c) correct verdicts are more.

## Wikipedia sentences, fresh (seed 11) (106 claims) — reported only

| configuration | correct | true claims Verified | **true claims marked Hallucinated** | real hallucinations caught | Uncertain |
|---|---|---|---|---|---|
| current (top-3, loose) | 82/106 (77%) | 82/106 | **3/106** (3%) | — | 21 |
| candidate (top-10, strict) | 92/106 (87%) | 92/106 | **3/106** (3%) | — | 11 |
| top-10, loose | 91/106 (86%) | 91/106 | **3/106** (3%) | — | 12 |
| top-3, strict | 83/106 (78%) | 83/106 | **3/106** (3%) | — | 20 |

## train (303 claims) — decides

| configuration | correct | true claims Verified | **true claims marked Hallucinated** | real hallucinations caught | Uncertain |
|---|---|---|---|---|---|
| current (top-3, loose) | 130/303 (43%) | 127/258 | **8/258** (3%) | 3/45 | 143 |
| candidate (top-10, strict) | 170/303 (56%) | 165/258 | **11/258** (4%) | 5/45 | 95 |
| top-10, loose | 172/303 (57%) | 165/258 | **15/258** (6%) | 7/45 | 89 |
| top-3, strict | 131/303 (43%) | 128/258 | **6/258** (2%) | 3/45 | 144 |

## test (76 claims) — reported only

| configuration | correct | true claims Verified | **true claims marked Hallucinated** | real hallucinations caught | Uncertain |
|---|---|---|---|---|---|
| current (top-3, loose) | 29/76 (38%) | 29/66 | **0/66** (0%) | 0/10 | 40 |
| candidate (top-10, strict) | 42/76 (55%) | 42/66 | **2/66** (3%) | 0/10 | 23 |
| top-10, loose | 42/76 (55%) | 42/66 | **2/66** (3%) | 0/10 | 23 |
| top-3, strict | 29/76 (38%) | 29/66 | **0/66** (0%) | 0/10 | 40 |

## round3 (40 claims) — reported only

| configuration | correct | true claims Verified | **true claims marked Hallucinated** | real hallucinations caught | Uncertain |
|---|---|---|---|---|---|
| current (top-3, loose) | 24/40 (60%) | 19/25 | **3/25** (12%) | 5/15 | 12 |
| candidate (top-10, strict) | 25/40 (62%) | 20/25 | **2/25** (8%) | 5/15 | 12 |
| top-10, loose | 26/40 (65%) | 20/25 | **4/25** (16%) | 6/15 | 9 |
| top-3, strict | 24/40 (60%) | 19/25 | **2/25** (8%) | 5/15 | 13 |

## Decision
- (a) false alarms not more: **no**
- (b) real hallucinations caught not fewer: **yes**
- (c) more correct verdicts: **yes**
- **Keep the current setup.**

## Product decision (recorded 2026-09-28, AFTER the result above)
- The pre-fixed rule says **keep the current setup**: check (a) failed (train false alarms 8 → 11 of 258).
- The project owner chose the **candidate (top-10 passages, strict title matching) as the live default**,
  as a product decision. Measured gain: train correct verdicts 130 → 170 of 303 (true claims Verified
  127 → 165, real hallucinations caught 3 → 5); fresh true Wikipedia sentences Verified 82 → 92 of 106
  with false alarms unchanged (3); test correct 29 → 42 of 76 (false alarms 0 → 2); round 3 24 → 25
  of 40 (false alarms 3 → 2). Cost, stated plainly: 3 more of 258 true train claims wrongly marked
  Hallucinated (3.1% → 4.3%).
- `SATYASCORE_NLI_TOP_K=3` restores reading three passages.
