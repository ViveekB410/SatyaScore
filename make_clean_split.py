"""
make_clean_split.py — the clean, well-formed, freshly-scored dataset + a
stratified train/test split for weight training and the ablation.

Joins gold_final_scored.csv (recomputed bilingual sem_sim/nli_prob) with
claim_quality.csv, keeps only well-formed claims, and splits 80/20 stratified
by (language, gold_verdict). Writes gold_train_clean.csv / gold_test_clean.csv.
"""
from __future__ import annotations
import pandas as pd
from sklearn.model_selection import train_test_split

SEED = 42


def main() -> None:
    scored = pd.read_csv("gold_final_scored.csv", encoding="utf-8")
    quality = pd.read_csv("claim_quality.csv", encoding="utf-8")[["claim_id", "quality_flag"]]
    df = scored.merge(quality, on="claim_id", how="left")

    print(f"scored rows: {len(df)}")
    print("signal coverage: sem_sim non-null",
          int(df['sem_sim'].notna().sum()), " nli_prob non-null", int(df['nli_prob'].notna().sum()))

    clean = df[df["quality_flag"] == "ok"].copy()
    print(f"well-formed (quality_flag==ok): {len(clean)}")
    print(clean.groupby(["language", "gold_verdict"]).size().to_string())

    # stratify by language+verdict so both splits keep all classes in both langs
    strata = clean["language"] + "_" + clean["gold_verdict"]
    train, test = train_test_split(clean, test_size=0.2, random_state=SEED, stratify=strata)

    train.to_csv("gold_train_clean.csv", index=False, encoding="utf-8")
    test.to_csv("gold_test_clean.csv", index=False, encoding="utf-8")
    print(f"\ntrain: {len(train)}  test: {len(test)}")
    print("train by (lang,verdict):"); print(train.groupby(["language", "gold_verdict"]).size().to_string())
    print("test by (lang,verdict):");  print(test.groupby(["language", "gold_verdict"]).size().to_string())


if __name__ == "__main__":
    main()
