"""
analyze_round3.py -- KG relational pilot, step 3: the pre-registered analysis
(round3/PREREGISTRATION.md). Run once both round-3 sheets are filled:

    .venv/Scripts/python.exe analyze_round3.py

Reads round3/round3_annotator_A.xlsx, _B.xlsx and round3/signals_round3.csv
(computed before the labels existed). Writes results/round3_kg_pilot.md.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from compute_round2 import LABELS, _norm1, kappa_ci
from member1_model.calibration import wilson

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "round3"
N_BOOT, SEED, MIN_POS = 2000, 42, 10
LOW, HIGH = 0.35, 0.65  # shipped verdict cut-offs


def hallu_f1(y: np.ndarray, s: np.ndarray) -> float:
    """Hallucinated-F1 with the shipped tiers (<0.35 Hallucinated). y: 1 = Verified."""
    pred_h, true_h = s < LOW, y == 0
    tp = int((pred_h & true_h).sum())
    denom = 2 * tp + int((pred_h & ~true_h).sum()) + int((~pred_h & true_h).sum())
    return 2 * tp / denom if denom else 0.0


def auc(y, s):
    return roc_auc_score(y, s)


def paired(y, a, b, stat):
    """stat(b) - stat(a) with a paired bootstrap 95% CI over claims."""
    rng = np.random.default_rng(SEED)
    d = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(y), len(y))
        if len(set(y[i])) == 2:
            d.append(stat(y[i], b[i]) - stat(y[i], a[i]))
    lo, hi = np.percentile(d, [2.5, 97.5])
    return stat(y, b) - stat(y, a), lo, hi


def main() -> None:
    A = pd.read_excel(OUT / "round3_annotator_A.xlsx").set_index("claim_id")
    B = pd.read_excel(OUT / "round3_annotator_B.xlsx").set_index("claim_id")
    sig = pd.read_csv(OUT / "signals_round3.csv").set_index("claim_id")
    d = pd.DataFrame({"a": A.verdict.map(_norm1), "b": B.verdict.map(_norm1)}).dropna()
    if len(d) < 2:
        raise SystemExit("Round-3 sheets are not filled yet.")
    d = d.join(sig)

    k3 = kappa_ci(d.a.to_numpy(), d.b.to_numpy(), LABELS)
    kb = kappa_ci((d.a == "Hallucinated").to_numpy(), (d.b == "Hallucinated").to_numpy(), [False, True])
    gold = d[(d.a == d.b) & d.a.isin(["Verified", "Hallucinated"])].copy()
    excluded = d.drop(gold.index)
    y = (gold.a == "Verified").astype(int).to_numpy()
    n_h = int((y == 0).sum())

    nli = gold.nli_net.fillna(0.5).to_numpy()            # no evidence -> neutral, as the API
    kg = gold.kg_conf.to_numpy(dtype=float)
    kg_only = np.where(np.isnan(kg), 0.5, kg)
    fused = np.where(np.isnan(kg), nli, (nli + np.nan_to_num(kg)) / 2)  # NLI and KG 0.5 each
    contra = gold.contra_top1.fillna(0.5).to_numpy()

    L = ["# Round 3 — KG relational pilot: results\n",
         "Pre-registered in `round3/PREREGISTRATION.md` (committed before any answer or label). "
         "Signals from `round3/signals_round3.csv`, computed before the labels existed.\n",
         "## Labels",
         f"- {len(d)} claims labelled by both annotators. Gold (both agree, Verified or "
         f"Hallucinated): **{len(gold)}** — Verified {int(y.sum())}, **Hallucinated {n_h}**. "
         f"Excluded (disagreement or Uncertain): {len(excluded)}.",
         f"- Agreement: binary κ = {kb[0]:.2f} [{kb[1]:.2f}, {kb[2]:.2f}]; 3-class κ = "
         f"{k3[0]:.2f} [{k3[1]:.2f}, {k3[2]:.2f}].\n"]
    few = n_h < MIN_POS or int(y.sum()) < 2
    if few:
        L.append(f"> **Too few positives to interpret** ({n_h} Hallucinated gold claims, below "
                 f"{MIN_POS}): the numbers below are reported, but no hypothesis is declared "
                 f"supported (pre-registered rule).\n")

    cov_all = d.kg_status.isin(["supported", "contradicted"]).mean()
    L += ["## KG coverage and correctness (H2)",
          f"- KG answered (supported or contradicted) for **{cov_all:.0%}** of all pilot claims; "
          f"status counts: {d.kg_status.value_counts().to_dict()}."]
    for status, label in (("supported", "Verified"), ("contradicted", "Hallucinated")):
        s = gold[gold.kg_status == status]
        k = int((s.a == label).sum())
        lo, hi = wilson(k, len(s))
        L.append(f"- KG **{status}** → gold {label}: {k}/{len(s)}"
                 + (f" ({k / len(s):.0%}, 95% CI [{lo:.0%}, {hi:.0%}])" if len(s) else ""))
    L.append("")

    if len(set(y)) == 2:
        L += ["## Discrimination (AUC; 0.5 = chance) and the PRD KG ablation (H1)",
              "| Score | AUC | Hallucinated-F1 @0.35/0.65 |", "| --- | --- | --- |"]
        for name, s in (("NLI only (semantic+NLI, SemSim weight 0)", nli), ("KG only", kg_only),
                        ("**Fused NLI + KG (full CMHSA)**", fused), ("1 − P(contradiction)", contra)):
            L.append(f"| {name} | {auc(y, s):.3f} | {hallu_f1(y, s):.3f} |")
        da, alo, ahi = paired(y, nli, fused, auc)
        df1, flo, fhi = paired(y, nli, fused, hallu_f1)
        dc, clo, chi = paired(y, nli, contra, auc)
        L += ["",
              f"- **H1 (PRD KG ablation):** ΔAUC fused − NLI = {da:+.3f} [{alo:+.3f}, {ahi:+.3f}]; "
              f"ΔHallucinated-F1 = {df1:+.3f} [{flo:+.3f}, {fhi:+.3f}] (PRD target ≥ +0.03).",
              f"  → " + ("not declared (too few positives)." if few else
                         ("**KG helps on relational claims** (CI above 0)." if alo > 0 else
                          "KG's gain is not established (CI includes 0).")),
              f"- **H3 (contradiction re-test):** ΔAUC = {dc:+.3f} [{clo:+.3f}, {chi:+.3f}] → "
              + ("not declared (too few positives)." if few else
                 ("adopt the contradiction signal." if clo > 0 else "not adopted.")), ""]
    if len(excluded):
        L += ["## Excluded claims (for adjudication)", "| claim | A | B |", "| --- | --- | --- |"]
        L += [f"| {r.claim_text[:90]} | {r.a} | {r.b} |" for r in excluded.itertuples()]
    out = ROOT / "results" / "round3_kg_pilot.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
