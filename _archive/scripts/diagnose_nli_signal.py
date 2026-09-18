"""
Diagnoses whether nli_prob is actually carrying useful signal for
gold_verdict, independent of anything about training itself. If nli_prob
is flat/near-constant regardless of verdict, that's decisive evidence the
signal isn't informative for this model -- not a training bug, not a
relevance-threshold issue, just "this signal doesn't distinguish these
claims for this dataset."

Usage:
    python diagnose_nli_signal.py
"""

import pandas as pd
import numpy as np

df = pd.read_csv("SatyaScore_final_gold_456claims_v2.csv")

# Coerce to numeric; blanks become NaN and are excluded from the stats below
df["nli_prob"] = pd.to_numeric(df["nli_prob"], errors="coerce")
df["sem_sim"] = pd.to_numeric(df["sem_sim"], errors="coerce")

has_nli = df["nli_prob"].notna()
print(f"Rows with a real (non-blank) nli_prob: {has_nli.sum()} / {len(df)}")
print(f"  (everything else has NO nli_prob at all -- can't carry signal it doesn't have)")
print()

sub = df[has_nli]

print("=== nli_prob distribution BY gold_verdict ===")
print(sub.groupby("gold_verdict")["nli_prob"].describe()[["count", "mean", "std", "min", "max"]])
print()

print("=== sem_sim distribution BY gold_verdict (for comparison) ===")
print(df[df["sem_sim"].notna()].groupby("gold_verdict")["sem_sim"].describe()[["count", "mean", "std", "min", "max"]])
print()

# Point-biserial-style check: does nli_prob separate Hallucinated from
# everything else at all? (Hallucinated should, in theory, have LOWER
# nli_prob if the signal is working -- evidence shouldn't entail a false claim)
sub = sub.copy()
sub["is_hallucinated"] = (sub["gold_verdict"] == "Hallucinated").astype(int)
if sub["is_hallucinated"].sum() > 0 and sub["is_hallucinated"].sum() < len(sub):
    corr = sub["nli_prob"].corr(sub["is_hallucinated"])
    print(f"Correlation(nli_prob, is_hallucinated): {corr:.4f}")
    print("  (expect a MEANINGFUL NEGATIVE number if NLI is working --")
    print("   near zero means nli_prob barely distinguishes hallucinated from not)")
else:
    print("Not enough class variation among non-blank-nli rows to compute correlation.")
print()

print("=== Quick read ===")
mean_by_verdict = sub.groupby("gold_verdict")["nli_prob"].mean()
spread = mean_by_verdict.max() - mean_by_verdict.min()
print(f"Spread between highest and lowest mean nli_prob across verdict classes: {spread:.4f}")
if spread < 0.05:
    print("-> VERY FLAT. nli_prob looks close to uninformative for distinguishing verdicts here.")
elif spread < 0.15:
    print("-> WEAK separation. Some signal, but not strong.")
else:
    print("-> REAL separation exists between classes -- worth investigating why training didn't use it.")
