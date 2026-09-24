"""
make_regroup_comparison.py -- old vs new ablation after regrouping the split
(IMPROVEMENT_PLAN.md 1.2 / corrections spec B1).

OLD = the plain train_test_split results, archived in _archive/results_pre_regroup/
      (412 well-formed claims; claims from one LLM answer on both sides).
NEW = the StratifiedGroupKFold split (fold 0, fixed in advance), where train and
      test share zero source questions, on the 418 well-formed claims after
      task 1.1's corrected quality rules.

Writes results/regroup_comparison.md. Reads only.
"""
from __future__ import annotations
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
OLD_DIR = ROOT / "_archive" / "results_pre_regroup"
CONFIGS = ["Full (S+N+KG)", "SemSim only", "NLI only", "SemSim + NLI", "Always-Verified baseline"]


def split_stats(train_csv: Path, test_csv: Path) -> dict:
    tr, te = pd.read_csv(train_csv), pd.read_csv(test_csv)
    shared = len(set(tr.source_query_id) & set(te.source_query_id))
    out = {"n_train": len(tr), "n_test": len(te), "shared_questions": shared,
           "test_questions": te.source_query_id.nunique()}
    for lang in ("en", "hi"):
        for name, d in (("train", tr), ("test", te)):
            out[f"{lang}_{name}_hallu"] = int(((d.language == lang) & (d.gold_verdict == "Hallucinated")).sum())
    return out


def cell(block: dict, config: str) -> tuple[str, str]:
    key = "always_verified_baseline" if config == "Always-Verified baseline" else config
    r = block["configurations"].get(key, {})
    m = r.get("test_all")
    if not m:
        return "n/a", "n/a"
    return f"{m['accuracy']:.3f}", f"{m['hallucinated_f1']:.3f}"


def main() -> None:
    old_s = split_stats(OLD_DIR / "gold_train_clean.csv", OLD_DIR / "gold_test_clean.csv")
    new_s = split_stats(ROOT / "gold_train_clean.csv", ROOT / "gold_test_clean.csv")

    L = ["# Regrouped split — old vs new ablation\n",
         "**Old:** plain stratified `train_test_split` (claims from the same LLM answer on both "
         "sides). **New:** `StratifiedGroupKFold` grouped by `source_query_id`, fold 0 as test "
         "(chosen before running; no other fold tried). Cut-points refit on each train split. "
         "The new well-formed set is 418 claims (was 412) after task 1.1's corrected quality "
         "rules.\n",
         "## The splits", "| | old | new |", "| --- | --- | --- |",
         f"| train / test claims | {old_s['n_train']} / {old_s['n_test']} | {new_s['n_train']} / {new_s['n_test']} |",
         f"| test source questions also in train | **{old_s['shared_questions']} of {old_s['test_questions']}** | "
         f"**{new_s['shared_questions']} of {new_s['test_questions']}** |"]
    for lang in ("en", "hi"):
        L.append(f"| {lang.upper()} Hallucinated train / test | {old_s[f'{lang}_train_hallu']} / "
                 f"{old_s[f'{lang}_test_hallu']} | {new_s[f'{lang}_train_hallu']} / {new_s[f'{lang}_test_hallu']} |")

    for mode in ("no_semsim", "with_semsim"):
        old = json.loads((OLD_DIR / "results" / f"ablation_clean_{mode}.json").read_text(encoding="utf-8"))
        new = json.loads((ROOT / "results" / f"ablation_clean_{mode}.json").read_text(encoding="utf-8"))
        L += ["", f"## Ablation — `{mode}` (test accuracy / Hallu-F1)"]
        for lang in ("en", "hi"):
            L += ["", f"### {lang.upper()} — test Hallucinated: old {old_s[f'{lang}_test_hallu']}, "
                  f"new {new_s[f'{lang}_test_hallu']}",
                  "| Configuration | Acc old | Acc new | Hallu-F1 old | Hallu-F1 new |",
                  "| --- | --- | --- | --- | --- |"]
            for c in CONFIGS:
                ao, ho = cell(old["languages"][lang], c)
                an, hn = cell(new["languages"][lang], c)
                L.append(f"| {c} | {ao} | {an} | {ho} | {hn} |")

    L += ["", "## Reading it",
          "- The leak is gone: the new test split shares no source question with training.",
          "- Both splits have fewer than 10 Hallucinated test claims per language, so every "
          "Hallu-F1 above is too few positives to interpret (the new ablation tables print 95% "
          "CIs; English Hallu-F1 spans roughly 0.00-0.46).",
          "- The qualitative result is unchanged: no configuration beats the always-Verified "
          "baseline on accuracy, and the NLI-based configurations remain identical to each other "
          "(KG never fires; SemSim does not vote).",
          "- Hindi: on the new split the NLI configurations' cut-points fit to 0.00/0.00 on train, "
          "i.e. they predict Verified for every claim. Their accuracy equalling the always-Verified "
          "baseline is that degenerate rule, not detection.",
          "- Numbers moved in both directions between splits; per the ground rules they are reported "
          "as they came out, with no other fold or seed tried.\n"]

    out = ROOT / "results" / "regroup_comparison.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
