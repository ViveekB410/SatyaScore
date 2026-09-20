"""
diagnose_retrieval.py  --  PHASE3 Task B.

Answers WHY the signals don't separate, at the passage level: is the right
evidence being retrieved at all, and if so does NLI use it? For every
Hallucinated claim in gold_final.csv (plus a matched sample of Verified claims):
retrieve top-k, check whether the claim's own source article appears (and at what
rank), and record the NLI outcome for the top-3 pairs.

Writes results/retrieval_diagnostic.csv (per claim) and results/retrieval_diagnostic.md
(summary + an explicit conclusion pointing to Task C1 / C2 / C3).

Uses the EXPERIMENT corpus only. Reads only; regenerates nothing.

    python diagnose_retrieval.py            # full
    python diagnose_retrieval.py --limit 8  # quick smoke test
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from build_corpus import title_from_url
from member1_model.embeddings import CrossLingualEmbedder
from member1_model.nli_scorer import NLIScorer
from member3_backend.faiss_retriever import FAISSRetriever
from member3_backend.pipeline import MIN_RELEVANCE_THRESHOLD

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "final annotator file(Sheet1) (1).csv"
KS = [1, 3, 5, 10]
SEED = 42


def load_source_titles() -> dict[str, str]:
    """claim_id -> source article title (from the AI Evidence URL the claim was
    anchored to; that's what build_corpus indexed)."""
    src = pd.read_csv(SRC, encoding="utf-8")
    out = {}
    for _, r in src.iterrows():
        url = r.get("AI Evidence URL")
        if isinstance(url, str) and "/wiki/" in url:
            out[str(r["Claim ID"])] = title_from_url(url)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cap total claims (quick test)")
    args = ap.parse_args()

    gold = pd.read_csv(ROOT / "gold_final.csv", encoding="utf-8")
    source_titles = load_source_titles()

    # select: all Hallucinated + a matched (per-language) sample of Verified
    parts = []
    for lang in ("en", "hi"):
        hall = gold[(gold.language == lang) & (gold.gold_verdict == "Hallucinated")]
        ver = gold[(gold.language == lang) & (gold.gold_verdict == "Verified")]
        ver_s = ver.sample(n=min(len(hall), len(ver)), random_state=SEED) if len(ver) else ver
        parts.append(hall)
        parts.append(ver_s)
    sel = pd.concat(parts).reset_index(drop=True)
    if args.limit:
        sel = sel.groupby("gold_verdict", group_keys=False).head(max(1, args.limit // 2)).head(args.limit)
    print(f"diagnosing {len(sel)} claims "
          f"({(sel.gold_verdict=='Hallucinated').sum()} Hallucinated, "
          f"{(sel.gold_verdict=='Verified').sum()} Verified)", flush=True)

    # experiment corpus + index (same as the pipeline)
    passages = json.loads((ROOT / "corpus_passages.json").read_text(encoding="utf-8"))
    vectors = np.load(ROOT / "corpus_vectors.npy")
    ptitle = {p["id"]: p["title"] for p in passages}
    retr = FAISSRetriever(n_clusters=1)
    retr.build_index([p["id"] for p in passages], [p["text"] for p in passages], vectors)

    embedder = CrossLingualEmbedder()
    nli = NLIScorer()
    # force XLM-R (uniform space with corpus_vectors) — same as recompute_signals
    cres = embedder.embed(sel["claim_id"].tolist(), sel["claim_text"].tolist(), ["en"] * len(sel))

    rows = []
    for i, (_, claim) in enumerate(sel.iterrows()):
        src_title = source_titles.get(str(claim["claim_id"]))
        r = retr.retrieve(claim["claim_id"], cres.vectors[i], top_k=10)
        titles = [ptitle.get(p.passage_id, "") for p in r.passages]
        scores = [float(p.score) for p in r.passages]

        # rank (1-based) at which the source article first appears
        src_rank = next((j + 1 for j, t in enumerate(titles) if src_title and t == src_title), None)
        in_topk = {k: bool(src_rank and src_rank <= k) for k in KS}

        # NLI outcome for top-3 pairs (argmax label); fraction neutral later
        top3 = r.passages[:3]
        outcomes = []
        if top3:
            res = nli.score_batch(
                claim_ids=[claim["claim_id"]] * len(top3),
                premises=[p.text for p in top3],
                hypotheses=[claim["claim_text"]] * len(top3),
            )
            for x in res:
                probs = {"entailment": x.entailment_prob, "neutral": x.neutral_prob,
                         "contradiction": x.contradiction_prob}
                outcomes.append(max(probs, key=probs.get))

        rows.append({
            "claim_id": claim["claim_id"], "language": claim["language"],
            "label": claim["gold_verdict"], "source_title": src_title or "",
            "top1_sim": scores[0] if scores else float("nan"),
            "top1_above_threshold": bool(scores and scores[0] >= MIN_RELEVANCE_THRESHOLD),
            "src_rank": src_rank if src_rank else "",
            "src_in_top1": in_topk[1], "src_in_top3": in_topk[3],
            "src_in_top5": in_topk[5], "src_in_top10": in_topk[10],
            "nli_top3_outcomes": "|".join(outcomes),
            "nli_frac_neutral": (outcomes.count("neutral") / len(outcomes)) if outcomes else float("nan"),
        })
        if (i + 1) % 10 == 0 or args.limit:
            print(f"  {i+1}/{len(sel)}", flush=True)

    df = pd.DataFrame(rows)
    (ROOT / "results").mkdir(exist_ok=True)
    df.to_csv(ROOT / "results" / "retrieval_diagnostic.csv", index=False, encoding="utf-8")

    # ---- summary ----
    def agg(sub):
        pairs_neutral = sub["nli_frac_neutral"].dropna()
        return {
            "n": len(sub),
            "src_in_top3": sub["src_in_top3"].mean() if len(sub) else float("nan"),
            "src_in_top10": sub["src_in_top10"].mean() if len(sub) else float("nan"),
            "mean_top1_sim": sub["top1_sim"].mean() if len(sub) else float("nan"),
            "frac_pairs_neutral": pairs_neutral.mean() if len(pairs_neutral) else float("nan"),
        }

    L = ["# Retrieval diagnostic\n",
         f"{len(df)} claims diagnosed against the experiment corpus "
         f"({len(passages)} passages). Per-claim rows in `results/retrieval_diagnostic.csv`.\n",
         "## By language and label", "| Group | n | src in top-3 | src in top-10 | mean top-1 sim | pairs neutral |",
         "| --- | --- | --- | --- | --- | --- |"]
    for lang in ("en", "hi"):
        for label in ("Hallucinated", "Verified"):
            sub = df[(df.language == lang) & (df.label == label)]
            if len(sub):
                a = agg(sub)
                L.append(f"| {lang} {label} | {a['n']} | {a['src_in_top3']:.2f} | {a['src_in_top10']:.2f} | "
                         f"{a['mean_top1_sim']:.3f} | {a['frac_pairs_neutral']:.2f} |")

    overall = agg(df)
    hall = df[df.label == "Hallucinated"]
    top3_recall = overall["src_in_top3"]
    frac_neutral = overall["frac_pairs_neutral"]

    # explicit conclusion (thresholds stated)
    if top3_recall < 0.5:
        concl = (f"**RETRIEVAL problem → Task C1.** The source article is in the top-3 only "
                 f"{top3_recall:.0%} of the time — retrieval usually doesn't surface the passage "
                 f"that could settle the claim. Try a stronger multilingual encoder.")
    elif frac_neutral > 0.6:
        concl = (f"**EVIDENCE-GRANULARITY problem → Task C2.** The source article is usually found "
                 f"(top-3 {top3_recall:.0%}), but {frac_neutral:.0%} of claim–passage NLI pairs land "
                 f"in neutral — long passages dilute the signal. Try sentence-level premises + a "
                 f"contradiction signal.")
    else:
        concl = (f"**MODEL / LABEL problem → Task C3.** The source article is usually found "
                 f"(top-3 {top3_recall:.0%}) and NLI is often decisive (neutral only {frac_neutral:.0%}), "
                 f"yet discrimination is still poor — the ceiling is the model or the labels, not retrieval.")
    L += ["\n## Conclusion (decision rule: top-3 recall <0.5 ⇒ C1; else neutral >0.6 ⇒ C2; else C3)", concl, ""]

    out = ROOT / "results" / "retrieval_diagnostic.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))
    print(f"\nwrote {out} and results/retrieval_diagnostic.csv")


if __name__ == "__main__":
    main()
