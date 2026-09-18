"""
rebuild_gold_from_xlsx.py

The authoritative gold data is individual_claims_3person_verification_merged.xlsx
(sheet 'Claims Verification'). The CSV pipeline files were a broken export of it:
a to_csv() without encoding='utf-8' on Windows replaced every Devanagari
character with '?'. This rebuilds a clean gold CSV straight from the xlsx, with
the Hindi intact, written as real UTF-8.

WRITES ONE NEW FILE: gold_456_clean.csv. Touches nothing else.

Run:
    .venv/Scripts/python.exe rebuild_gold_from_xlsx.py
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd

XLSX = Path(r"C:\Users\vivek\Downloads\individual_claims_3person_verification_merged.xlsx")
SHEET = "Claims Verification"
OUT = Path("gold_456_clean.csv")

# xlsx column  ->  gold schema column
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
    "Consensus Verdict (2/3)": "consensus_verdict",
    "Agreement Type": "agreement_type",
}

LANG = {"english": "en", "en": "en", "hindi": "hi", "hi": "hi"}
VERDICTS = {"verified": "Verified", "uncertain": "Uncertain", "hallucinated": "Hallucinated"}


def has_dev(v) -> bool:
    return any("\u0900" <= ch <= "\u097f" for ch in str(v))


def norm_verdict(v):
    return VERDICTS.get(str(v).strip().lower(), str(v).strip() or "")


def main() -> None:
    raw = pd.read_excel(XLSX, sheet_name=SHEET)
    missing = [c for c in COLMAP if c not in raw.columns]
    if missing:
        print("WARNING: expected columns not found:", missing)

    df = raw[[c for c in COLMAP if c in raw.columns]].rename(columns=COLMAP)

    df["language"] = df["language"].astype(str).str.strip().str.lower().map(LANG).fillna(df["language"])
    df["gold_verdict"] = df["gold_verdict"].map(norm_verdict)
    if "ai_verdict" in df:
        df["ai_verdict"] = df["ai_verdict"].map(norm_verdict)

    # provenance: did the humans override the AI's suggestion?
    if "ai_verdict" in df:
        df["gold_source"] = df.apply(
            lambda r: "human_override" if r["gold_verdict"] and r["ai_verdict"]
            and r["gold_verdict"] != r["ai_verdict"] else "human_verified", axis=1)
    else:
        df["gold_source"] = "human_verified"

    for col in ("sem_sim", "nli_prob", "kg_conf"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df.to_csv(OUT, index=False, encoding="utf-8")

    # ---- verification ----
    print(f"wrote {OUT}  ({len(df)} rows)")
    print("language counts:", df["language"].value_counts().to_dict())
    print("verdict counts :", df["gold_verdict"].value_counts().to_dict())
    print("gold_source    :", df["gold_source"].value_counts().to_dict())
    hi = df[df["language"] == "hi"]
    hi_dev = hi["claim_text"].apply(has_dev).sum()
    print(f"Hindi rows: {len(hi)}   with intact Devanagari: {hi_dev}")
    en = df[df["language"] == "en"]
    print(f"English rows: {len(en)}")
    blank = (df["gold_verdict"].astype(str).str.strip() == "").sum()
    if blank:
        print(f"NOTE: {blank} rows have a blank Final Gold Verdict (not yet finalized).")
    # cross-check against the corrupted v3 ids
    try:
        v3 = pd.concat([pd.read_csv("gold_train_v3.csv", encoding="utf-8"),
                        pd.read_csv("gold_test_v3.csv", encoding="utf-8")], ignore_index=True)
        v3_hi = set(v3[v3["language"] == "hi"]["claim_id"])
        recovered = set(hi["claim_id"]) & v3_hi
        print(f"Hindi claim_ids in v3 recovered from xlsx: {len(recovered)} / {len(v3_hi)} "
              f"(remainder are synthetic perturbations, regenerated separately)")
    except Exception as e:
        print("v3 cross-check skipped:", e)


if __name__ == "__main__":
    main()
