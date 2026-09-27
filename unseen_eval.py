"""
unseen_eval.py -- does on-demand Wikipedia expansion, on top of the gated
evidence rule, give CORRECT verdicts on data the index has not seen?

Configurations, all through the live objects (member3_backend.api):
  gated              the live default (fixed 245-article index)
  gated + expansion  the index grows with the Wikipedia articles found by
                     searching each claim (member3_backend/wiki_expander.py)
  legacy             the old rule (reference)

DECISION RULE (fixed 2026-09-28, committed before running). Expansion becomes the
live default only if, on the TRAIN split (claims from real chatbot answers, not
copied from Wikipedia), compared with gated alone:
  (a) true claims marked Hallucinated (false alarms): not more;
  (b) real hallucinations caught: not fewer;
  (c) correct verdicts: more.
Test, round 3 and the Wikipedia lead sentences (seed 11 fresh, seed 7 design;
verbatim Wikipedia, so retrieval can find them word for word: flattering) are
reported only.

    .venv/Scripts/python.exe unseen_eval.py        (GPU; ~15 min, mostly Wikipedia search)
Writes results/unseen_eval.md; train scores of the adopted configuration go to
results/_unseen_train_scores.csv for the calibration refit (build_calibration_live.py).
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from aggregation_eval import rows_for, sample_texts, tier
from member3_backend.evidence_rules import RULES
from member3_backend.wiki_expander import WikiExpander, indexed_titles_from_cache
from nli_model_search import load_sets

ROOT = Path(__file__).resolve().parent
BATCH = 20
CONFIGS = ("legacy", "gated", "gated + expansion")


def counts(gold: np.ndarray, v: np.ndarray) -> dict:
    return {"n": len(gold), "correct": int((v == gold).sum()),
            "false_alarms": int(((gold == "Verified") & (v == "Hallucinated")).sum()),
            "true_verified": int(((gold == "Verified") & (v == "Verified")).sum()),
            "caught": int(((gold == "Hallucinated") & (v == "Hallucinated")).sum()),
            "n_true": int((gold == "Verified").sum()), "n_hallu": int((gold == "Hallucinated").sum()),
            "uncertain": int((v == "Uncertain").sum())}


def table(res: dict) -> list[str]:
    L = ["| configuration | correct | true claims Verified | **true claims marked Hallucinated** | "
         "real hallucinations caught | Uncertain |", "|---|---|---|---|---|---|"]
    for cfg, c in res.items():
        hal = f"{c['caught']}/{c['n_hallu']}" if c["n_hallu"] else "—"
        L.append(f"| {cfg} | {c['correct']}/{c['n']} ({c['correct'] / c['n']:.0%}) | "
                 f"{c['true_verified']}/{c['n_true']} | **{c['false_alarms']}/{c['n_true']}** "
                 f"({c['false_alarms'] / max(c['n_true'], 1):.0%}) | {hal} | {c['uncertain']} |")
    return L


def main() -> None:
    import member3_backend.api as api
    api.load_starter_corpus()
    api._warmup_models()
    pipe = api._pipeline

    # every evaluation set as (name, claims, langs, gold, claim_ids)
    sets = load_sets()
    evalsets = []
    design_texts = {it["text"] for it in sample_texts(7)}
    for seed, name, exclude in ((11, "Wikipedia sentences, fresh (seed 11)", design_texts),
                                (7, "Wikipedia sentences, design sample (seed 7)", set())):
        claims, langs = [], []
        for it in sample_texts(seed):
            if it["text"] in exclude:
                continue
            for c in pipe.claim_extractor.extract(it["text"], it["lang"]):
                claims.append(c.text)
                langs.append(it["lang"])
        evalsets.append((name, claims, langs, np.array(["Verified"] * len(claims)), None))
    for name in ("train", "test", "round3"):
        df = sets[name]
        evalsets.append((name, df.claim_text.tolist(), df.language.tolist(), df.gold_verdict.to_numpy(),
                         df.claim_id.tolist()))

    base = {name: rows_for(api, cl, lg) for name, cl, lg, _, _ in evalsets}
    expander = WikiExpander(api._embedder, api._retriever, ROOT / "results" / "_wiki_cache",
                            indexed=indexed_titles_from_cache(ROOT / "evidence_corpus_cache.json"))
    all_claims = [(c, l) for _, cl, lg, _, _ in evalsets for c, l in zip(cl, lg)]
    added = 0
    for k in range(0, len(all_claims), BATCH):
        added += expander.expand(all_claims[k:k + BATCH]).articles_added
        print(f"expanded {min(k + BATCH, len(all_claims))}/{len(all_claims)} claims (+{added} articles)", flush=True)
    exp = {name: rows_for(api, cl, lg) for name, cl, lg, _, _ in evalsets}

    kg3 = pd.read_csv(ROOT / "round3" / "signals_round3_kgfix.csv").set_index("claim_id").kg_conf
    L = ["# Unseen data: gated rule, with and without Wikipedia expansion\n",
         f"Live objects; the expanded index gained {added} articles (index {len(api._retriever):,} passages). "
         "**Decision rule (fixed before running):** expansion becomes the default only if on TRAIN, versus "
         "gated alone, (a) false alarms are not more, (b) real hallucinations caught are not fewer, and "
         "(c) correct verdicts are more.\n"]
    decision = None
    for name, cl, lg, gold, ids in evalsets:
        scores = {"legacy": [RULES["legacy"](r) for r in base[name]],
                  "gated": [RULES["gated"](r) for r in base[name]],
                  "gated + expansion": [RULES["gated"](r) for r in exp[name]]}
        verdicts = {c: tier(np.array(s)) for c, s in scores.items()}
        if name == "round3":  # the live rule: the KG decides when it answers
            kg = kg3.reindex(ids).to_numpy(dtype=float)
            has = ~np.isnan(kg)
            verdicts = {c: np.where(has, tier(np.nan_to_num(kg)), v) for c, v in verdicts.items()}
        res = {c: counts(gold, verdicts[c]) for c in CONFIGS}
        tag = " — decides" if name == "train" else " — reported only"
        L += [f"## {name} ({len(cl)} claims){tag}", ""] + table(res) + [""]
        if name == "train":
            g, e = res["gated"], res["gated + expansion"]
            decision = {"a": e["false_alarms"] <= g["false_alarms"], "b": e["caught"] >= g["caught"],
                        "c": e["correct"] > g["correct"]}
            pd.DataFrame({"claim_id": ids, "language": lg, "gold_verdict": gold,
                          "score_gated": scores["gated"], "score_expanded": scores["gated + expansion"]}
                         ).to_csv(ROOT / "results" / "_unseen_train_scores.csv", index=False)
    ok = all(decision.values())
    L += ["## Decision",
          f"- (a) false alarms not more: **{'yes' if decision['a'] else 'no'}**",
          f"- (b) real hallucinations caught not fewer: **{'yes' if decision['b'] else 'no'}**",
          f"- (c) more correct verdicts: **{'yes' if decision['c'] else 'no'}**",
          f"- **{'Switch expansion on by default.' if ok else 'Keep expansion off by default.'}**"]
    out = ROOT / "results" / "unseen_eval.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
