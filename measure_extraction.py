"""
measure_extraction.py -- IMPROVEMENT_PLAN.md task 1.1 before/after.

Re-extracts every English LLM answer in raw_responses.json with the OLD claim
extractor (loaded from git, default ref HEAD) and the CURRENT one, and scores
every claim with the same quality rules (claim_extractor.claim_quality -- the
definition flag_quality.py also uses). Also counts claims that lost a % or $
symbol present in their source text (which changes the claim's meaning).

Writes results/extraction_quality.md. Reads only.

    python measure_extraction.py              # old = HEAD
    python measure_extraction.py --old a31c411
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import types
from collections import Counter
from pathlib import Path

from member3_backend import claim_extractor as new_mod
from member3_backend.claim_extractor import claim_quality

ROOT = Path(__file__).resolve().parent
SYMBOLS = ("%", "$")


def load_old_extractor(ref: str):
    src = subprocess.run(["git", "show", f"{ref}:member3_backend/claim_extractor.py"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    mod = types.ModuleType("old_claim_extractor")
    sys.modules[mod.__name__] = mod  # @dataclass looks the module up here
    exec(compile(src, "old_claim_extractor.py", "exec"), mod.__dict__)
    return mod.ClaimExtractor()


def measure(extractor, texts):
    n = 0
    reasons = Counter()
    symbol_lost = 0
    methods = Counter()
    for text in texts:
        for c in extractor.extract(text, "en"):
            n += 1
            methods[c.extraction_method] += 1
            flag, reason = claim_quality(c.text, "en")
            if flag == "broken":
                reasons[reason] += 1
            source = text[c.start_char:c.end_char]
            if any(s in source and s not in c.text for s in SYMBOLS):
                symbol_lost += 1
    return {"n": n, "broken": sum(reasons.values()), "reasons": reasons,
            "symbol_lost": symbol_lost, "methods": methods}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", default="HEAD", help="git ref of the baseline extractor")
    args = ap.parse_args()

    data = json.loads((ROOT / "raw_responses.json").read_text(encoding="utf-8"))
    texts = [r["response_text"] for q in data.values() if q["language"] == "en"
             for r in q["responses"]]

    old = measure(load_old_extractor(args.old), texts)
    new_extractor = new_mod.ClaimExtractor()
    new = measure(new_extractor, texts)

    # Sentences for which the new extractor emits NO claim -- the cost of the
    # fix, listed in full so "0% broken" is never read as "nothing lost".
    nlp = new_mod._get_english_pipeline()
    uncovered = []
    for text in texts:
        claims = new_extractor.extract(text, "en")
        for s in nlp(new_mod._blank_markdown_artifacts(text)).sents:
            if s.text.strip() and not any(c.start_char < s.end_char and c.end_char > s.start_char
                                          for c in claims):
                uncovered.append(" ".join(s.text.split()))

    def pct(m):
        return f"{m['broken']}/{m['n']} ({m['broken'] / m['n']:.1%})"

    L = ["# Claim extraction quality — before / after (task 1.1)\n",
         f"All {len(texts)} English LLM answers in `raw_responses.json`, re-extracted with the "
         f"old extractor (`{args.old}`) and the current one. Every claim scored with the same "
         f"rules (`claim_extractor.claim_quality`, also used by `flag_quality.py`).\n",
         "| | old | new |", "| --- | --- | --- |",
         f"| claims extracted | {old['n']} | {new['n']} |",
         f"| **broken claims** | **{pct(old)}** | **{pct(new)}** |",
         f"| claims that lost a % or $ from their source | {old['symbol_lost']} | {new['symbol_lost']} |",
         "", "## Broken claims by reason", "| reason | old | new |", "| --- | --- | --- |"]
    for r in sorted(set(old["reasons"]) | set(new["reasons"])):
        L.append(f"| {r} | {old['reasons'][r]} | {new['reasons'][r]} |")
    L += ["", "## Extraction method", "| method | old | new |", "| --- | --- | --- |"]
    for m in sorted(set(old["methods"]) | set(new["methods"])):
        L.append(f"| {m} | {old['methods'][m]} | {new['methods'][m]} |")
    L += ["", f"## Sentences that now produce no claim ({len(uncovered)})",
          "Instead of emitting a broken fragment, the new extractor skips sentences that have no "
          "subject: list labels, headings, and bare gerund items. These are unjudgeable as "
          "stand-alone claims. **Known loss:** a real claim is dropped if spaCy's small model "
          "mis-parses its verb as a noun (e.g. \"...the points system awards drivers points...\"); "
          "a larger parser would fix that. Every skipped sentence:", ""]
    L += [f"- {s[:140]}" for s in uncovered]
    L += ["",
          "_Scope: this measures the live extractor on the source answers. The annotated gold "
          "claims in `gold_final.csv` are fixed and are not re-extracted, so their 44 broken "
          "rows stay as they are (tracked in `claim_quality.csv`)._\n"]

    out = ROOT / "results" / "extraction_quality.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
