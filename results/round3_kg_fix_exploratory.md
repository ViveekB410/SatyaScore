# Round 3 — KG place-linking fix: EXPLORATORY re-run

> **Not pre-registered.** The fix was made after the labels were seen, to correct a diagnosed bug (place names linked to non-places: "Erode" → a given name, "Naigaon" → a monorail station, "Niphad" → an insect genus, "Bodua" → an encyclopedia article). Only the KG signal was recomputed; NLI and labels are unchanged. The pre-registered result stays `results/round3_kg_pilot.md`. Labels are AI-assisted, annotator-verified (Deviation 3).

- KG status before: {'unlinked': 17, 'unknown': 15, 'supported': 8, 'contradicted': 5}
- KG status after: {'unlinked': 19, 'unknown': 14, 'supported': 10, 'contradicted': 2}

## Claims whose KG status changed
| claim | gold | before | after |
| --- | --- | --- | --- |
| Savitribai Phule was born in Naigaon near Pune in the state of Maharashtra India on 3 Janu | Verified | contradicted | supported |
| The Asian Development Bank is headquartered in Manila Philippines. | Hallucinated | unknown | unlinked |
| Srinivasa Ramanujan was born in Erode in the state of Tamil Nadu India. | Verified | contradicted | supported |
| Kanaklata Barua was born in Bodua a village in the Darrang district of Assam India. | Hallucinated | contradicted | unlinked |

## KG correctness on gold claims
- KG **supported** → gold Verified: 10/10 (100%, 95% CI [72%, 100%])
- KG **contradicted** → gold Hallucinated: 2/2 (100%, 95% CI [34%, 100%])

## All gold claims (exploratory)
n = 40 gold claims (Verified 25, Hallucinated 15).

| Score | AUC | Hallucinated-F1 @0.35/0.65 |
| --- | --- | --- |
| NLI only (semantic+NLI, SemSim weight 0) | 0.704 | 0.512 |
| KG only | 0.740 | 0.235 |
| **Fused NLI + KG (full CMHSA)** | 0.848 | 0.649 |
| 1 − P(contradiction) | 0.771 | 0.533 |

- **H1 (PRD KG ablation):** ΔAUC fused − NLI = +0.144 [+0.044, +0.275]; ΔHallucinated-F1 = +0.137 [+0.047, +0.248] (PRD target ≥ +0.03).
  → **KG helps on relational claims** (CI above 0).
- **H3 (contradiction re-test):** ΔAUC = +0.067 [-0.107, +0.235] → not adopted.

## Without the 3 coreference-garbled claims (exploratory)
n = 38 gold claims (Verified 25, Hallucinated 13).

| Score | AUC | Hallucinated-F1 @0.35/0.65 |
| --- | --- | --- |
| NLI only (semantic+NLI, SemSim weight 0) | 0.763 | 0.500 |
| KG only | 0.746 | 0.267 |
| **Fused NLI + KG (full CMHSA)** | 0.886 | 0.647 |
| 1 − P(contradiction) | 0.778 | 0.571 |

- **H1 (PRD KG ablation):** ΔAUC fused − NLI = +0.123 [+0.032, +0.253]; ΔHallucinated-F1 = +0.147 [+0.054, +0.262] (PRD target ≥ +0.03).
  → **KG helps on relational claims** (CI above 0).
- **H3 (contradiction re-test):** ΔAUC = +0.015 [-0.165, +0.195] → not adopted.

