"""
round3_kg_decides.py -- EXPLORATORY, not pre-registered. Compares two ways of
using the KG on round-3 claims (KG signals from round3/signals_round3_kgfix.csv,
labels from the two annotator sheets):

  fused       current CMHSA: NLI and KG averaged 50/50 when the KG answers
  kg_decides  when the KG answers (supported / contradicted), its answer is the
              score; otherwise NLI alone

Writes results/round3_kg_decides.md.
    .venv/Scripts/python.exe round3_kg_decides.py
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_round3 import SENSITIVITY_EXCLUDE, auc, hallu_f1, paired
from compute_round2 import _norm1

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "round3"


def scores(gold: pd.DataFrame) -> dict[str, np.ndarray]:
    nli = gold.nli_net.fillna(0.5).to_numpy()
    kg = gold.kg_conf.to_numpy(dtype=float)
    has = ~np.isnan(kg)
    return {
        "NLI only": nli,
        "fused (current)": np.where(has, (nli + np.nan_to_num(kg)) / 2, nli),
        "kg_decides": np.where(has, np.nan_to_num(kg), nli),
    }


def block(gold: pd.DataFrame, title: str) -> list[str]:
    y = (gold.a == "Verified").astype(int).to_numpy()
    s = scores(gold)
    L = [f"## {title}", f"n = {len(gold)} (Verified {int(y.sum())}, Hallucinated {int((y == 0).sum())}); "
         f"KG answered {int((~gold.kg_conf.isna()).sum())}", "",
         "| Score | AUC | Hallucinated-F1 @0.35/0.65 |", "| --- | --- | --- |"]
    L += [f"| {k} | {auc(y, v):.3f} | {hallu_f1(y, v):.3f} |" for k, v in s.items()]
    for base in ("fused (current)", "NLI only"):
        da = paired(y, s[base], s["kg_decides"], auc)
        df = paired(y, s[base], s["kg_decides"], hallu_f1)
        L.append(f"- kg_decides − {base}: ΔAUC {da[0]:+.3f} [{da[1]:+.3f}, {da[2]:+.3f}]; "
                 f"ΔHallucinated-F1 {df[0]:+.3f} [{df[1]:+.3f}, {df[2]:+.3f}]")
    # the case that motivated the change: KG sure, NLI disagrees
    kg = gold.kg_conf.to_numpy(dtype=float)
    nli = gold.nli_net.fillna(0.5).to_numpy()
    disagree = (~np.isnan(kg)) & (np.abs(kg - nli) >= 0.5)
    right_kg = int(((kg[disagree] >= 0.5) == (y[disagree] == 1)).sum())
    L += [f"- Claims where the KG answered and NLI disagreed by ≥ 0.5: {int(disagree.sum())}; "
          f"the KG was right on {right_kg}.", ""]
    return L


def main() -> None:
    sig = pd.read_csv(OUT / "signals_round3_kgfix.csv").set_index("claim_id")
    A = pd.read_excel(OUT / "round3_annotator_A.xlsx").set_index("claim_id")
    B = pd.read_excel(OUT / "round3_annotator_B.xlsx").set_index("claim_id")
    d = pd.DataFrame({"a": A.verdict.map(_norm1), "b": B.verdict.map(_norm1)}).dropna()
    gold = d[(d.a == d.b) & d.a.isin(["Verified", "Hallucinated"])].join(sig)
    L = ["# Round 3 — should the KG decide when it answers? (EXPLORATORY)\n",
         "> Not pre-registered; decided after the labels were seen. Labels are AI-assisted, "
         "annotator-verified (Deviation 3). KG signals after the place-linking fix. English "
         "claims only: the KG has no Hindi path in this data.\n"]
    L += block(gold, "All gold claims")
    L += block(gold.drop([c for c in SENSITIVITY_EXCLUDE if c in gold.index]),
               "Without the 3 coreference-garbled claims")
    out = ROOT / "results" / "round3_kg_decides.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
