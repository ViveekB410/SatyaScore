"""
evidence_rule_eval.py -- two candidate fixes to the evidence rule (found by a user test,
2026-10-05: "Humans can breathe naturally underwater" was Verified).

  gated          the live rule
  capped         Verified only when a passage SUPPORTS the claim (entailment >= 0.5); a weak
                 entailment with no on-topic contradiction scored up to 0.75 (0.72 here)
  capped_strong  capped, and support from an article not about the claim's subject must be
                 >= 0.9 ("Human can breath naturally underwater": Scuba diving passage, 0.79)

(Adapted from strict_support_eval.py, whose own history follows.)

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

DECISION RULE for THIS file (fixed 2026-10-05, committed before running): a candidate ("capped",
"capped_strong") becomes the live default only if ALL of (a)-(d) below hold for it, with FRESH = a NEW
sample (seed 17; seeds 7, 11, 13 were used before). If both qualify, the one with fewer train
hallucinations Verified wins; a tie goes to "capped" (the smaller change). The common-sense set
below is reported only (written while designing the fix).

(The rule as it read for "strict":) "strict" becomes the live default only if ALL hold:
  TRAIN  (a) gold-Hallucinated claims marked Verified: fewer;
         (b) true claims marked Hallucinated (false alarms): not more;
         (c) gold-Verified claims marked Verified: fall by at most 10% (relative);
  FRESH  (d) claims marked Verified: fall by at most 10% (relative), and false alarms not more.
Test and round 3 reported only.

    .venv/Scripts/python.exe evidence_rule_eval.py       -> results/evidence_rule_eval.md
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
FRESH_SEED = 17
CANDIDATES = ("capped", "capped_strong")
COMMON_SENSE = [  # (claim, true?) -- reported only
    ("Humans can breathe naturally underwater.", False), ("Human can breath naturally underwater.", False),
    ("Humans can breathe underwater without any equipment.", False), ("Fish breathe using gills.", True),
    ("The Sun revolves around the Earth.", False), ("The Earth revolves around the Sun.", True),
    ("Water boils at 100 degrees Celsius at sea level.", True), ("Humans have three lungs.", False),
    ("Humans have two lungs.", True), ("Penguins can fly long distances.", False),
    ("Snakes have legs.", False), ("Bats are mammals.", True), ("Spiders are insects.", False),
    ("The Moon produces its own light.", False), ("Plants make food by photosynthesis.", True)]
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
    sets["common sense"] = ([c for c, _ in COMMON_SENSE], ["en"] * len(COMMON_SENSE),
                            np.array(["Verified" if ok else "Hallucinated" for _, ok in COMMON_SENSE]))

    wiki = WikiExpander(api._embedder, api._retriever, ROOT / "results" / "_wiki_cache",
                        indexed=indexed_titles_from_cache(ROOT / "evidence_corpus_cache.json"))
    memo_search(wiki)
    every = [(c, l) for cl, lg, _ in sets.values() for c, l in zip(cl, lg)]
    for k in range(0, len(every), 25):
        wiki.expand(every[k:k + 25])
        print(f"wikipedia {min(k + 25, len(every))}/{len(every)}", flush=True)

    L = ["# Evidence rule: Verified only with a supporting passage (capped / capped_strong)\n",
         "**Decision rule (fixed before running):** a candidate is adopted only if on TRAIN (a) hallucinations marked "
         "Verified are fewer, (b) false alarms not more, (c) true claims marked Verified fall by at most 10%; and "
         f"on FRESH true Wikipedia sentences (seed {FRESH_SEED}, unseen) (d) claims marked Verified fall by at most "
         "10% and false alarms are not more. Both qualify: fewer train hallucinations Verified wins; tie: capped.\n"]
    res = {}
    for name, (cl, lg, gold) in sets.items():
        rows = rows_for(api, cl, lg)
        res[name] = {rule: stats(gold, tier(np.array([RULES[rule](r) for r in rows]))) for rule in ("gated", *CANDIDATES)}
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
    g, fg = res["train"]["gated"], res["fresh"]["gated"]
    L += ["## Decision", ""]
    passed = []
    for cand in CANDIDATES:
        s, fs = res["train"][cand], res["fresh"][cand]
        ok = {"a": s["hallu_ver"] < g["hallu_ver"], "b": s["fa"] <= g["fa"], "c": s["true_ver"] >= 0.9 * g["true_ver"],
              "d": fs["ver"] >= 0.9 * fg["ver"] and fs["fa"] <= fg["fa"]}
        L.append(f"- **{cand}**: (a) hallucinations Verified {g['hallu_ver']} -> {s['hallu_ver']}: "
                 f"{'met' if ok['a'] else 'NOT met'}; (b) false alarms {g['fa']} -> {s['fa']}: {'met' if ok['b'] else 'NOT met'}; "
                 f"(c) true claims Verified {g['true_ver']} -> {s['true_ver']}: {'met' if ok['c'] else 'NOT met'}; "
                 f"(d) fresh Verified {fg['ver']} -> {fs['ver']}, false alarms {fg['fa']} -> {fs['fa']}: "
                 f"{'met' if ok['d'] else 'NOT met'}.")
        if all(ok.values()):
            passed.append(cand)
    if passed:
        winner = min(passed, key=lambda c: (res["train"][c]["hallu_ver"], CANDIDATES.index(c)))
        L += ["", f"**Adopt \"{winner}\" (SATYASCORE_AGGREGATION={winner} by default).**"]
    else:
        L += ["", "**Do not adopt; the live rule stays \"gated\".**"]
    (ROOT / "results" / "evidence_rule_eval.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
