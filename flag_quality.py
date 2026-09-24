"""
flag_quality.py  --  flags grammatically-broken extraction artifacts in
gold_final.csv, by CODE (no re-annotation). Conservative: it drops only claims
that are genuinely unjudgeable (no finite clause / stripped-symbol number-soup /
too short), and keeps awkward-but-judgeable ones.

English uses spaCy (falls back to regex if the model is unavailable).
Hindi is sentence-level (clean) so only trivially-short claims are flagged.

Writes claim_quality.csv (claim_id, language, gold_verdict, quality_flag, reason).
Reads gold_final.csv; does NOT modify it.
"""
from __future__ import annotations
import sys
import pandas as pd

# The single definition of a "broken" claim lives in the extractor, so the
# extractor's sentence-level fallback and this audit always agree.
from member3_backend.claim_extractor import claim_quality as flag

GOLD = "gold_final.csv"
OUT = "claim_quality.csv"


def main() -> None:
    df = pd.read_csv(GOLD, encoding="utf-8")

    flags = [flag(r.claim_text, r.language) for r in df.itertuples()]
    df["quality_flag"] = [f[0] for f in flags]
    df["quality_reason"] = [f[1] for f in flags]
    df[["claim_id", "language", "gold_verdict", "quality_flag", "quality_reason"]].to_csv(
        OUT, index=False, encoding="utf-8")

    print(f"\nwrote {OUT}")
    print("=== quality by language ===")
    print(df.groupby(["language", "quality_flag"]).size().to_string())
    print("\n=== broken reasons ===")
    print(df[df.quality_flag == "broken"].groupby(["language", "quality_reason"]).size().to_string())

    print("\n=== contamination of the Hallucinated class (the key number) ===")
    h = df[df.gold_verdict == "Hallucinated"]
    print(h.groupby(["language", "quality_flag"]).size().to_string())

    print("\n=== survivors (well-formed) by (language, verdict) ===")
    print(df[df.quality_flag == "ok"].groupby(["language", "gold_verdict"]).size().to_string())

    print("\n=== sample BROKEN English claims (sanity check) ===")
    for t in df[(df.language == "en") & (df.quality_flag == "broken")]["claim_text"].head(6):
        sys.stdout.buffer.write((" x " + str(t)[:100] + "\n").encode("utf-8"))
    print("=== sample OK English claims (should read fine) ===")
    for t in df[(df.language == "en") & (df.quality_flag == "ok")]["claim_text"].head(6):
        sys.stdout.buffer.write((" + " + str(t)[:100] + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
