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
import re, sys
import pandas as pd

GOLD = "gold_final.csv"
OUT = "claim_quality.csv"
STRIPPED_SYMBOL = re.compile(r"\d+\s+of\s+the\b")   # e.g. "65 of the warming" (% stripped)

_nlp = None
def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            _nlp = False
    return _nlp


def has_finite_clause_en(text: str) -> bool:
    nlp = get_nlp()
    if nlp is False:
        # regex fallback: needs a lowercase word (crude "has a predicate") and > 3 words
        return len(text.split()) > 3 and bool(re.search(r"\b[a-z]{3,}\b", text))
    doc = nlp(text)
    return any(t.dep_ in ("nsubj", "nsubjpass") and t.head.pos_ in ("VERB", "AUX") for t in doc)


def flag(text: str, lang: str) -> tuple[str, str]:
    t = str(text).strip()
    words = t.split()
    if lang == "hi":
        if len(words) < 3:
            return "broken", "too_short"
        return "ok", ""
    # English
    if len(words) < 4:
        return "broken", "too_short"
    if STRIPPED_SYMBOL.search(t):
        return "broken", "stripped_symbol"
    if not has_finite_clause_en(t):
        return "broken", "no_finite_clause"
    return "ok", ""


def main() -> None:
    df = pd.read_csv(GOLD, encoding="utf-8")
    nlp = get_nlp()
    print("spaCy model:", "loaded" if nlp not in (None, False) else "UNAVAILABLE (regex fallback)")

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
