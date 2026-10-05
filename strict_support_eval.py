"""
strict_support_eval.py -- should only on-topic passages be allowed to VERIFY a claim?

"gated" (live): support from any passage; only on-topic passages may contradict.
"strict":       support must come from an on-topic passage too (evidence_rules.aggregate_strict).

Why: results/missed_hallucinations_analysis.md -- 8 of 14 genuine hallucinations in train were
Verified by loosely related passages. The cost to watch: true claims supported only by a
passage whose article title is not in the claim lose Verified.

Data, all through the live objects with Wikipedia expansion (as the live system):
  train / test / round 3   the annotated claims (train decides);
  fresh                     lead sentences of Wikipedia articles, TRUE by construction, English
                            and Hindi, seed 13 (seeds 7 and 11 were used before; 13 is unseen).

DECISION RULE (fixed 2026-10-05, committed before running). "strict" becomes the live default
only if ALL hold:
  TRAIN  (a) gold-Hallucinated claims marked Verified: fewer;
         (b) true claims marked Hallucinated (false alarms): not more;
         (c) gold-Verified claims marked Verified: fall by at most 10% (relative);
  FRESH  (d) claims marked Verified: fall by at most 10% (relative), and false alarms not more.
Test and round 3 reported only.

    .venv/Scripts/python.exe strict_support_eval.py      -> results/strict_support_eval.md
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from aggregation_eval import rows_for, sample_texts, tier
from member3_backend.evidence_rules import RULES
from nli_model_search import load_sets

ROOT = Path(__file__).resolve().parent
FRESH_SEED = 13
SEARCH_CACHE = ROOT / "results" / "_wiki_search_cache"


def memo_search(expander):
    """Remember Wikipedia search results on disk, so a rerun repeats the same evidence and
    does not re-query (evaluation only; the live expander is unchanged)."""
    original = expander.search

    def search(text, lang):
        f = SEARCH_CACHE / (hashlib.sha1(f"{lang}|{text}".encode("utf-8")).hexdigest()[:20] + ".json")
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        out = original(text, lang)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return out
    expander.search = search


def stats(gold, v) -> dict:
    return {"n": len(gold), "correct": int((v == gold).sum()),
            "true_ver": int(((gold == "Verified") & (v == "Verified")).sum()),
            "hallu_ver": int(((gold == "Hallucinated") & (v == "Verified")).sum()),
            "fa": int(((gold == "Verified") & (v == "Hallucinated")).sum()),
            "caught": int(((gold == "Hallucinated") & (v == "Hallucinated")).sum()),
            "unc": int((v == "Uncertain").sum()), "ver": int((v == "Verified").sum()),
            "n_true": int((gold == "Verified").sum()), "n_hallu": int((gold == "Hallucinated").sum())}


def main() -> None:
    import member3_backend.api as api
    from member3_backend.wiki_expander import WikiExpander, indexed_titles_from_cache
    api.load_starter_corpus()
    api._warmup_models()
    sets = {n: (df.claim_text.tolist(), df.language.tolist(), df.gold_verdict.to_numpy())
            for n, df in load_sets().items()}
    claims, langs = [], []
    for it in sample_texts(FRESH_SEED):
        for c in api._pipeline.claim_extractor.extract(it["text"], it["lang"]):
            claims.append(c.text)
            langs.append(it["lang"])
    sets["fresh"] = (claims, langs, np.array(["Verified"] * len(claims)))

    wiki = WikiExpander(api._embedder, api._retriever, ROOT / "results" / "_wiki_cache",
                        indexed=indexed_titles_from_cache(ROOT / "evidence_corpus_cache.json"))
    memo_search(wiki)
    every = [(c, l) for cl, lg, _ in sets.values() for c, l in zip(cl, lg)]
    for k in range(0, len(every), 25):
        wiki.expand(every[k:k + 25])
        print(f"wikipedia {min(k + 25, len(every))}/{len(every)}", flush=True)

    L = ["# Strict support: only on-topic passages may verify a claim\n",
         "**Decision rule (fixed before running):** adopt \"strict\" only if on TRAIN (a) hallucinations marked "
         "Verified are fewer, (b) false alarms not more, (c) true claims marked Verified fall by at most 10%; and "
         f"on FRESH true Wikipedia sentences (seed {FRESH_SEED}) (d) claims marked Verified fall by at most 10% and "
         "false alarms are not more.\n"]
    res = {}
    for name, (cl, lg, gold) in sets.items():
        rows = rows_for(api, cl, lg)
        res[name] = {rule: stats(gold, tier(np.array([RULES[rule](r) for r in rows]))) for rule in ("gated", "strict")}
        L += [f"## {name} ({len(cl)} claims){' — decides' if name in ('train', 'fresh') else ' — reported only'}", "",
              "| rule | correct | true claims Verified | **hallucinations Verified** | false alarms | caught | Uncertain |",
              "|---|---|---|---|---|---|---|"]
        for rule, s in res[name].items():
            hv = f"{s['hallu_ver']}/{s['n_hallu']}" if s["n_hallu"] else "—"
            cg = f"{s['caught']}/{s['n_hallu']}" if s["n_hallu"] else "—"
            L.append(f"| {rule} | {s['correct']}/{s['n']} | {s['true_ver']}/{s['n_true']} | **{hv}** | "
                     f"{s['fa']}/{s['n_true']} | {cg} | {s['unc']} |")
        L.append("")
        print(f"scored {name}", flush=True)
    g, s = res["train"]["gated"], res["train"]["strict"]
    fg, fs = res["fresh"]["gated"], res["fresh"]["strict"]
    ok = {"a": s["hallu_ver"] < g["hallu_ver"], "b": s["fa"] <= g["fa"], "c": s["true_ver"] >= 0.9 * g["true_ver"],
          "d": fs["ver"] >= 0.9 * fg["ver"] and fs["fa"] <= fg["fa"]}
    L += ["## Decision", "",
          f"(a) hallucinations Verified {g['hallu_ver']} -> {s['hallu_ver']}: {'met' if ok['a'] else 'NOT met'}; "
          f"(b) false alarms {g['fa']} -> {s['fa']}: {'met' if ok['b'] else 'NOT met'}; "
          f"(c) true claims Verified {g['true_ver']} -> {s['true_ver']}: {'met' if ok['c'] else 'NOT met'}; "
          f"(d) fresh Verified {fg['ver']} -> {fs['ver']}, false alarms {fg['fa']} -> {fs['fa']}: "
          f"{'met' if ok['d'] else 'NOT met'}.", "",
          "**Adopt \"strict\" (SATYASCORE_AGGREGATION=strict by default).**" if all(ok.values())
          else "**Do not adopt; the live rule stays \"gated\".**"]
    (ROOT / "results" / "strict_support_eval.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
