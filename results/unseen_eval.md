# Unseen data: gated rule, with and without Wikipedia expansion

Live objects; the expanded index gained 1106 articles (index 44,707 passages). **Decision rule (fixed before running):** expansion becomes the default only if on TRAIN, versus gated alone, (a) false alarms are not more, (b) real hallucinations caught are not fewer, and (c) correct verdicts are more.

## Wikipedia sentences, fresh (seed 11) (99 claims) — reported only

| configuration | correct | true claims Verified | **true claims marked Hallucinated** | real hallucinations caught | Uncertain |
|---|---|---|---|---|---|
| legacy | 40/99 (40%) | 40/99 | **33/99** (33%) | — | 26 |
| gated | 43/99 (43%) | 43/99 | **8/99** (8%) | — | 48 |
| gated + expansion | 77/99 (78%) | 77/99 | **6/99** (6%) | — | 16 |

## Wikipedia sentences, design sample (seed 7) (128 claims) — reported only

| configuration | correct | true claims Verified | **true claims marked Hallucinated** | real hallucinations caught | Uncertain |
|---|---|---|---|---|---|
| legacy | 65/128 (51%) | 65/128 | **30/128** (23%) | — | 33 |
| gated | 72/128 (56%) | 72/128 | **9/128** (7%) | — | 47 |
| gated + expansion | 100/128 (78%) | 100/128 | **8/128** (6%) | — | 20 |

## train (303 claims) — decides

| configuration | correct | true claims Verified | **true claims marked Hallucinated** | real hallucinations caught | Uncertain |
|---|---|---|---|---|---|
| legacy | 104/303 (34%) | 93/258 | **47/258** (18%) | 11/45 | 137 |
| gated | 110/303 (36%) | 107/258 | **8/258** (3%) | 3/45 | 168 |
| gated + expansion | 125/303 (41%) | 122/258 | **8/258** (3%) | 3/45 | 150 |

## test (76 claims) — reported only

| configuration | correct | true claims Verified | **true claims marked Hallucinated** | real hallucinations caught | Uncertain |
|---|---|---|---|---|---|
| legacy | 28/76 (37%) | 25/66 | **14/66** (21%) | 3/10 | 30 |
| gated | 27/76 (36%) | 27/66 | **3/66** (5%) | 0/10 | 41 |
| gated + expansion | 28/76 (37%) | 28/66 | **0/66** (0%) | 0/10 | 41 |

## round3 (40 claims) — reported only

| configuration | correct | true claims Verified | **true claims marked Hallucinated** | real hallucinations caught | Uncertain |
|---|---|---|---|---|---|
| legacy | 24/40 (60%) | 12/25 | **9/25** (36%) | 12/15 | 7 |
| gated | 16/40 (40%) | 14/25 | **1/25** (4%) | 2/15 | 23 |
| gated + expansion | 23/40 (57%) | 18/25 | **4/25** (16%) | 5/15 | 12 |

## Decision
- (a) false alarms not more: **yes**
- (b) real hallucinations caught not fewer: **yes**
- (c) more correct verdicts: **yes**
- **Switch expansion on by default.**
