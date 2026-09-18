"""
Merges freshly-recomputed sem_sim/nli_prob/kg_conf (from a re-run of
generate_dataset.py under the relevance-threshold-fixed pipeline) with the
existing human-verified gold_verdict labels, matched by claim_id.

This lets us test whether NLI's near-zero trained weight was because NLI
genuinely isn't useful, or because the ORIGINAL nli_prob values were
computed by scoring against irrelevant retrieved evidence (the exact bug
the relevance threshold fixed) -- without needing anyone to re-annotate
anything, since the gold labels themselves don't change.

Usage:
    python merge_fresh_signals.py
"""

import pandas as pd

FRESH_SIGNALS_PATH = "unannotated_dataset.csv"          # just regenerated
EXISTING_GOLD_PATH = "SatyaScore_final_gold_456claims.csv"
OUTPUT_PATH = "SatyaScore_final_gold_456claims_v2.csv"

fresh = pd.read_csv(FRESH_SIGNALS_PATH).set_index("claim_id")
gold = pd.read_csv(EXISTING_GOLD_PATH)

missing = [cid for cid in gold["claim_id"] if cid not in fresh.index]
if missing:
    print(f"WARNING: {len(missing)} claim_ids from the gold file were not found "
          f"in the freshly-regenerated dataset (claim_id/text may have shifted "
          f"if the extractor logic changed again). First few: {missing[:5]}")

for col in ["sem_sim", "nli_prob", "kg_conf"]:
    gold[f"{col}_old"] = gold[col]
    gold[col] = gold["claim_id"].map(fresh[col])

changed = (gold["sem_sim"] != gold["sem_sim_old"]) | (gold["nli_prob"] != gold["nli_prob_old"])
print(f"Rows where signals actually changed: {changed.sum()} / {len(gold)}")

gold.to_csv(OUTPUT_PATH, index=False)
print(f"Written: {OUTPUT_PATH}")
print("Next: DatasetBuilder.to_training_csv(...) on this file, then re-run train_weights.py")
