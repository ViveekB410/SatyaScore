"""
build_calibration_live.py -- FR-04 confidence interval, refitted on the scores the
LIVE pipeline actually produces (member1_model/calibration.py).

The previous tables (build_calibration.py) were fitted on evaluation signals (NLI
on the top-1 passage) and the old "most decisive passage" rule; the live API now
uses the gated evidence rule (member3_backend/evidence_rules.py), so its P(Verified)
readings were off-scale. This recomputes every train/test claim through the live
objects (retrieval, NLI, evidence rule; optionally Wikipedia expansion), fits
equal-count bins on TRAIN only and checks them on test.

    .venv/Scripts/python.exe build_calibration_live.py [--aggregation gated] [--expansion]
Writes calibration_en.json, calibration_hi.json and results/calibration.md.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import numpy as np

from aggregation_eval import rows_for
from member1_model.calibration import fit_bins, lookup
from member3_backend.evidence_rules import RULES
from member3_backend.wiki_expander import WikiExpander, indexed_titles_from_cache
from nli_model_search import load_sets

ROOT = Path(__file__).resolve().parent
BATCH = 20


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aggregation", choices=list(RULES), default="gated")
    ap.add_argument("--expansion", action="store_true", help="expand the index as the live API does")
    args = ap.parse_args()

    import member3_backend.api as api
    api.load_starter_corpus()
    api._warmup_models()
    sets = load_sets()
    train, test = sets["train"], sets["test"]
    if args.expansion:
        ex = WikiExpander(api._embedder, api._retriever, ROOT / "results" / "_wiki_cache",
                          indexed=indexed_titles_from_cache(ROOT / "evidence_corpus_cache.json"))
        claims = [(c, l) for df in (train, test) for c, l in zip(df.claim_text, df.language)]
        for k in range(0, len(claims), BATCH):
            ex.expand(claims[k:k + BATCH])
    rule = RULES[args.aggregation]
    for df in (train, test):
        df["score"] = [rule(r) for r in rows_for(api, df.claim_text.tolist(), df.language.tolist())]

    config = f"live pipeline: aggregation={args.aggregation}, expansion={'on' if args.expansion else 'off'}"
    L = ["# Calibration — FR-04 confidence interval (live scores)\n",
         f"Scores from the {config} (retrieval, NLI, evidence rule exactly as the API). Each HalluScore "
         "is reported with **P(Verified)** and a **95% Wilson interval**: the share of TRAIN claims in the "
         "same score bin (equal-count bins) that were Verified; checked on the grouped test split.\n"]
    for lang in ("en", "hi"):
        tr, te = train[train.language == lang], test[test.language == lang]
        table = fit_bins(tr.score.to_numpy(), (tr.gold_verdict == "Verified").to_numpy())
        table.update({"language": lang, "fitted_on": "gold_train_clean.csv", "scores": config})
        (ROOT / f"calibration_{lang}.json").write_text(json.dumps(table, indent=2), encoding="utf-8")

        y = (te.gold_verdict == "Verified").to_numpy().astype(float)
        p = np.array([lookup(s, table).p_verified for s in te.score])
        base = float((tr.gold_verdict == "Verified").mean())
        brier, brier_base = float(np.mean((p - y) ** 2)), float(np.mean((base - y) ** 2))
        edges = [-np.inf] + table["edges"] + [np.inf]
        L += [f"## {lang.upper()} — train n = {len(tr)}, test n = {len(te)}",
              "| score bin | train n | P(Verified) [95% CI] | test n | test Verified rate | inside CI? |",
              "| --- | --- | --- | --- | --- | --- |"]
        inside = 0
        for b, (lo_e, hi_e) in enumerate(zip(edges[:-1], edges[1:])):
            bt = table["bins"][b]
            m = (te.score >= lo_e) & (te.score < hi_e)
            n_te = int(m.sum())
            rate = float((te[m].gold_verdict == "Verified").mean()) if n_te else None
            ok = rate is not None and bt["ci95"][0] <= rate <= bt["ci95"][1]
            inside += ok
            p_txt = "n/a" if bt["p_verified"] is None else f"{bt['p_verified']:.2f}"
            L.append(f"| [{'−∞' if lo_e == -np.inf else f'{lo_e:.3f}'}, {'∞' if hi_e == np.inf else f'{hi_e:.3f}'}) "
                     f"| {bt['n']} | {p_txt} [{bt['ci95'][0]:.2f}, {bt['ci95'][1]:.2f}] | {n_te} | "
                     f"{'n/a' if rate is None else f'{rate:.2f}'} | {'yes' if ok else 'no'} |")
        L += ["", f"- Test Brier score **{brier:.3f}** vs **{brier_base:.3f}** for always predicting the train "
              f"Verified rate ({base:.2f}): " + ("the score adds calibrated information." if brier < brier_base else
                                                 "**the score adds no calibrated information over the base rate**; "
                                                 "the overlapping intervals say so honestly."),
              f"- {inside} of {len(table['bins'])} test bin rates fall inside their train 95% CI.\n"]
    out = ROOT / "results" / "calibration.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
