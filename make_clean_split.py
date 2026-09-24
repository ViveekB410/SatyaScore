"""
make_clean_split.py — the clean, well-formed, freshly-scored dataset + a
train/test split for weight training and the ablation.

Joins gold_final_scored.csv (recomputed bilingual sem_sim/nli_prob) with
claim_quality.csv and keeps only well-formed claims.

The split is GROUPED BY SOURCE QUESTION (StratifiedGroupKFold, 5 folds,
stratified by language x verdict). Every claim extracted from one LLM answer
lands on the same side. The previous plain train_test_split scattered claims
from the same answer across train and test (43 of 52 test questions also
appeared in training), which leaks the answer's context into evaluation.

Fold 0 is the test set. That was fixed BEFORE looking at any result; no other
fold is ever tried (IMPROVEMENT_PLAN.md 1.2 / corrections spec B1).

Writes gold_train_clean.csv / gold_test_clean.csv.
"""
from __future__ import annotations
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

SEED = 42
N_SPLITS = 5
TEST_FOLD = 0  # fixed in advance; do not change after seeing numbers


def main() -> None:
    scored = pd.read_csv("gold_final_scored.csv", encoding="utf-8")
    quality = pd.read_csv("claim_quality.csv", encoding="utf-8")[["claim_id", "quality_flag"]]
    df = scored.merge(quality, on="claim_id", how="left")

    print(f"scored rows: {len(df)}")
    print("signal coverage: sem_sim non-null",
          int(df['sem_sim'].notna().sum()), " nli_prob non-null", int(df['nli_prob'].notna().sum()))

    clean = df[df["quality_flag"] == "ok"].reset_index(drop=True)
    print(f"well-formed (quality_flag==ok): {len(clean)}")
    print(clean.groupby(["language", "gold_verdict"]).size().to_string())

    strata = clean["language"] + "_" + clean["gold_verdict"]
    groups = clean["source_query_id"]
    sgkf = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    train_idx, test_idx = list(sgkf.split(clean, strata, groups))[TEST_FOLD]
    train, test = clean.iloc[train_idx], clean.iloc[test_idx]

    shared = set(train["source_query_id"]) & set(test["source_query_id"])
    if shared:
        raise SystemExit(f"LEAK: {len(shared)} source questions appear in both train and test")

    train.to_csv("gold_train_clean.csv", index=False, encoding="utf-8")
    test.to_csv("gold_test_clean.csv", index=False, encoding="utf-8")
    print(f"\ntrain: {len(train)} claims / {train['source_query_id'].nunique()} source questions")
    print(f"test:  {len(test)} claims / {test['source_query_id'].nunique()} source questions")
    print("shared source questions: 0 (asserted)")
    print("train by (lang,verdict):"); print(train.groupby(["language", "gold_verdict"]).size().to_string())
    print("test by (lang,verdict):");  print(test.groupby(["language", "gold_verdict"]).size().to_string())
    print("\nHallucinated claims per split:")
    for lang in ("en", "hi"):
        n_tr = int(((train.language == lang) & (train.gold_verdict == "Hallucinated")).sum())
        n_te = int(((test.language == lang) & (test.gold_verdict == "Hallucinated")).sum())
        print(f"  {lang}: train {n_tr}  test {n_te}")


if __name__ == "__main__":
    main()
