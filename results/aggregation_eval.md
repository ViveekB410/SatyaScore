# Evidence aggregation: legacy vs gated

Same retrieval, NLI numbers and extractor for both rules (the live objects). **Decision rule (fixed before running):** gated becomes the default only if (a) false alarms fall on FRESH true statements, (b) the train false-alarm rate does not rise, and (c) pooled train ΔAUC has a 95% CI lower bound above -0.03.

## (a) FRESH true statements (none from the design sample) — decides: 99 true lead sentences (seed 11) → 99 claims

| rule | seen en | seen hi | unseen en | unseen hi | **all: false alarms** | all: Verified |
|---|---|---|---|---|---|---|
| gated | 3/26 | 0/18 | 4/39 | 1/16 | **8** (8%) | 43 |
| legacy | 4/26 | 2/18 | 15/39 | 12/16 | **33** (33%) | 40 |

(cells: false alarms / claims)

## Design sample (the fix was designed on it) — reported only: 120 true lead sentences (seed 7) → 128 claims

| rule | seen en | seen hi | unseen en | unseen hi | **all: false alarms** | all: Verified |
|---|---|---|---|---|---|---|
| gated | 4/44 | 0/21 | 5/43 | 0/20 | **9** (7%) | 72 |
| legacy | 8/44 | 1/21 | 14/43 | 7/20 | **30** (23%) | 65 |

(cells: false alarms / claims)

## train (n = 303, Hallucinated 45) — decides (b) and (c)

- ROC-AUC legacy 0.557 → gated 0.526 (Δ -0.031 [-0.093, +0.028])

| rule | correct | true claims marked Hallucinated (false alarms) | real hallucinations caught | Uncertain |
|---|---|---|---|---|
| gated | 110/303 | 8/258 (3%) | 3/45 (7%) | 168 |
| legacy | 104/303 | 47/258 (18%) | 11/45 (24%) | 137 |

## test (n = 76, Hallucinated 10) — reported only

- ROC-AUC legacy 0.502 → gated 0.364 (Δ -0.138 [-0.313, +0.015])

| rule | correct | true claims marked Hallucinated (false alarms) | real hallucinations caught | Uncertain |
|---|---|---|---|---|
| gated | 27/76 | 3/66 (5%) | 0/10 (0%) | 41 |
| legacy | 28/76 | 14/66 (21%) | 3/10 (30%) | 30 |

## round3 (n = 40, Hallucinated 15) — reported only

- ROC-AUC legacy 0.688 → gated 0.571 (Δ -0.117 [-0.372, +0.146]) (NLI part; the KG decides 12 claims)

| rule | correct | true claims marked Hallucinated (false alarms) | real hallucinations caught | Uncertain |
|---|---|---|---|---|
| gated | 16/40 | 1/25 (4%) | 2/15 (13%) | 23 |
| legacy | 24/40 | 9/25 (36%) | 12/15 (80%) | 7 |

## Decision
- (a) fewer false alarms on fresh true statements: **yes** (33 → 8)
- (b) train false-alarm rate not higher: **yes**
- (c) train ΔAUC -0.031 [-0.093, +0.028], lower bound above -0.03: **no**
- **Keep legacy as the default.**

## Product decision (recorded 2026-09-28, AFTER the result above)
- The pre-fixed rule says **keep legacy**: check (c) failed.
- The project owner chose **gated as the live default anyway**, as a product decision: a fact-checker
  should answer "Uncertain — not enough evidence" rather than wrongly call genuine text Hallucinated.
  Measured cost, stated plainly: false alarms on fresh true statements fall 33 → 8 of 99, but real
  hallucinations caught fall on every labelled set (train 11 → 3 of 45; test 3 → 0 of 10; round 3
  12 → 2 of 15). The legacy rule's catches were largely made by the same mechanism that produces
  the false alarms (a passage about another subject read as a contradiction): on train it marks 58
  claims Hallucinated, 11 correctly (19%, against a 15% base rate).
- `SATYASCORE_AGGREGATION=legacy` restores the old behaviour. The intended source of detection power
  is the LLM verifier (`llm_verifier_eval.py --evidence expanded`), evaluated under its own fixed rule.
