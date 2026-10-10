# Public benchmarks: FEVER and Mu-SHROOM (live system)

Protocol fixed before the run: `results/public_benchmarks_PROTOCOL.md`. Reported only; nothing was tuned on these data.

## FEVER paper_dev (English), random sample (seed 20261010)

### Live system

| | Verified | Hallucinated | Uncertain |
|---|---|---|---|
| SUPPORTS (150) | 107/150 (71%; 95% CI 64%-78%) | 17/150 (11%; 95% CI 7%-17%) (false alarms) | 26/150 (17%; 95% CI 12%-24%) |
| REFUTES (150) | 24/150 (16%; 95% CI 11%-23%) (missed) | 64/150 (43%; 95% CI 35%-51%) (caught) | 62/150 (41%; 95% CI 34%-49%) |

- Accuracy over decided claims: 171/212 (81%; 95% CI 75%-85%); share decided: 212/300 (71%; 95% CI 65%-76%).

### NLI only (structured sources ignored)

| | Verified | Hallucinated | Uncertain |
|---|---|---|---|
| SUPPORTS (150) | 107/150 (71%; 95% CI 64%-78%) | 17/150 (11%; 95% CI 7%-17%) (false alarms) | 26/150 (17%; 95% CI 12%-24%) |
| REFUTES (150) | 23/150 (15%; 95% CI 10%-22%) (missed) | 64/150 (43%; 95% CI 35%-51%) (caught) | 63/150 (42%; 95% CI 34%-50%) |

- Accuracy over decided claims: 171/211 (81%; 95% CI 75%-86%); share decided: 211/300 (70%; 95% CI 65%-75%).

## Mu-SHROOM test, Hindi

| method | mean IoU | mean Spearman (soft labels) |
|---|---|---|
| Satya-Score (live) | 0.011 | 0.053 |
| mark-all baseline | 0.271 | 0.000 |
| mark-none baseline | 0.000 | 0.000 |

- Answers: 150; claims extracted: 207; answers with at least one claim flagged: 10/150 (7%; 95% CI 4%-12%).
- Flagged claims overlapping a gold hallucinated span: 10/14 (71%; 95% CI 45%-88%).

## Mu-SHROOM test, English

| method | mean IoU | mean Spearman (soft labels) |
|---|---|---|
| Satya-Score (live) | 0.102 | 0.112 |
| mark-all baseline | 0.349 | 0.000 |
| mark-none baseline | 0.032 | 0.000 |

- Answers: 154; claims extracted: 390; answers with at least one claim flagged: 46/154 (30%; 95% CI 23%-38%).
- Flagged claims overlapping a gold hallucinated span: 56/68 (82%; 95% CI 72%-90%).

## Run record

- Items answered: 604 of 604.
- Failures in this run: 0
- FEVER labels refer to Wikipedia of 2017; the system reads today's Wikipedia and Wikidata.
