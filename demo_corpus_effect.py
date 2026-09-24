"""
demo_corpus_effect.py -- IMPROVEMENT_PLAN Phase 4: do more sources hurt the
evidence NLI sees?

The demo corpus is the experiment corpus plus extra topics (a strict superset),
so it tests the distractor cost of adding sources. Article-level recall drops
(results/retrieval_comparison_demo.md), but a new article may legitimately hold
the evidence, so the deciding test is downstream: NLI AUC (Verified vs
Hallucinated) when NLI reads the DEMO corpus's top-1 passage, versus the stored
signal from the experiment corpus's top-1 passage. Same NLI settings as
recompute_signals.py (192-token cap, batches of 16).

DECISION RULE (fixed before running): the expansion is harmful if the English
paired ΔAUC (demo - experiment) has a 95% CI entirely below 0.

Writes results/demo_corpus_effect.md.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from nli_components import components, paired
from retrieval_eval import corpus_vectors, encode

ROOT = Path(__file__).resolve().parent


def main() -> None:
    passages = json.loads((ROOT / "corpus_passages_demo.json").read_text(encoding="utf-8"))
    texts = [p["text"] for p in passages]
    titles = [p["title"] for p in passages]
    exp_titles = {p["title"] for p in json.loads((ROOT / "corpus_passages.json").read_text(encoding="utf-8"))}
    df = pd.read_csv(ROOT / "gold_final_scored.csv", encoding="utf-8")
    q = pd.read_csv(ROOT / "claim_quality.csv")[["claim_id", "quality_flag"]]
    df = df.merge(q, on="claim_id")
    df = df[(df.quality_flag == "ok") & df.gold_verdict.isin(["Verified", "Hallucinated"])].reset_index(drop=True)

    S = encode("xlmr", df.claim_text.tolist(), passage=False) @ corpus_vectors("xlmr", texts, "demo").T
    top1 = S.argmax(axis=1)
    df["demo_top1_new_topic"] = [titles[j] not in exp_titles for j in top1]
    print(f"{len(df)} claims; NLI on demo top-1 ...", flush=True)
    C = components([texts[j] for j in top1], df.claim_text.tolist())
    df["net_demo"] = 0.5 + 0.5 * (C[:, 0] - C[:, 2])

    L = ["# More sources — effect on the evidence NLI sees (Phase 4)\n",
         "NLI AUC (Verified vs Hallucinated; 0.5 = chance) when NLI reads the top-1 passage from the "
         "**experiment** corpus (stored signal) vs the **demo** corpus (experiment + extra topics). "
         "Well-formed claims.\n",
         "**Decision rule (fixed before running):** the expansion is harmful if the English paired "
         "ΔAUC (demo − experiment) has a 95% CI entirely below 0.\n",
         "| Lang | n V / H | top-1 from a new topic | AUC experiment | AUC demo | ΔAUC [95% CI] |",
         "| --- | --- | --- | --- | --- | --- |"]
    res = {}
    for lang in ("en", "hi"):
        d = df[df.language == lang]
        y = (d.gold_verdict == "Verified").astype(int).to_numpy()
        dl, lo, hi = paired(y, d.nli_prob.to_numpy(), d.net_demo.to_numpy())
        res[lang] = (dl, lo, hi)
        L.append(f"| {lang.upper()} | {y.sum()} / {(1 - y).sum()} | {d.demo_top1_new_topic.mean():.0%} | "
                 f"{roc_auc_score(y, d.nli_prob):.3f} | {roc_auc_score(y, d.net_demo):.3f} | "
                 f"{dl:+.3f} [{lo:+.3f}, {hi:+.3f}] |")
    dl, lo, hi = res["en"]
    L += ["", "## Decision",
          ("- **Harmful:** the extra sources make NLI's evidence measurably worse on English."
           if hi < 0 else
           f"- **No demonstrated harm** to NLI's discrimination (English ΔAUC {dl:+.3f}, CI "
           f"[{lo:+.3f}, {hi:+.3f}] includes 0), even though article-level recall drops. Either "
           f"the new articles often hold equally usable evidence, or NLI is too weak for the "
           f"difference to show. More sources for the demo are acceptable on this evidence; "
           f"retrieval must still be re-measured after any expansion."),
          "- Hindi has 9 Hallucinated claims; its row is noise.\n"]
    out = ROOT / "results" / "demo_corpus_effect.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
