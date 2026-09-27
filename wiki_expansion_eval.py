"""
wiki_expansion_eval.py -- does on-demand Wikipedia expansion (member3_backend/
wiki_expander.py) improve evidence and verdicts?

Both conditions use the SAME path as the live system: the pipeline's XLM-R
embedder, a FAISS IVF index over the demo corpus (sqrt(N) clusters), top-3
passages above the relevance cut, the current NLI model (net score), 0.35/0.65
tiers. "baseline" retrieves from the demo corpus; "expanded" retrieves after
the expander has added the Wikipedia articles found by searching each claim's
text (claim text only: no labels, no annotators' evidence links).

DECISION RULE (fixed before running): expansion is switched on by default only if
the pooled EN+HI TRAIN ROC-AUC (expanded - baseline) has a paired-bootstrap 95%
CI entirely above 0. Test and round 3 are reported only.

    .venv/Scripts/python.exe wiki_expansion_eval.py        (GPU recommended)
Article text is cached in results/_wiki_cache/ (git-ignored); re-runs do not
download again. Writes results/wiki_expansion.md and results/wiki_expansion.csv.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from member1_model.embeddings import CrossLingualEmbedder
from member3_backend.faiss_retriever import FAISSRetriever
from member3_backend.pipeline import MIN_RELEVANCE_THRESHOLD, NLI_EVIDENCE_TOP_K
from member3_backend.wiki_expander import WikiExpander, indexed_titles_from_cache
from nli_model_search import claim_scores, load_sets, probs

ROOT = Path(__file__).resolve().parent
SET_ORDER = ("train", "test", "round3")
N_BOOT, SEED = 2000, 42
LOW, HIGH = 0.35, 0.65
BATCH = 20


def build_retriever() -> FAISSRetriever:
    passages = json.loads((ROOT / "corpus_passages_demo.json").read_text(encoding="utf-8"))
    vectors = np.load(ROOT / "corpus_vectors_demo.npy")
    r = FAISSRetriever(n_clusters=max(1, round(math.sqrt(len(passages)))))  # as api.py
    r.build_index([p["id"] for p in passages], [p["text"] for p in passages], vectors)
    return r


def evidence(retriever: FAISSRetriever, vecs: np.ndarray) -> list[list[tuple[str, str, float]]]:
    out = []
    for i, v in enumerate(vecs):
        res = retriever.retrieve(str(i), v, top_k=NLI_EVIDENCE_TOP_K)
        out.append([(p.passage_id, p.text, p.score) for p in res.passages if p.score >= MIN_RELEVANCE_THRESHOLD])
    return out


def nli_net(df: pd.DataFrame, ev) -> np.ndarray:
    texts = [[t for _, t, _ in e] for e in ev]
    prem = [p for e in texts for p in e]
    hyp = [c for c, e in zip(df.claim_text, texts) for _ in e]
    return claim_scores(texts, probs("mdeberta_base_xnli", prem, hyp))["net"]


def tier(s):
    return np.where(s < LOW, "Hallucinated", np.where(s > HIGH, "Verified", "Uncertain"))


def acc(gold, v) -> str:
    right, unc = int((v == gold).sum()), int((v == "Uncertain").sum())
    return (f"{right}/{len(gold)} ({right / len(gold):.0%}) · Uncertain {unc} · when it commits "
            f"{right}/{len(gold) - unc} ({right / max(len(gold) - unc, 1):.0%})")


def paired(y, a, b):
    rng = np.random.default_rng(SEED)
    d = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(y), len(y))
        if len(set(y[i])) == 2:
            d.append(roc_auc_score(y[i], b[i]) - roc_auc_score(y[i], a[i]))
    lo, hi = np.percentile(d, [2.5, 97.5])
    return roc_auc_score(y, b) - roc_auc_score(y, a), lo, hi


def build_evidence(sets: dict) -> tuple[dict, dict, dict, int, int]:
    """(baseline evidence, expanded evidence, totals, index size before, after).
    Shared with llm_verifier_eval.py so both evaluate the identical expanded index
    (same claim order and batches; articles come from the disk cache)."""
    embedder = CrossLingualEmbedder()
    retriever = build_retriever()
    n0 = len(retriever)
    vecs = {name: embedder.embed([f"{name}{i}" for i in range(len(df))], df.claim_text.tolist(),
                                 df.language.tolist()).vectors for name, df in sets.items()}
    base = {name: evidence(retriever, vecs[name]) for name in sets}

    expander = WikiExpander(embedder, retriever, ROOT / "results" / "_wiki_cache",
                            indexed=indexed_titles_from_cache(ROOT / "evidence_corpus_cache.json"))
    claims = [(c, l) for name in SET_ORDER for c, l in zip(sets[name].claim_text, sets[name].language)]
    totals = {"articles": 0, "passages": 0, "failures": 0}
    for k in range(0, len(claims), BATCH):
        st = expander.expand(claims[k:k + BATCH])
        totals["articles"] += st.articles_added
        totals["passages"] += st.passages_added
        totals["failures"] += st.failures
        print(f"expanded {min(k + BATCH, len(claims))}/{len(claims)} claims; +{totals['articles']} articles, "
              f"+{totals['passages']} passages, {totals['failures']} failed lookups", flush=True)
    exp = {name: evidence(retriever, vecs[name]) for name in sets}
    return base, exp, totals, n0, len(retriever)


def main() -> None:
    sets = load_sets()
    base, exp, totals, n0, n1 = build_evidence(sets)

    kg3 = pd.read_csv(ROOT / "round3" / "signals_round3_kgfix.csv").set_index("claim_id").kg_conf
    L = ["# Wikipedia index expansion (FR-03 incremental indexing)\n",
         f"Demo corpus {n0:,} passages → **{n1:,}** after expansion "
         f"(+{totals['articles']} Wikipedia articles, +{totals['passages']:,} passages; "
         f"{totals['failures']} failed lookups). Same embedder, index type, top-3 and relevance cut "
         f"({MIN_RELEVANCE_THRESHOLD}) in both conditions; NLI = current model (net). "
         "**Decision rule (fixed before running):** switch expansion on only if the pooled EN+HI "
         "TRAIN ΔAUC (expanded − baseline) has a 95% CI entirely above 0.\n"]
    rows, decision = [], None
    for name in SET_ORDER:
        df = sets[name]
        y = (df.gold_verdict == "Verified").astype(int).to_numpy()
        gold = df.gold_verdict.to_numpy()
        sb, se = nli_net(df, base[name]), nli_net(df, exp[name])
        cov_b = np.mean([len(e) > 0 for e in base[name]])
        cov_e = np.mean([len(e) > 0 for e in exp[name]])
        top_b = np.mean([e[0][2] if e else 0 for e in base[name]])
        top_e = np.mean([e[0][2] if e else 0 for e in exp[name]])
        from_new = np.mean([any(pid.startswith("wiki:") for pid, _, _ in e) for e in exp[name]])
        d, lo, hi = paired(y, sb, se)
        L += [f"## {name} (n = {len(df)}, Hallucinated {int((y == 0).sum())})", "",
              f"- Evidence: claims with a relevant passage {cov_b:.0%} → {cov_e:.0%}; mean top-1 "
              f"similarity {top_b:.3f} → {top_e:.3f}; claims whose top-3 includes a new article {from_new:.0%}.",
              f"- NLI AUC {roc_auc_score(y, sb):.3f} → {roc_auc_score(y, se):.3f} "
              f"(Δ {d:+.3f} [{lo:+.3f}, {hi:+.3f}]).",
              f"- Verdicts, baseline: {acc(gold, tier(sb))}",
              f"- Verdicts, expanded: {acc(gold, tier(se))}"]
        if name == "round3":
            kg = kg3.reindex(df.claim_id).to_numpy(dtype=float)
            has = ~np.isnan(kg)
            L += [f"- Live rule (KG decides, else NLI), baseline: {acc(gold, np.where(has, tier(np.nan_to_num(kg)), tier(sb)))}",
                  f"- Live rule (KG decides, else NLI), expanded: {acc(gold, np.where(has, tier(np.nan_to_num(kg)), tier(se)))}"]
        for lang in ("en", "hi"):
            m = (df.language == lang).to_numpy()
            if m.any() and len(set(y[m])) == 2:
                rows.append({"set": name, "lang": lang, "n": int(m.sum()), "n_hallu": int((y[m] == 0).sum()),
                             "auc_base": roc_auc_score(y[m], sb[m]), "auc_expanded": roc_auc_score(y[m], se[m]),
                             "coverage_base": float(np.mean([len(e) > 0 for e, k in zip(base[name], m) if k])),
                             "coverage_expanded": float(np.mean([len(e) > 0 for e, k in zip(exp[name], m) if k]))})
        if name == "train":
            decision = (d, lo, hi)
        L.append("")
    pd.DataFrame(rows).to_csv(ROOT / "results" / "wiki_expansion.csv", index=False)
    d, lo, hi = decision
    L += ["## Decision",
          (f"- **Switch on**: pooled train ΔAUC {d:+.3f} [{lo:+.3f}, {hi:+.3f}], CI above 0." if lo > 0 else
           f"- **Not switched on by default**: pooled train ΔAUC {d:+.3f} [{lo:+.3f}, {hi:+.3f}] does not "
           f"have a CI above 0. Expansion stays available (off by default).")]
    out = ROOT / "results" / "wiki_expansion.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
