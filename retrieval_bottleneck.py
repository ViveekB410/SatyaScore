"""
retrieval_bottleneck.py -- Phase 2 decision test: is retrieval what limits the
detector?

The stored NLI signal (gold_final_scored.csv, from recompute_signals.py) was
computed on each claim's TOP-1 retrieved passage (current XLM-R encoder,
experiment corpus). So claims split naturally into:
  A: the top-1 passage came from the claim's own source article
  B: it did not
If better retrieval would help, NLI should separate Verified from Hallucinated
clearly better in A than in B. If NLI is near chance even in A, a better
retriever (Phase 2.1) cannot fix detection.

The same test is run for the relevance threshold (Phase 2.2): claims whose top-1
cosine is >= the candidate cut-off vs below it.

Metric: NLI ROC-AUC (Verified = 1 vs Hallucinated = 0), well-formed claims, with
a 95% bootstrap CI (2,000 resamples). Uncertain claims are excluded, as in the
results summary. Writes results/retrieval_bottleneck.md. Reads only.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from diagnose_retrieval import load_source_titles
from retrieval_eval import corpus_vectors, encode, ranks_from_scores, source_rank

ROOT = Path(__file__).resolve().parent
N_BOOT = 2000
SEED = 42
FITTED_CUTOFF = 0.66  # from results/retrieval_comparison.md (train-fitted)


def auc_ci(y: np.ndarray, s: np.ndarray):
    if len(set(y)) < 2:
        return None
    rng = np.random.default_rng(SEED)
    vals = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(y), len(y))
        if len(set(y[i])) == 2:
            vals.append(roc_auc_score(y[i], s[i]))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return roc_auc_score(y, s), lo, hi


def row(name: str, df: pd.DataFrame) -> str:
    y = (df.gold_verdict == "Verified").astype(int).to_numpy()
    r = auc_ci(y, df.nli_prob.to_numpy())
    n_v, n_h = int(y.sum()), int((1 - y).sum())
    if r is None:
        return f"| {name} | {n_v} / {n_h} | n/a | |"
    auc, lo, hi = r
    return f"| {name} | {n_v} / {n_h} | {auc:.3f} | [{lo:.3f}, {hi:.3f}] |"


def main() -> None:
    passages = json.loads((ROOT / "corpus_passages.json").read_text(encoding="utf-8"))
    titles = np.array([p["title"] for p in passages])
    scored = pd.read_csv(ROOT / "gold_final_scored.csv", encoding="utf-8")
    q = pd.read_csv(ROOT / "claim_quality.csv", encoding="utf-8")[["claim_id", "quality_flag"]]
    df = scored.merge(q, on="claim_id")
    df = df[(df.quality_flag == "ok") & df.gold_verdict.isin(["Verified", "Hallucinated"])].copy()
    df["src"] = df.claim_id.astype(str).map(load_source_titles())
    df = df[df.src.isin(set(titles))].reset_index(drop=True)

    S = encode("xlmr", df.claim_text.tolist(), passage=False) @ corpus_vectors(
        "xlmr", [p["text"] for p in passages]).T
    df["src_rank"] = source_rank(ranks_from_scores(S), titles, df.src.to_numpy())
    df["top1_sim"] = S.max(axis=1)
    df["src_at_top1"] = df.src_rank == 1

    L = ["# Is retrieval the bottleneck? (Phase 2 decision test)\n",
         "NLI ROC-AUC (Verified vs Hallucinated; 0.5 = chance) on well-formed claims whose source "
         "article is in the experiment corpus. The stored NLI signal was computed on each claim's "
         "top-1 retrieved passage, so the split below is exactly \"NLI saw a passage from the "
         "claim's own source article\" vs \"it did not\".\n"]
    for lang in ("en", "hi"):
        d = df[df.language == lang]
        L += [f"## {lang.upper()}", "| Group | n Verified / Hallucinated | NLI AUC | 95% CI |",
              "| --- | --- | --- | --- |",
              row("all", d),
              row("top-1 passage FROM source article", d[d.src_at_top1]),
              row("top-1 passage NOT from source article", d[~d.src_at_top1]),
              row(f"top-1 cosine >= {FITTED_CUTOFF}", d[d.top1_sim >= FITTED_CUTOFF]),
              row(f"top-1 cosine < {FITTED_CUTOFF}", d[d.top1_sim < FITTED_CUTOFF]), ""]
    # Decision, computed (English only: Hindi has 9 Hallucinated claims -> noise).
    en = df[df.language == "en"]
    y = lambda d: (d.gold_verdict == "Verified").astype(int).to_numpy()  # noqa: E731
    a_auc, a_lo, a_hi = auc_ci(y(en[en.src_at_top1]), en[en.src_at_top1].nli_prob.to_numpy())
    all_auc = roc_auc_score(y(en), en.nli_prob)
    hi_t = en[en.top1_sim >= FITTED_CUTOFF]
    t_auc, t_lo, _ = auc_ci(y(hi_t), hi_t.nli_prob.to_numpy())
    L += ["## Decision (English; Hindi has too few Hallucinated claims to read)",
          f"- Even when NLI saw a passage from the claim's own source article, its AUC is "
          f"{a_auc:.3f} [{a_lo:.3f}, {a_hi:.3f}] — "
          + ("**not distinguishable from chance**." if a_lo <= 0.5 else "above chance."),
          f"- Perfect retrieval would put every claim in that group: best-case AUC {a_auc:.3f} vs "
          f"{all_auc:.3f} today ({a_auc - all_auc:+.3f}). "
          + ("**A better encoder cannot fix detection**; the limit is NLI's use of the evidence "
             "(and the labels), not retrieval. Phase 2.1 (E5/LaBSE) is not pursued."
             if a_lo <= 0.5 else "Retrieval improvements could matter; test Phase 2.1."),
          f"- Relevance threshold: claims with top-1 cosine >= {FITTED_CUTOFF} score AUC {t_auc:.3f} "
          f"(CI low {t_lo:.3f}) — "
          + ("no demonstrated gain, while the cut drops "
             f"{(en.top1_sim < FITTED_CUTOFF).mean():.0%} of claims. Keep "
             "`MIN_RELEVANCE_THRESHOLD = 0.3` (documented as effectively no filter)."
             if t_lo <= 0.5 else "a real gain; consider raising the threshold."),
          "- Caveat: \"from the source article\" is article-level, not the exact evidence passage.\n"]

    out = ROOT / "results" / "retrieval_bottleneck.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
