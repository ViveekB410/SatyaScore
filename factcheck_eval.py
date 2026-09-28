"""
factcheck_eval.py -- should professional fact-checks (Google Fact Check Tools API,
member2_data/factcheck.py + member3_backend/factcheck_rules.py) be ON in the live app?

Sets:
  rumours   factcheck_eval/rumours.csv: 25 widely fact-checked rumours (EN 15, HI 10),
            written by us in our own words, and 15 TRUE counterparts, 8 of them the
            exact negations of rumours (the dangerous case: a fact-check of "X" rated
            False must never mark "not X" Hallucinated). Labels: basis column.
  train / test / round3   the annotated gold claims (from real chatbot answers):
            fact-checks rarely exist for them; any decision made there must be right.

DECISION RULE (fixed 2026-09-28, committed before the first run). Fact-checks become
the live default (SATYASCORE_FACTCHECK=true) only if
  (a) NO wrong decision: across all four sets, no fact-check turns a gold-Verified
      claim Hallucinated or a gold-Hallucinated claim Verified; and
  (b) on the rumours set, fact-checks correct at least 5 verdicts the pipeline alone
      got wrong (i.e. they add something).
Coverage (how many claims a fact-check decided) is reported only.

Needs GOOGLE_FACTCHECK_KEY in YOUR shell (never pasted anywhere, never printed):
    $env:GOOGLE_FACTCHECK_KEY = "..."      (PowerShell)
    .venv/Scripts/python.exe factcheck_eval.py
~15 min (the pipeline runs on the 40 rumour-set claims; ~650 API lookups, cached in
results/_factcheck_cache). Writes results/factcheck_eval.md and .csv.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

from member2_data.factcheck import FactChecker
from member3_backend.factcheck_rules import decide, match
from nli_model_search import load_sets

ROOT = Path(__file__).resolve().parent
MIN_CORRECTED = 5


def pipeline_verdict(pipe, text: str, lang: str) -> str:
    r = pipe.run(text, lang)
    return r.scores[0].verdict.value if len(r.scores) == 1 else r.document.document_verdict.value


def main() -> None:
    if not FactChecker.available():
        sys.exit("GOOGLE_FACTCHECK_KEY is not set in this shell. Set it (do not paste it anywhere else) and rerun.")
    import member3_backend.api as api
    api.load_starter_corpus()
    api._warmup_models()
    pipe = api._pipeline
    pipe.fact_checker = None  # the baseline verdicts are the pipeline ALONE
    checker = FactChecker(cache_dir=ROOT / "results" / "_factcheck_cache")

    sets = {"rumours": pd.read_csv(ROOT / "factcheck_eval" / "rumours.csv", encoding="utf-8")}
    sets.update(load_sets())
    rows = []
    for name, df in sets.items():
        for k, r in enumerate(df.itertuples(index=False)):
            checks = checker.search(r.claim_text, r.language)
            time.sleep(0.1)
            m = decide(match(r.claim_text, r.language, checks, api._embedder, api._nli_scorer))
            fc_verdict = None if m is None else ("Hallucinated" if m.check.verdict == "false" else "Verified")
            # the pipeline's own verdict: all of the rumours set; elsewhere only where a fact-check decided
            base = pipeline_verdict(pipe, r.claim_text, r.language) if (name == "rumours" or m) else None
            rows.append({"set": name, "claim_id": r.claim_id, "language": r.language, "claim_text": r.claim_text,
                         "gold": r.gold_verdict, "pipeline": base, "n_factchecks_found": len(checks),
                         "factcheck": fc_verdict, "publisher": m.check.publisher if m else "",
                         "rating": m.check.rating if m else "", "checked_claim": m.check.claim_text if m else "",
                         "url": m.check.url if m else ""})
            if (k + 1) % 50 == 0:
                print(f"{name}: {k + 1}/{len(df)}", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(ROOT / "results" / "factcheck_eval.csv", index=False, encoding="utf-8")

    dec = res[res.factcheck.notna()]
    wrong = dec[dec.factcheck != dec.gold]
    rum = res[res.set == "rumours"]
    final = rum.factcheck.fillna(rum.pipeline)
    corrected = int(((rum.pipeline != rum.gold) & (final == rum.gold)).sum())
    a, b = len(wrong) == 0, corrected >= MIN_CORRECTED

    L = ["# Professional fact-checks (Google Fact Check Tools API)\n",
         "**Decision rule (fixed before running):** fact-checks become the live default only if (a) no "
         "fact-check decision is wrong on any set and (b) on the rumours set they correct at least "
         f"{MIN_CORRECTED} verdicts the pipeline alone got wrong.\n",
         "| set | claims | a fact-check was found | a fact-check decided | decisions right | decisions wrong |",
         "|---|---|---|---|---|---|"]
    for name in sets:
        s = res[res.set == name]
        d = s[s.factcheck.notna()]
        L.append(f"| {name} | {len(s)} | {int((s.n_factchecks_found > 0).sum())} | {len(d)} | "
                 f"{int((d.factcheck == d.gold).sum())} | **{int((d.factcheck != d.gold).sum())}** |")
    L += ["", "## Rumours set: verdicts", "",
          "| | correct | rumours caught (Hallucinated) | true claims marked Hallucinated |", "|---|---|---|---|"]
    for label, v in (("pipeline alone", rum.pipeline), ("pipeline + fact-checks", final)):
        L.append(f"| {label} | {int((v == rum.gold).sum())}/{len(rum)} | "
                 f"{int(((rum.gold == 'Hallucinated') & (v == 'Hallucinated')).sum())}/{int((rum.gold == 'Hallucinated').sum())} | "
                 f"{int(((rum.gold == 'Verified') & (v == 'Hallucinated')).sum())}/{int((rum.gold == 'Verified').sum())} |")
    L += ["", f"Verdicts corrected by a fact-check: **{corrected}**.", "",
          f"**Decision:** (a) no wrong decision: {'met' if a else 'NOT met'} ({len(wrong)} wrong); "
          f"(b) at least {MIN_CORRECTED} corrected: {'met' if b else 'NOT met'} ({corrected}). "
          + ("**Adopt: set SATYASCORE_FACTCHECK=true as the default.**" if a and b else
             "**Do not adopt; fact-checks stay off by default.**"), "",
          "## Every fact-check decision", "", "| set | claim | gold | fact-check | publisher: rating | checked claim |",
          "|---|---|---|---|---|---|"]
    for r in dec.itertuples():
        L.append(f"| {r.set} | {r.claim_text} | {r.gold} | {r.factcheck} | [{r.publisher}: {r.rating}]({r.url}) | "
                 f"{r.checked_claim} |")
    (ROOT / "results" / "factcheck_eval.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:20]))


if __name__ == "__main__":
    main()
