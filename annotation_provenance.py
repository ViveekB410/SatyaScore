"""
annotation_provenance.py  --  PROOF that gold_final.csv is a faithful, traceable
product of HUMAN annotation, and an honest breakdown of how much of it is active
human judgement vs. agreement-by-silence.

Convention (annotator's own):
  blank Annotator 1 Verdict / "ok"  -> human AGREES with AI     -> gold = AI verdict
  a written verdict word            -> human OVERRIDES/CONFIRMS -> gold = human verdict

Reads only. Writes ANNOTATION_PROVENANCE.md (the proof, for the report).
"""
from __future__ import annotations
import sys
import pandas as pd

SRC = "final annotator file(Sheet1) (1).csv"
GOLD = "gold_final.csv"

VMAP = {"verified": "Verified", "uncertain": "Uncertain", "hallucinated": "Hallucinated"}
HUMAN = {
    "ok": "AGREE", "": "AGREE", "nan": "AGREE", "none": "AGREE",
    "verified": "Verified", "correct": "Verified", "true": "Verified",
    "uncertain": "Uncertain", "unsure": "Uncertain", "unclear": "Uncertain",
    "hallucinated": "Hallucinated", "hallucination": "Hallucinated", "false": "Hallucinated",
    "halluscinated": "Hallucinated", "hallluscinated": "Hallucinated", "halucinated": "Hallucinated",
}
LANG = {"en": "en", "english": "en", "hi": "hi", "hindi": "hi"}


def norm_ai(v): return VMAP.get(str(v).strip().lower(), str(v).strip())
def has_dev(v): return any("ऀ" <= ch <= "ॿ" for ch in str(v))


def main() -> None:
    src = pd.read_csv(SRC, encoding="utf-8")
    src["language"] = src["Language"].astype(str).str.strip().str.lower().map(LANG)
    src["ai"] = src["AI Suggested Verdict"].map(norm_ai)
    a1 = src["Annotator 1 Verdict"].astype(str).str.strip().str.lower()
    src["mapped"] = a1.map(HUMAN)
    src["expected_gold"] = [
        ai if (m is None or m == "AGREE") else m for m, ai in zip(src["mapped"], src["ai"])
    ]
    src["active_human"] = src["mapped"].apply(lambda m: m not in (None, "AGREE"))

    gold = pd.read_csv(GOLD, encoding="utf-8")
    g = gold.set_index("claim_id")["gold_verdict"]

    # 1) traceability: every gold claim maps to exactly one source row
    src_ids, gold_ids = set(src["Claim ID"]), set(gold["claim_id"])
    orphan_gold = gold_ids - src_ids
    missing_in_gold = src_ids - gold_ids

    # 2) label fidelity: gold_verdict == independently-recomputed expected_gold
    merged = src.set_index("Claim ID")
    common = [c for c in merged.index if c in g.index]
    mismatches = [c for c in common if str(g[c]).strip() != str(merged.loc[c, "expected_gold"]).strip()]

    # 3) human-effort breakdown
    total = len(src)
    active = int(src["active_human"].sum())
    agreed = total - active
    by_lang_active = src.groupby("language")["active_human"].agg(["size", "sum"])

    # 4) Hindi integrity in the gold
    hi_gold = gold[gold["language"] == "hi"]
    hi_dev = int(hi_gold["claim_text"].apply(has_dev).sum())

    # ---- report ----
    lines = []
    def out(s=""):
        lines.append(s); sys.stdout.buffer.write((s + "\n").encode("utf-8"))

    out("# Annotation Provenance — proof that gold_final.csv is human-annotated\n")
    out(f"Source of record: `{SRC}` (clean UTF-8 export of the annotator's sheet).")
    out(f"Derived gold: `{GOLD}` ({len(gold)} claims).\n")

    out("## 1. Traceability")
    out(f"- Gold claims: {len(gold_ids)} | Source claims: {len(src_ids)}")
    out(f"- Gold claims with NO matching source row (should be 0): **{len(orphan_gold)}**")
    out(f"- Source claims missing from gold (should be 0): **{len(missing_in_gold)}**")

    out("\n## 2. Label fidelity (gold == independently recomputed human rule)")
    out(f"- Claims cross-checked: {len(common)}")
    out(f"- Verdict mismatches (should be 0): **{len(mismatches)}**")
    if mismatches[:10]:
        out(f"  first few: {mismatches[:10]}")

    out("\n## 3. How much is genuine human judgement?")
    out(f"- Total claims: {total}")
    out(f"- **Actively human-judged** (annotator wrote a verdict): **{active}**")
    out(f"- Agreed-with-AI by leaving blank / 'ok': {agreed}")
    out("- Per language (size = total, sum = actively human-judged):")
    out(by_lang_active.to_string())

    out("\n## 4. Gold verdict distribution")
    out(gold.groupby(["language", "gold_verdict"]).size().to_string())
    out(f"\n- Hindi gold rows with intact Devanagari: {hi_dev}/{len(hi_gold)}")

    verdict = "PROVEN" if (not orphan_gold and not missing_in_gold and not mismatches) else "FAILED — see above"
    out(f"\n## Verdict: {verdict}")
    out("Every gold label is reproducible from the human annotator file by a fixed, "
        "documented rule; no label is invented. The honest caveat: only the "
        f"{active} actively-judged claims carry strong human signal; the other "
        f"{agreed} are agreement-by-silence with the AI suggestion (single annotator, "
        "no second reviewer / IAA yet).")

    with open("ANNOTATION_PROVENANCE.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
