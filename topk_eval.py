"""
topk_eval.py -- on the 102,069-passage index (build_corpus_expanded.py), how many
passages should NLI read per claim, and how strict should the on-topic title
match be?

Found on the reported cricket example: with 11x more passages, the supporting
Cricket passage fell to rank 8 of the top-10 while the live system reads only the
top 3, and passages from "Comparison of baseball and cricket" counted as on-topic
through the last-word title shortcut.

Configurations (gated evidence rule; all through the live objects on the
expanded corpus):
  current    top-3 passages, loose title match   (the live system now)
  candidate  top-10 passages, strict title match
  (top-10 loose and top-3 strict are reported)

DECISION RULE (fixed 2026-09-28, committed before running). The candidate
becomes the live default only if, on TRAIN versus current:
  (a) true claims marked Hallucinated: not more;
  (b) real hallucinations caught: not fewer;
  (c) correct verdicts: more.
Test, round 3 and the fresh true Wikipedia sentences are reported only.

    .venv/Scripts/python.exe topk_eval.py        (GPU)
Writes results/topk_eval.md.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from aggregation_eval import sample_texts, tier
from member3_backend.evidence_rules import SubjectIndex, aggregate
from member3_backend.pipeline import MIN_RELEVANCE_THRESHOLD
from nli_model_search import load_sets
from unseen_eval import counts, table

ROOT = Path(__file__).resolve().parent
TOP_MAX = 10
CONFIGS = {"current (top-3, loose)": (3, False), "candidate (top-10, strict)": (10, True),
           "top-10, loose": (10, False), "top-3, strict": (3, True)}


def passages_for(api, claims: list[str], langs: list[str]):
    """Per claim: [(e, c, passage_id)] for the top-10 passages above the relevance cut."""
    vecs = api._embedder.embed([str(i) for i in range(len(claims))], claims, langs).vectors
    out = []
    for claim, v in zip(claims, vecs):
        ps = [p for p in api._retriever.retrieve("q", v, top_k=TOP_MAX).passages if p.score >= MIN_RELEVANCE_THRESHOLD]
        res = api._nli_scorer.score_batch(["q"] * len(ps), [p.text for p in ps], [claim] * len(ps)) if ps else []
        out.append([(r.entailment_prob, r.contradiction_prob, p.passage_id) for p, r in zip(ps, res)])
    return out


def main() -> None:
    import member3_backend.api as api
    api.load_starter_corpus()
    api._warmup_models()
    subjects = {s: SubjectIndex.from_cache(ROOT / "evidence_corpus_cache.json", strict=s) for s in (False, True)}

    sets = load_sets()
    design = {it["text"] for it in sample_texts(7)}
    fresh_claims, fresh_langs = [], []
    for it in sample_texts(11):
        if it["text"] not in design:
            for c in api._pipeline.claim_extractor.extract(it["text"], it["lang"]):
                fresh_claims.append(c.text)
                fresh_langs.append(it["lang"])
    evalsets = [("Wikipedia sentences, fresh (seed 11)", fresh_claims, fresh_langs,
                 np.array(["Verified"] * len(fresh_claims)), None)]
    for name in ("train", "test", "round3"):
        df = sets[name]
        evalsets.append((name, df.claim_text.tolist(), df.language.tolist(), df.gold_verdict.to_numpy(),
                         df.claim_id.tolist()))

    kg3 = pd.read_csv(ROOT / "round3" / "signals_round3_kgfix.csv").set_index("claim_id").kg_conf
    L = ["# Passages per claim and title strictness (102,069-passage index)\n",
         f"Index: {len(api._retriever):,} passages. Gated evidence rule throughout. **Decision rule (fixed before "
         "running):** the candidate (top-10, strict) replaces the current live setup (top-3, loose) only if on "
         "TRAIN (a) false alarms are not more, (b) real hallucinations caught are not fewer, (c) correct "
         "verdicts are more.\n"]
    decision = None
    for name, claims, langs, gold, ids in evalsets:
        found = passages_for(api, claims, langs)
        verdicts = {}
        for cfg, (k, strict) in CONFIGS.items():
            s = np.array([aggregate([(e, c, subjects[strict].on_topic(cl, pid)) for e, c, pid in rows[:k]])
                          for cl, rows in zip(claims, found)])
            v = tier(s)
            if name == "round3":
                kg = kg3.reindex(ids).to_numpy(dtype=float)
                has = ~np.isnan(kg)
                v = np.where(has, tier(np.nan_to_num(kg)), v)
            verdicts[cfg] = v
        res = {cfg: counts(gold, v) for cfg, v in verdicts.items()}
        L += [f"## {name} ({len(claims)} claims)" + (" — decides" if name == "train" else " — reported only"), ""]
        L += table(res) + [""]
        if name == "train":
            cur, cand = res["current (top-3, loose)"], res["candidate (top-10, strict)"]
            decision = {"a": cand["false_alarms"] <= cur["false_alarms"], "b": cand["caught"] >= cur["caught"],
                        "c": cand["correct"] > cur["correct"]}
    ok = all(decision.values())
    L += ["## Decision",
          f"- (a) false alarms not more: **{'yes' if decision['a'] else 'no'}**",
          f"- (b) real hallucinations caught not fewer: **{'yes' if decision['b'] else 'no'}**",
          f"- (c) more correct verdicts: **{'yes' if decision['c'] else 'no'}**",
          f"- **{'Adopt top-10 passages with strict title matching.' if ok else 'Keep the current setup.'}**"]
    out = ROOT / "results" / "topk_eval.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
