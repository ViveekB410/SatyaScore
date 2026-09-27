# Round 3 — should the KG decide when it answers? (EXPLORATORY)

> Not pre-registered; decided after the labels were seen. Labels are AI-assisted, annotator-verified (Deviation 3). KG signals after the place-linking fix. English claims only: the KG has no Hindi path in this data.

## All gold claims
n = 40 (Verified 25, Hallucinated 15); KG answered 12

| Score | AUC | Hallucinated-F1 @0.35/0.65 |
| --- | --- | --- |
| NLI only | 0.704 | 0.512 |
| fused (current) | 0.848 | 0.649 |
| kg_decides | 0.872 | 0.649 |
- kg_decides − fused (current): ΔAUC +0.024 [-0.000, +0.083]; ΔHallucinated-F1 +0.000 [+0.000, +0.000]
- kg_decides − NLI only: ΔAUC +0.168 [+0.052, +0.313]; ΔHallucinated-F1 +0.137 [+0.047, +0.248]
- Claims where the KG answered and NLI disagreed by ≥ 0.5: 9; the KG was right on 9.

## Without the 3 coreference-garbled claims
n = 38 (Verified 25, Hallucinated 13); KG answered 12

| Score | AUC | Hallucinated-F1 @0.35/0.65 |
| --- | --- | --- |
| NLI only | 0.763 | 0.500 |
| fused (current) | 0.886 | 0.647 |
| kg_decides | 0.914 | 0.647 |
- kg_decides − fused (current): ΔAUC +0.028 [-0.000, +0.101]; ΔHallucinated-F1 +0.000 [+0.000, +0.000]
- kg_decides − NLI only: ΔAUC +0.151 [+0.036, +0.300]; ΔHallucinated-F1 +0.147 [+0.054, +0.262]
- Claims where the KG answered and NLI disagreed by ≥ 0.5: 9; the KG was right on 9.

