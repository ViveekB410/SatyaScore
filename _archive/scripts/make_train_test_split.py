"""
Creates a stratified 80/20 train/test split of the gold-labeled dataset,
stratified by (language, gold_verdict) so both splits keep roughly the
same class balance and language mix as the full set. This did not exist
anywhere in the project before -- all 456 claims were previously used to
both train weights AND (if we hadn't caught this) evaluate them, which
would have measured memorization, not generalization.

Usage:
    python make_train_test_split.py
"""

import pandas as pd
from sklearn.model_selection import train_test_split

SOURCE_PATH = "SatyaScore_final_gold_456claims_v2.csv"
TRAIN_PATH = "gold_train.csv"
TEST_PATH = "gold_test.csv"
TEST_FRACTION = 0.2
RANDOM_SEED = 42  # fixed for reproducibility -- report this in the paper

df = pd.read_csv(SOURCE_PATH)
df["strata"] = df["language"] + "_" + df["gold_verdict"]

# Any stratum with fewer than 2 examples can't be split at all (sklearn
# requires at least 2 per class for stratification) -- fall back to an
# unstratified split for just those rows rather than crashing.
strata_counts = df["strata"].value_counts()
tiny_strata = strata_counts[strata_counts < 2].index
df_splittable = df[~df["strata"].isin(tiny_strata)]
df_tiny = df[df["strata"].isin(tiny_strata)]

if len(df_tiny):
    print(f"WARNING: {len(df_tiny)} rows in strata too small to stratify "
          f"({list(tiny_strata)}) -- these go entirely into the TRAIN split.")

train_df, test_df = train_test_split(
    df_splittable,
    test_size=TEST_FRACTION,
    stratify=df_splittable["strata"],
    random_state=RANDOM_SEED,
)
train_df = pd.concat([train_df, df_tiny], ignore_index=True)

train_df = train_df.drop(columns=["strata"])
test_df = test_df.drop(columns=["strata"])

train_df.to_csv(TRAIN_PATH, index=False)
test_df.to_csv(TEST_PATH, index=False)

print(f"\nTrain: {len(train_df)} rows -> {TRAIN_PATH}")
print(train_df.groupby(["language", "gold_verdict"]).size())
print(f"\nTest: {len(test_df)} rows -> {TEST_PATH}")
print(test_df.groupby(["language", "gold_verdict"]).size())
