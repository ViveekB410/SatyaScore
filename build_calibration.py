"""
build_calibration.py -- FR-04 confidence interval (member1_model/calibration.py).

Fits per-language calibration tables on gold_train_clean.csv (fused score with
the shipped weights -> P(Verified) with a 95% Wilson CI per score bin) and
writes calibration_<lang>.json. Checks them on gold_test_clean.csv:
  - Brier score vs a constant (train Verified rate) -- does the score add anything?
  - per bin, does the test Verified rate fall inside the train CI?
Writes results/calibration.md.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np

from honest_eval import add_fused, load_split, load_weights
from member1_model.calibration import fit_bins, lookup

ROOT = Path(__file__).resolve().parent


def main() -> None:
    train = load_split(ROOT / "gold_train_clean.csv")
    test = load_split(ROOT / "gold_test_clean.csv")
    weights = {lang: load_weights(lang, ROOT) for lang in ("en", "hi")}
    train, test = add_fused(train, weights), add_fused(test, weights)

    L = ["# Calibration — FR-04 confidence interval\n",
         "Each HalluScore is reported with **P(Verified)** and a **95% Wilson interval**: the share "
         "of training claims in the same score bin (equal-count bins) that were Verified. Fitted "
         "on the train split only, checked on the grouped test split.\n"]
    for lang in ("en", "hi"):
        tr = train[(train.language == lang) & train.fused.notna()]
        te = test[(test.language == lang) & test.fused.notna()]
        table = fit_bins(tr.fused.to_numpy(), (tr.gold_verdict == "Verified").to_numpy())
        table.update({"language": lang, "fitted_on": "gold_train_clean.csv",
                      "weights": {k: weights[lang][k] for k in ("alpha", "beta", "gamma")}})
        (ROOT / f"calibration_{lang}.json").write_text(json.dumps(table, indent=2), encoding="utf-8")

        y_te = (te.gold_verdict == "Verified").to_numpy().astype(float)
        p_te = np.array([lookup(s, table).p_verified for s in te.fused])
        base = float((tr.gold_verdict == "Verified").mean())
        brier, brier_base = float(np.mean((p_te - y_te) ** 2)), float(np.mean((base - y_te) ** 2))

        edges = [-np.inf] + table["edges"] + [np.inf]
        L += [f"## {lang.upper()} — train n = {len(tr)}, test n = {len(te)}",
              "| score bin | train n | P(Verified) [95% CI] | test n | test Verified rate | inside CI? |",
              "| --- | --- | --- | --- | --- | --- |"]
        inside = 0
        for b, (lo_e, hi_e) in enumerate(zip(edges[:-1], edges[1:])):
            bt = table["bins"][b]
            m = (te.fused >= lo_e) & (te.fused < hi_e) if b else (te.fused < hi_e)
            n_te = int(m.sum())
            rate = float((te[m].gold_verdict == "Verified").mean()) if n_te else None
            ok = rate is not None and bt["ci95"][0] <= rate <= bt["ci95"][1]
            inside += ok
            lo_s = "−∞" if lo_e == -np.inf else f"{lo_e:.3f}"
            hi_s = "∞" if hi_e == np.inf else f"{hi_e:.3f}"
            L.append(f"| [{lo_s}, {hi_s}) | {bt['n']} | {bt['p_verified']:.2f} "
                     f"[{bt['ci95'][0]:.2f}, {bt['ci95'][1]:.2f}] | {n_te} | "
                     f"{'n/a' if rate is None else f'{rate:.2f}'} | {'yes' if ok else 'no'} |")
        L += ["", f"- Test Brier score: **{brier:.3f}** vs **{brier_base:.3f}** for always predicting "
              f"the train Verified rate ({base:.2f}). "
              + ("The score adds calibrated information." if brier < brier_base else
                 "**The score adds no calibrated information over the base rate** — consistent with "
                 "the near-chance AUC; the intervals say so honestly by overlapping."),
              f"- {inside} of {len(table['bins'])} test bin rates fall inside their train 95% CI.\n"]
    L.append("_Caveat: fitted on evaluation signals (NLI on the top-1 passage, experiment corpus); "
             "the live API uses the most decisive of the top-3 passages, so live scores are only "
             "approximately on this scale._")
    out = ROOT / "results" / "calibration.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
