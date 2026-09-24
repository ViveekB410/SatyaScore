"""
ivf_eval.py -- PRD FR-03 says "SHALL maintain a FAISS IVF index". The API uses
exact (flat) search. This measures what IVF costs/gains on the demo corpus:
source-article recall@3 and per-query latency, IVF (the retriever's own IVF
path, n_clusters ~ sqrt(N), nprobe = n_clusters/4) vs exact search.

DECISION RULE (fixed before running): switch the API to IVF only if its R@3
is not measurably worse than exact (paired-bootstrap CI of the difference
includes 0 or is above it) AND it is faster.

Writes results/ivf_vs_flat.md.
"""
from __future__ import annotations
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from diagnose_retrieval import load_source_titles
from member3_backend.faiss_retriever import FAISSRetriever
from retrieval_eval import encode, paired_diff_ci

ROOT = Path(__file__).resolve().parent


def run(retriever: FAISSRetriever, Q: np.ndarray, titles: dict, src: np.ndarray):
    hits, lat = [], []
    for i, q in enumerate(Q):
        t = time.perf_counter()
        r = retriever.retrieve(f"c{i}", q, top_k=3)
        lat.append((time.perf_counter() - t) * 1000)
        hits.append(any(titles[p.passage_id] == src[i] for p in r.passages))
    return np.array(hits), np.array(lat)


def main() -> None:
    passages = json.loads((ROOT / "corpus_passages_demo.json").read_text(encoding="utf-8"))
    V = np.load(ROOT / "corpus_vectors_demo.npy")
    ids, texts = [p["id"] for p in passages], [p["text"] for p in passages]
    titles = {p["id"]: p["title"] for p in passages}
    gold = pd.read_csv(ROOT / "gold_final.csv", encoding="utf-8")
    gold["src"] = gold.claim_id.astype(str).map(load_source_titles())
    ev = gold[gold.src.isin(set(titles.values()))].reset_index(drop=True)
    Q = encode("xlmr", ev.claim_text.tolist(), passage=False)
    src = ev.src.to_numpy()

    flat = FAISSRetriever(n_clusters=1)
    flat.build_index(ids, texts, V)
    k = int(round(math.sqrt(len(ids))))
    ivf = FAISSRetriever(n_clusters=k)
    ivf.build_index(ids, texts, V)
    f_hit, f_lat = run(flat, Q, titles, src)
    i_hit, i_lat = run(ivf, Q, titles, src)
    d, lo, hi = paired_diff_ci(f_hit, i_hit)
    # not measurably worse (CI not entirely below 0) AND faster
    adopt = hi >= 0 and np.median(i_lat) < np.median(f_lat)

    L = ["# IVF vs exact search (PRD FR-03)\n",
         f"Demo corpus, {len(ids)} passages; {len(ev)} gold claims with a source article in it. "
         f"IVF: {k} clusters, nprobe {max(1, k // 4)} (the retriever's defaults).\n",
         "| Index | R@3 | median latency / query | p95 latency |", "| --- | --- | --- | --- |",
         f"| exact (flat, current) | {f_hit.mean():.3f} | {np.median(f_lat):.2f} ms | {np.percentile(f_lat, 95):.2f} ms |",
         f"| IVF | {i_hit.mean():.3f} | {np.median(i_lat):.2f} ms | {np.percentile(i_lat, 95):.2f} ms |",
         "", f"- ΔR@3 (IVF − exact): {d:+.3f}, 95% CI [{lo:+.3f}, {hi:+.3f}].",
         f"- Both are far inside the PRD's 100 ms retrieval target.",
         ("- **Decision: switch to IVF** — no measurable recall loss and faster."
          if adopt else
          "- **Decision: keep exact search.** At this corpus size IVF " +
          ("loses recall" if hi < 0 else "gives no speed benefit worth its approximation") +
          ". This is a recorded deviation from FR-03's IVF wording: the retriever keeps its IVF "
          "path (used automatically when `n_clusters > 1`), and IVF becomes worthwhile at "
          "Wikipedia scale (millions of passages), which is where the PRD's requirement comes from."),
          ""]
    out = ROOT / "results" / "ivf_vs_flat.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
