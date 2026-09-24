"""
retrieval_eval.py -- IMPROVEMENT_PLAN.md Phase 2: does a retrieval change find
the claim's source evidence more often?

Metric (the one that decides Phase 2): SOURCE-ARTICLE RECALL@k -- for each gold
claim, is a passage from the article the claim was annotated against among the
top-k retrieved passages? Evaluated on every gold claim whose source article is
in the experiment corpus (417 claims), not a sample.

Methods:
  dense:<tag>   cosine over corpus vectors from encoder <tag> (xlmr = current)
  bm25          lexical BM25 (k1=1.5, b=0.75 -- textbook defaults, not tuned)
  hybrid:<tag>  reciprocal-rank fusion of dense:<tag> and bm25 (k=60, default)

DECISION RULE (fixed before running): a method replaces the current retrieval
only if its recall@3 beats dense:xlmr with a paired-bootstrap 95% CI (2,000
resamples of claims) entirely above 0. Nothing here is fitted on the evaluation
claims, so there is no train/test issue for recall.

Also calibrates MIN_RELEVANCE_THRESHOLD (Phase 2.2) for a dense encoder: the
cut-off is fitted on the TRAIN split's claims only and reported on TEST.

Writes results/retrieval_comparison.md. Experiment corpus only; reads only.

    python retrieval_eval.py                      # dense:xlmr, bm25, hybrid:xlmr
    python retrieval_eval.py --encoders xlmr e5   # needs the e5 model downloaded
"""
from __future__ import annotations
import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from diagnose_retrieval import load_source_titles
from member3_backend.pipeline import MIN_RELEVANCE_THRESHOLD

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "results" / "_vector_cache"   # git-ignored; re-buildable
KS = (1, 3, 10)
N_BOOT = 2000
SEED = 42

# encoder tag -> (model name, query prefix, passage prefix). E5 is trained with
# "query: " / "passage: " prefixes and underperforms without them.
ENCODERS = {
    "xlmr": ("sentence-transformers/paraphrase-xlm-r-multilingual-v1", "", ""),
    "e5": ("intfloat/multilingual-e5-base", "query: ", "passage: "),
    "labse": ("sentence-transformers/LaBSE", "", ""),
}

# ---------------------------------------------------------------- BM25 -------
_SPLIT = re.compile(r"[\s.,;:!?()\[\]{}\"'`|/\\\-–—।॥]+")


def tokenize(text: str) -> list[str]:
    """Lower-cased tokens split on whitespace/punctuation (Devanagari-safe:
    matras are not split off, unlike a \\w+ regex)."""
    return [t for t in _SPLIT.split(str(text).lower()) if t]


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        toks = [tokenize(d) for d in docs]
        self.n = len(toks)
        self.dl = np.array([len(t) for t in toks], dtype=float)
        self.avgdl = float(self.dl.mean())
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, t in enumerate(toks):
            for term, tf in Counter(t).items():
                self.postings[term].append((i, tf))
        self.idf = {term: math.log(1 + (self.n - len(p) + 0.5) / (len(p) + 0.5))
                    for term, p in self.postings.items()}

    def scores(self, query: str) -> np.ndarray:
        s = np.zeros(self.n)
        for term in set(tokenize(query)):
            for i, tf in self.postings.get(term, ()):
                norm = tf + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avgdl)
                s[i] += self.idf[term] * tf * (self.k1 + 1) / norm
        return s


# ---------------------------------------------------------------- dense ------
def corpus_vectors(tag: str, texts: list[str]) -> np.ndarray:
    if tag == "xlmr":  # the committed corpus vectors ARE the current encoder's
        return np.load(ROOT / "corpus_vectors.npy")
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"corpus_vectors_{tag}.npy"
    if path.exists():
        return np.load(path)
    v = encode(tag, texts, passage=True)
    np.save(path, v)
    return v


_models: dict = {}


def encode(tag: str, texts: list[str], passage: bool) -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    name, qp, pp = ENCODERS[tag]
    if tag not in _models:
        _models[tag] = SentenceTransformer(name, device="cpu")
    prefix = pp if passage else qp
    v = _models[tag].encode([prefix + t for t in texts], batch_size=64,
                            convert_to_numpy=True, show_progress_bar=False)
    v = v / np.clip(np.linalg.norm(v, axis=1, keepdims=True), 1e-12, None)
    return v.astype(np.float32)


# ---------------------------------------------------------------- eval -------
def ranks_from_scores(score_matrix: np.ndarray) -> np.ndarray:
    """(n_claims, n_passages) scores -> passage indices ordered best-first."""
    return np.argsort(-score_matrix, axis=1)


def source_rank(order: np.ndarray, titles: np.ndarray, src: np.ndarray) -> np.ndarray:
    """1-based rank of the first passage from each claim's source article."""
    hit = titles[order] == src[:, None]
    return np.where(hit.any(axis=1), hit.argmax(axis=1) + 1, 10**9)


def rrf(order_a: np.ndarray, order_b: np.ndarray, k: int = 60) -> np.ndarray:
    n = order_a.shape[1]
    fused = np.zeros(order_a.shape)
    rows = np.arange(order_a.shape[0])[:, None]
    ranks = np.arange(1, n + 1)[None, :]
    fused[rows, order_a] += 1.0 / (k + ranks)
    fused[rows, order_b] += 1.0 / (k + ranks)
    return ranks_from_scores(fused)


def paired_diff_ci(a_hit: np.ndarray, b_hit: np.ndarray) -> tuple[float, float, float]:
    """recall(b) - recall(a) with a paired bootstrap 95% CI over claims."""
    rng = np.random.default_rng(SEED)
    n = len(a_hit)
    diffs = []
    for _ in range(N_BOOT):
        i = rng.integers(0, n, n)
        diffs.append(b_hit[i].mean() - a_hit[i].mean())
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(b_hit.mean() - a_hit.mean()), float(lo), float(hi)


def calibrate_threshold(best_rel: np.ndarray, best_irr: np.ndarray, is_train: np.ndarray):
    """Pick the cosine cut-off that best separates a claim's best source-article
    passage (relevant) from its best other-article passage (irrelevant), by
    Youden's J on TRAIN claims only; report the same cut-off on TEST."""
    ytr = np.r_[np.ones(is_train.sum()), np.zeros(is_train.sum())]
    str_ = np.r_[best_rel[is_train], best_irr[is_train]]
    grid = np.round(np.arange(0.05, 0.95, 0.01), 2)
    j = [((str_[ytr == 1] >= t).mean() - (str_[ytr == 0] >= t).mean()) for t in grid]
    t_star = float(grid[int(np.argmax(j))])

    def rates(t, mask):
        return float((best_rel[mask] >= t).mean()), float((best_irr[mask] >= t).mean())
    te = ~is_train
    return t_star, {t: {"train": rates(t, is_train), "test": rates(t, te)}
                    for t in (MIN_RELEVANCE_THRESHOLD, t_star)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--encoders", nargs="+", default=["xlmr"], choices=list(ENCODERS))
    args = ap.parse_args()

    passages = json.loads((ROOT / "corpus_passages.json").read_text(encoding="utf-8"))
    texts = [p["text"] for p in passages]
    titles = np.array([p["title"] for p in passages])

    gold = pd.read_csv(ROOT / "gold_final.csv", encoding="utf-8")
    gold["src"] = gold["claim_id"].astype(str).map(load_source_titles())
    ev = gold[gold["src"].isin(set(titles))].reset_index(drop=True)
    train_ids = set(pd.read_csv(ROOT / "gold_train_clean.csv")["claim_id"])
    is_train = ev["claim_id"].isin(train_ids).to_numpy()
    src = ev["src"].to_numpy()
    lang = ev["language"].to_numpy()
    print(f"evaluating {len(ev)} claims ({(lang == 'en').sum()} en, {(lang == 'hi').sum()} hi) "
          f"against {len(passages)} passages", flush=True)

    orders: dict[str, np.ndarray] = {}
    dense_scores: dict[str, np.ndarray] = {}
    for tag in args.encoders:
        print(f"dense:{tag} ...", flush=True)
        V = corpus_vectors(tag, texts)
        Q = encode(tag, ev["claim_text"].tolist(), passage=False)
        dense_scores[tag] = Q @ V.T
        orders[f"dense:{tag}"] = ranks_from_scores(dense_scores[tag])
    print("bm25 ...", flush=True)
    bm = BM25(texts)
    orders["bm25"] = ranks_from_scores(np.vstack([bm.scores(t) for t in ev["claim_text"]]))
    for tag in args.encoders:
        orders[f"hybrid:{tag}"] = rrf(orders[f"dense:{tag}"], orders["bm25"])

    ranks = {m: source_rank(o, titles, src) for m, o in orders.items()}
    base = "dense:xlmr" if "dense:xlmr" in ranks else next(iter(ranks))

    L = ["# Retrieval comparison — source-article recall (Phase 2)\n",
         f"{len(ev)} gold claims whose source article is in the experiment corpus "
         f"({(lang == 'en').sum()} EN, {(lang == 'hi').sum()} HI), {len(passages)} passages. "
         f"Recall@k = share of claims with a passage from their own source article in the "
         f"top k. Baseline = `{base}` (the current retrieval).\n",
         "**Decision rule (fixed before running):** a method replaces the baseline only if its "
         "recall@3 gain has a paired-bootstrap 95% CI entirely above 0.\n",
         "| Method | " + " | ".join(f"R@{k} all" for k in KS) + " | R@3 EN | R@3 HI | "
         "ΔR@3 vs baseline [95% CI] | adopt? |",
         "| --- | " + " | ".join("---" for _ in KS) + " | --- | --- | --- | --- |"]
    base_hit = ranks[base] <= 3
    for m, r in ranks.items():
        cells = [f"{(r <= k).mean():.3f}" for k in KS]
        en, hi = (r[lang == "en"] <= 3).mean(), (r[lang == "hi"] <= 3).mean()
        if m == base:
            delta, adopt = "—", "baseline"
        else:
            d, lo, hi_ = paired_diff_ci(base_hit, r <= 3)
            delta = f"{d:+.3f} [{lo:+.3f}, {hi_:+.3f}]"
            adopt = "**yes**" if lo > 0 else "no"
        L.append(f"| `{m}` | " + " | ".join(cells) + f" | {en:.3f} | {hi:.3f} | {delta} | {adopt} |")

    L += ["", "## By language and label (R@3)", "| Method | EN Verified | EN Hallucinated | HI Verified | HI Hallucinated |",
          "| --- | --- | --- | --- | --- |"]
    lab = ev["gold_verdict"].to_numpy()
    for m, r in ranks.items():
        cells = []
        for lg in ("en", "hi"):
            for lb in ("Verified", "Hallucinated"):
                mask = (lang == lg) & (lab == lb)
                cells.append(f"{(r[mask] <= 3).mean():.2f} (n={mask.sum()})")
        L.append(f"| `{m}` | " + " | ".join(cells) + " |")

    # Phase 2.2: relevance threshold, per dense encoder
    L += ["", "## Relevance threshold (Phase 2.2)",
          "`MIN_RELEVANCE_THRESHOLD` decides when retrieved evidence counts as \"no relevant "
          "evidence found\". For each claim: the best cosine of any passage from its **source "
          "article** (relevant) vs the best cosine of any passage from **another article** "
          "(irrelevant). The cut-off is fitted on the TRAIN split's claims by Youden's J and "
          "reported on TEST. Proxy caveat: another article can still be relevant, so the "
          "\"irrelevant\" rate is an upper bound on true false positives.\n"]
    for tag, S in dense_scores.items():
        same = titles[None, :] == src[:, None]
        best_rel = np.where(same, S, -np.inf).max(axis=1)
        best_irr = np.where(~same, S, -np.inf).max(axis=1)
        t_star, table = calibrate_threshold(best_rel, best_irr, is_train)
        L += [f"### dense:{tag} — fitted cut-off **{t_star:.2f}** (current {MIN_RELEVANCE_THRESHOLD})",
              "| cut-off | relevant kept (train) | irrelevant kept (train) | relevant kept (test) | irrelevant kept (test) |",
              "| --- | --- | --- | --- | --- |"]
        for t, v in table.items():
            L.append(f"| {t:.2f} | {v['train'][0]:.2f} | {v['train'][1]:.2f} | {v['test'][0]:.2f} | {v['test'][1]:.2f} |")
        L.append(f"\n- Median best cosine: relevant {np.median(best_rel):.3f}, irrelevant "
                 f"{np.median(best_irr):.3f} (train+test).\n")

    adopted = [m for m, r in ranks.items() if m != base
               and paired_diff_ci(base_hit, r <= 3)[1] > 0]
    n_src = int(gold["src"].notna().sum())
    L += ["## Conclusion and caveats",
          (f"- **Adopted by the decision rule:** {', '.join(f'`{m}`' for m in adopted)}."
           if adopted else
           f"- **No method beats the baseline** under the decision rule; `{base}` stays."),
          f"- The baseline already finds the source article in the top 3 for "
          f"{base_hit.mean():.1%} of claims and the top 10 for {(ranks[base] <= 10).mean():.1%}. "
          f"Article-level retrieval leaves little headroom; the weak detector results are not "
          f"mainly a retrieval failure at this level.",
          "- This is **article-level** recall: a passage from the right article is not necessarily "
          "the passage stating the fact, so it is an upper bound on evidence recall. Measuring the "
          "exact evidence passage would need passage-level relevance labels (human annotation).",
          f"- Claims whose source article is missing from the corpus are excluded "
          f"({n_src - len(ev)} of {n_src} claims with a recorded source) — a coverage gap, not a "
          f"ranking one (Phase 4).",
          "- Any variant chosen after seeing these numbers (e.g. hybrid for English only) would be "
          "fitted to this evaluation and is not adopted here.\n"]

    out = ROOT / "results" / "retrieval_comparison.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
