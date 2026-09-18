"""
build_gold_final.py

Correct annotation convention (per the annotator):
  - blank Annotator 1 Verdict  -> annotator AGREES with AI      -> gold = AI verdict
  - "ok"                        -> also agreement               -> gold = AI verdict
  - any written verdict + note  -> DISAGREEMENT / override       -> gold = human verdict

So every one of the 456 claims has a gold label. Source: the clean UTF-8
'final annotator file(Sheet1) (1).csv' (intact Devanagari). Writes real UTF-8.

WRITES: gold_final.csv  (complete 456-claim gold). Touches nothing else.
"""
from __future__ import annotations
from pathlib import Path
import sys
import pandas as pd

SRC = Path("final annotator file(Sheet1) (1).csv")
OUT = Path("gold_final.csv")

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
VMAP = {"verified": "Verified", "uncertain": "Uncertain", "hallucinated": "Hallucinated"}
# informal / typo human labels -> canonical verdict
HUMAN = {
    "ok": "AGREE", "": "AGREE", "nan": "AGREE", "none": "AGREE",
    "verified": "Verified", "correct": "Verified", "true": "Verified",
    "uncertain": "Uncertain", "unsure": "Uncertain", "unclear": "Uncertain",
    "hallucinated": "Hallucinated", "hallucination": "Hallucinated", "false": "Hallucinated",
    "halluscinated": "Hallucinated", "hallluscinated": "Hallucinated", "halucinated": "Hallucinated",
}


def norm_ai(v):
    return VMAP.get(str(v).strip().lower(), str(v).strip())


def has_dev(v) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in str(v))


def main() -> None:
    raw = pd.read_csv(SRC, encoding="utf-8")
    df = raw[[c for c in COLMAP if c in raw.columns]].rename(columns=COLMAP)
    df["language"] = df["language"].astype(str).str.strip().str.lower().map(LANG).fillna(df["language"])
    df["ai_verdict"] = df["ai_verdict"].map(norm_ai)

    a1 = df["annotator1_raw"].astype(str).str.strip().str.lower()
    mapped = a1.map(HUMAN)
    unmapped = sorted(set(a1[df["annotator1_raw"].notna() & mapped.isna()]))
    if unmapped:
        print("UNMAPPED annotator labels (treated as AGREE — tell me the right mapping):", unmapped)

    def decide(row_mapped, ai):
        if row_mapped is None or row_mapped == "AGREE":
            return ai, "ai_agreed"
        return row_mapped, ("human_override" if row_mapped != ai else "human_confirmed")

    decided = [decide(m, ai) for m, ai in zip(mapped, df["ai_verdict"])]
    df["gold_verdict"] = [d[0] for d in decided]
    df["gold_source"] = [d[1] for d in decided]
    for col in ("sem_sim", "nli_prob", "kg_conf"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df.to_csv(OUT, index=False, encoding="utf-8")

    print(f"\nwrote {OUT}  ({len(df)} claims, all labelled)")
    print("gold_source :", df["gold_source"].value_counts().to_dict())
    print("\n(lang, gold_verdict):")
    print(df.groupby(["language", "gold_verdict"]).size().to_string())
    for lang in ("en", "hi"):
        sub = df[df["language"] == lang]
        h = sub[sub["gold_source"] == "human_override"]
        print(f"\n{lang.upper()}: {len(sub)} claims | human overrode AI on {len(h)} "
              f"| verdicts={sub['gold_verdict'].value_counts().to_dict()}")
    hi = df[df["language"] == "hi"]
    print(f"\nHindi rows with intact Devanagari: {hi['claim_text'].apply(has_dev).sum()}/{len(hi)}")
    sys.stdout.buffer.write(b"--- sample Hindi claims ---\n")
    for t in hi[hi["claim_text"].apply(has_dev)]["claim_text"].head(2):
        sys.stdout.buffer.write(("   " + str(t)[:80] + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
