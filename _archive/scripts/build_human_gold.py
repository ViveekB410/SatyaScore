"""
build_human_gold.py

Builds the ONLY trustworthy labelled dataset that actually exists, from
final annotator file(Sheet1) (1).csv (clean UTF-8, intact Devanagari):
the rows Annotator 1 actually verified. Normalises the informal labels
('ok' -> Verified, etc.), keeps intact Hindi, writes real UTF-8.

WRITES: gold_human_labeled.csv (Annotator-1-verified rows only).
Touches nothing else.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

SRC = Path("final annotator file(Sheet1) (1).csv")
OUT = Path("gold_human_labeled.csv")

COLMAP = {
    "Claim ID": "claim_id", "Query ID": "source_query_id", "Domain": "domain",
    "Language": "language", "Source LLM": "source_llm",
    "Atomic Claim to Verify": "claim_text",
    "Semantic Sim (sem_sim)": "sem_sim", "NLI Prob (nli_prob)": "nli_prob",
    "KG Conf (kg_conf)": "kg_conf",
    "AI Suggested Verdict": "ai_verdict",
    "Annotator 1 Verdict": "annotator1_raw",
    "Annotator 1 Notes & Evidence": "annotator1_notes",
    "AI Reasoning": "ai_reasoning", "Gold Evidence URL": "evidence_url",
}
LANG = {"en": "en", "english": "en", "hi": "hi", "hindi": "hi"}
LABEL = {
    "ok": "Verified", "verified": "Verified", "correct": "Verified", "true": "Verified",
    "hallucinated": "Hallucinated", "hallucination": "Hallucinated", "false": "Hallucinated",
    "halluscinated": "Hallucinated", "hallluscinated": "Hallucinated", "halucinated": "Hallucinated",
    "uncertain": "Uncertain", "unsure": "Uncertain", "unclear": "Uncertain",
}


def has_dev(v) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in str(v))


def main() -> None:
    raw = pd.read_csv(SRC, encoding="utf-8")
    df = raw[[c for c in COLMAP if c in raw.columns]].rename(columns=COLMAP)
    df["language"] = df["language"].astype(str).str.strip().str.lower().map(LANG).fillna(df["language"])

    key = df["annotator1_raw"].astype(str).str.strip().str.lower()
    df["gold_verdict"] = key.map(LABEL)

    unmapped = sorted(set(key[df["annotator1_raw"].notna() & df["gold_verdict"].isna()]))
    if unmapped:
        print("UNMAPPED annotator labels (excluded, tell me how to map):", unmapped)

    human = df[df["gold_verdict"].notna()].copy()
    human["gold_source"] = "annotator1"
    for col in ("sem_sim", "nli_prob", "kg_conf"):
        human[col] = pd.to_numeric(human[col], errors="coerce")

    human.to_csv(OUT, index=False, encoding="utf-8")

    print(f"\nwrote {OUT}  ({len(human)} human-labelled rows of {len(df)} total)")
    print("by language        :", human["language"].value_counts().to_dict())
    print("by verdict          :", human["gold_verdict"].value_counts().to_dict())
    print("by (lang, verdict)  :")
    print(human.groupby(["language", "gold_verdict"]).size().to_string())
    hi = human[human["language"] == "hi"]
    print(f"\nHindi human-labelled rows: {len(hi)}   with intact Devanagari: "
          f"{hi['claim_text'].apply(has_dev).sum()}")
    print("--- sample restored Hindi claims (utf-8) ---")
    import sys
    for t in hi[hi["claim_text"].apply(has_dev)]["claim_text"].head(3):
        sys.stdout.buffer.write(("   " + str(t)[:90] + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
