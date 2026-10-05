"""
official_sources_eval.py -- should the official sources be ON in the live app?

1. MedlinePlus as a second evidence source (member3_backend/medline_expander.py).
   On the annotated claims, the live evidence rule (gated NLI) with Wikipedia expansion, with
   and without MedlinePlus topics added to the index (the same comparison that adopted the
   Wikipedia expansion, unseen_eval.py).
   DECISION RULE (fixed 2026-10-04, committed before running): MedlinePlus becomes the default
   (SATYASCORE_MEDLINE=true) only if on TRAIN, versus without it:
     (a) true claims marked Hallucinated (false alarms): not more;
     (b) real hallucinations caught: not fewer;
     (c) correct verdicts: more.
   Test and round 3 reported only.

2. World Bank / WHO statistics (member2_data/official_stats.py).
   (i) every annotated claim (train, test, round 3): any statistic decision must be right;
   (ii) robustness across countries, labels by construction: for 40 countries drawn at random
   (seed 5) from the World Bank list, a TRUE claim states the official figure (rounded) and a
   FALSE claim states it x2 or /2, for population, life expectancy, literacy and GDP. This tests
   country identification and claim reading on countries the checks were not built on (the
   design cases used India and Japan).
   DECISION RULE (fixed 2026-10-04, committed before running): the statistics become the default
   (SATYASCORE_OFFICIAL_STATS=true) only if
     (a) annotated: no wrong decision;
     (b) robustness: no TRUE claim contradicted;
     (c) robustness: at least 80% of the FALSE claims that get an answer are contradicted.

    .venv/Scripts/python.exe official_sources_eval.py      -> results/official_sources_eval.md

ATTEMPT 2 for the statistics (fixed 2026-10-04, committed before running): attempt 1 (seed 5)
contradicted one TRUE claim, "The GDP of Tuvalu is about $0.1 billion" (0.066 billion rounded),
so rule (b) was not met. The check now also accepts a figure within the precision it is written
to. Attempt 2 uses 40 FRESH countries (--seed 6) and the SAME rules (a)-(c).
    .venv/Scripts/python.exe official_sources_eval.py --part stats --seed 6
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from aggregation_eval import rows_for, tier
from member3_backend.evidence_rules import RULES
from nli_model_search import load_sets

ROOT = Path(__file__).resolve().parent
SEED, N_COUNTRIES = 5, 40


def counts(gold, v) -> dict:
    return {"n": len(gold), "correct": int((v == gold).sum()),
            "fa": int(((gold == "Verified") & (v == "Hallucinated")).sum()),
            "caught": int(((gold == "Hallucinated") & (v == "Hallucinated")).sum()),
            "n_true": int((gold == "Verified").sum()), "n_hallu": int((gold == "Hallucinated").sum()),
            "unc": int((v == "Uncertain").sum())}


def medline_part(api, sets) -> tuple[list[str], bool]:
    from member3_backend.medline_expander import MedlineExpander
    from member3_backend.wiki_expander import WikiExpander, indexed_titles_from_cache
    wiki = WikiExpander(api._embedder, api._retriever, ROOT / "results" / "_wiki_cache",
                        indexed=indexed_titles_from_cache(ROOT / "evidence_corpus_cache.json"))
    claims = [(c, l) for df in sets.values() for c, l in zip(df.claim_text, df.language)]
    for k in range(0, len(claims), 25):
        wiki.expand(claims[k:k + 25])
        print(f"wikipedia {min(k + 25, len(claims))}/{len(claims)}", flush=True)
    base = {n: rows_for(api, df.claim_text.tolist(), df.language.tolist()) for n, df in sets.items()}
    med = MedlineExpander(api._embedder, api._retriever, ROOT / "results" / "_medline_cache", wiki=wiki)
    added = 0
    for k in range(0, len(claims), 25):
        added += med.expand(claims[k:k + 25]).articles_added
        print(f"medlineplus {min(k + 25, len(claims))}/{len(claims)} (+{added} topics)", flush=True)
    withm = {n: rows_for(api, df.claim_text.tolist(), df.language.tolist()) for n, df in sets.items()}
    L = [f"## 1. MedlinePlus as a second evidence source ({added} topics added)\n",
         "**Rule (fixed before running):** adopt only if on TRAIN, versus without it, false alarms are not "
         "more, hallucinations caught not fewer, and correct verdicts more.\n"]
    decision = False
    for name, df in sets.items():
        gold = df.gold_verdict.to_numpy()
        a = counts(gold, tier(np.array([RULES["gated"](r) for r in base[name]])))
        b = counts(gold, tier(np.array([RULES["gated"](r) for r in withm[name]])))
        L += [f"### {name} ({len(gold)} claims){' — decides' if name == 'train' else ' — reported only'}", "",
              "| | correct | false alarms | hallucinations caught | Uncertain |", "|---|---|---|---|---|"]
        for label, c in (("without MedlinePlus", a), ("with MedlinePlus", b)):
            L.append(f"| {label} | {c['correct']}/{c['n']} | {c['fa']}/{c['n_true']} | {c['caught']}/{c['n_hallu']} | {c['unc']} |")
        L.append("")
        if name == "train":
            ok = (b["fa"] <= a["fa"], b["caught"] >= a["caught"], b["correct"] > a["correct"])
            decision = all(ok)
            L.append(f"(a) {'met' if ok[0] else 'NOT met'}; (b) {'met' if ok[1] else 'NOT met'}; "
                     f"(c) {'met' if ok[2] else 'NOT met'}. "
                     + ("**Adopt MedlinePlus.**" if decision else "**Do not adopt MedlinePlus.**") + "\n")
    return L, decision


def stats_part(sets, seed: int = SEED) -> tuple[list[str], bool]:
    from member2_data import official_stats as st
    from member2_data.entity_linker import EntityLinker
    from member2_data.wikidata_connector import WikidataConnector
    el, wd, session = EntityLinker(), WikidataConnector(), requests.Session()
    wrong, decided = [], 0
    for df in sets.values():
        for r in df.itertuples(index=False):
            v = st.check(r.claim_text, r.language, el, wd, session)
            if v is not None and v.status != "unknown":
                decided += 1
                if (v.status == "supported") != (r.gold_verdict == "Verified"):
                    wrong.append(r.claim_text)
    # robustness: countries from the World Bank list (real countries, not aggregates)
    data = st._get_json(session, "https://api.worldbank.org/v2/country", {"format": "json", "per_page": 400})
    countries = sorted(c["name"] for c in data[1] if (c.get("region") or {}).get("id") not in ("NA", ""))
    rng = random.Random(seed)
    picked = rng.sample(countries, N_COUNTRIES)
    rows = []
    templates = {"population": ("{c} has a population of about {v:,.0f}.", 1),
                 "life": ("Life expectancy in {c} is {v:.0f} years.", 1),
                 "literacy": ("The literacy rate of {c} is {v:.0f}%.", 1),
                 "gdp": ("The GDP of {c} is about ${v:.1f} billion.", 1e9)}
    for c in picked:
        found = st.country_iso3(c, "en", el, wd)
        for kind, (tpl, scale) in templates.items():
            if found is None:
                rows.append({"country": c, "kind": kind, "gold": "-", "got": "country not found"})
                continue
            try:
                wb = st.world_bank(session, found[0], st.KINDS[kind][0])
            except Exception:  # lookup failed after retries: no figure to build the claims from
                wb = None
            if wb is None:
                continue
            value = wb[1]
            for gold, x in (("Verified", value), ("Hallucinated", value * rng.choice([2, 0.5]))):
                claim = tpl.format(c=c, v=x / scale)
                v = st.check(claim, "en", el, wd, session)
                got = "no answer" if v is None or v.status == "unknown" else (
                    "Verified" if v.status == "supported" else "Hallucinated")
                rows.append({"country": c, "kind": kind, "gold": gold, "got": got, "claim": claim})
    res = pd.DataFrame(rows)
    res.to_csv(ROOT / "results" / f"official_sources_eval_stats_seed{seed}.csv", index=False, encoding="utf-8")
    t, f = res[res.gold == "Verified"], res[res.gold == "Hallucinated"]
    t_contra = int((t.got == "Hallucinated").sum())
    f_ans = f[f.got.isin(["Verified", "Hallucinated"])]
    f_caught = int((f_ans.got == "Hallucinated").sum())
    not_found = sorted(set(res[res.got == "country not found"].country))
    ok = (not wrong, t_contra == 0, len(f_ans) > 0 and f_caught >= 0.8 * len(f_ans))
    L = [f"## 2. World Bank / WHO statistics (countries: seed {seed})\n",
         "**Rule (fixed before running):** adopt only if (a) no wrong decision on the annotated claims, (b) no TRUE "
         "robustness claim contradicted, (c) at least 80% of answered FALSE robustness claims contradicted.\n",
         f"- Annotated claims (train, test, round 3): {decided} decided by the statistics, {len(wrong)} wrong.",
         f"- Robustness, {N_COUNTRIES} random countries: TRUE claims {len(t)}, Verified {int((t.got == 'Verified').sum())}, "
         f"**contradicted {t_contra}**, no answer {int((t.got == 'no answer').sum())}; FALSE claims {len(f)}, "
         f"answered {len(f_ans)}, **contradicted {f_caught}**.",
         f"- Countries not identified on Wikidata by their World Bank name: {', '.join(not_found) or 'none'}.", "",
         f"(a) {'met' if ok[0] else 'NOT met'}; (b) {'met' if ok[1] else 'NOT met'}; (c) {'met' if ok[2] else 'NOT met'}. "
         + ("**Adopt the statistics.**" if all(ok) else "**Do not adopt the statistics.**")]
    if wrong:
        L += ["", "Wrong decisions:"] + [f"- {w}" for w in wrong]
    return L, all(ok)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["all", "stats", "medline"], default="all",
                    help="run one part (each writes its own section file); 'all' runs both")
    ap.add_argument("--seed", type=int, default=SEED, help="countries for the robustness check (attempt 2: 6)")
    args = ap.parse_args()
    part = args.part
    from member2_data import official_stats
    official_stats.CACHE_DIR = ROOT / "results" / "_stats_cache"
    official_stats.TIMEOUT_S, official_stats.ATTEMPTS = 30, 3  # the evaluation can wait for a slow API
    sets = load_sets()
    out = ROOT / "results"
    if part in ("all", "stats"):
        s, _ = stats_part(sets, args.seed)
        (out / f"official_sources_eval_stats_seed{args.seed}.md").write_text("\n".join(s) + "\n", encoding="utf-8")
        print("\n".join(s), flush=True)
    if part in ("all", "medline"):
        import member3_backend.api as api
        api.load_starter_corpus()
        api._warmup_models()
        m, _ = medline_part(api, sets)
        (out / "official_sources_eval_medline.md").write_text("\n".join(m) + "\n", encoding="utf-8")
        print("\n".join(m), flush=True)
    sections = [p.read_text(encoding="utf-8") for p in sorted(out.glob("official_sources_eval_stats_seed*.md"))
                + [out / "official_sources_eval_medline.md"] if p.exists()]
    (out / "official_sources_eval.md").write_text("# Official sources: MedlinePlus, World Bank, WHO\n\n"
                                                  + "\n".join(sections), encoding="utf-8")


if __name__ == "__main__":
    main()
