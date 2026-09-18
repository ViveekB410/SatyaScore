"""
rebuild_gold.py

Authoritative source = the clean UTF-8 annotator export that already lives in
the project:  final annotator file(Sheet1) (1).csv  (456 real claims, intact
Devanagari, Final Gold Verdict). The old SatyaScore_final_gold_456claims.csv was
a broken cp1252 export of this and lost all Hindi to '?'. This rebuilds a clean
gold CSV with the pipeline schema and real UTF-8.

WRITES ONE NEW FILE: gold_456_clean.csv. Touches nothing else.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

SRC = Path("final annotator file(Sheet1) (1).csv")
OUT = Path("gold_456_clean.csv")

COLMAP = {
    "Claim ID": "claim_id",
    "Query ID": "source_query_id",
    "Domain": "domain",
    "Language": "language",
    "Source LLM": "source_llm",
    "Atomic Claim to Verify": "claim_text",
    "Semantic Sim (sem_sim)": "sem_sim",
    "NLI Prob (nli_prob)": "nli_prob",
    "KG Conf (kg_conf)": "kg_conf",
    "Final Gold Verdict": "gold_verdict",
    "AI Suggested Verdict": "ai_verdict",
    "AI Reasoning": "gold_reasoning",
    "Gold Evidence URL": "evidence_url",
    "Override / Review Notes": "review_notes",
}
LANG = {"en": "en", "english": "en", "hi": "hi", "hindi": "hi"}
VERDICTS = {"verified": "Verified", "uncertain": "Uncertain", "hallucinated": "Hallucinated"}


def has_dev(v) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in str(v))


def norm_verdict(v):
    return VERDICTS.get(str(v).strip().lower(), str(v).strip())


def main() -> None:
    raw = pd.read_csv(SRC, encoding="utf-8")
    df = raw[[c for c in COLMAP if c in raw.columns]].rename(columns=COLMAP)

    df["language"] = df["language"].astype(str).str.strip().str.lower().map(LANG).fillna(df["language"])
    df["gold_verdict"] = df["gold_verdict"].map(norm_verdict)
    df["ai_verdict"] = df["ai_verdict"].map(norm_verdict)
    df["gold_source"] = df.apply(
        lambda r: "human_override" if r["gold_verdict"] and r["ai_verdict"]
        and r["gold_verdict"] != r["ai_verdict"] else "human_verified", axis=1)
    for col in ("sem_sim", "nli_prob", "kg_conf"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # drop rows with no finalized verdict (kept count reported below)
    blank = df["gold_verdict"].astype(str).str.strip().isin(["", "nan", "None"])
    n_blank = int(blank.sum())
    df = df[~blank].copy()

    df.to_csv(OUT, index=False, encoding="utf-8")

    print(f"wrote {OUT}  ({len(df)} rows kept, {n_blank} dropped for blank verdict)")
    print("language     :", df["language"].value_counts().to_dict())
    print("gold_verdict :", df["gold_verdict"].value_counts().to_dict())
    print("gold_source  :", df["gold_source"].value_counts().to_dict())
    hi = df[df["language"] == "hi"]
    print(f"Hindi rows: {len(hi)}   with intact Devanagari: {hi['claim_text'].apply(has_dev).sum()}")
    # proof: show two real Hindi claims
    print("\n--- sample restored Hindi claims ---")
    for t in hi[hi["claim_text"].apply(has_dev)]["claim_text"].head(2):
        print("  ", str(t)[:90])
    # cross-check ids against the corrupted v3 files
    try:
        v3 = pd.concat([pd.read_csv("gold_train_v3.csv", encoding="utf-8"),
                        pd.read_csv("gold_test_v3.csv", encoding="utf-8")], ignore_index=True)
        v3_hi = set(v3[v3["language"] == "hi"]["claim_id"])
        rec = set(hi["claim_id"]) & v3_hi
        print(f"\nHindi claim_ids in v3 recoverable from this file: {len(rec)} / {len(v3_hi)} "
              f"(remainder = synthetic perturbations, regenerated separately)")
    except Exception as e:
        print("v3 cross-check skipped:", e)


if __name__ == "__main__":
    main()
