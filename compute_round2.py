"""
compute_round2.py  --  analyses the returned round-2 sheets (Corrections spec A4).

Run once BOTH round2_annotator_A.xlsx and round2_annotator_B.xlsx are filled:

    .venv/Scripts/python.exe compute_round2.py

Reports and writes results/label_audit.md:
  1. Human-human agreement -- 3-class and binary (Hallucinated vs not) Cohen's
     kappa, each with a 95% bootstrap CI (2,000 resamples), the confusion matrix,
     and how many claims BOTH annotators called Hallucinated.
  2. Label-scheme check -- how often each annotator used each label; a loud flag
     if either annotator never used one.
  3. Anchoring check -- where the two humans AGREE, how often the existing gold
     label (and the AI verdict) matches them, as a rate with a 95% Wilson CI,
     split by language.

Reads only; the private key (gold + AI verdicts) is git-ignored and never copied
into the report.
"""
from __future__ import annotations
import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.exceptions import UndefinedMetricWarning
from sklearn.metrics import cohen_kappa_score, confusion_matrix

OUT = Path("annotation_round2")
KEY = OUT / "round2_key_DO_NOT_SHARE.csv"
LABELS = ["Verified", "Uncertain", "Hallucinated"]
N_BOOT = 2000
SEED = 42


def _norm1(v):
    """Normalise one free-text verdict. Prefix-based (not an exact dict) so it
    tolerates typos like 'verfied' -- IDENTICAL to compute_iaa.py and
    generate_results_summary.py, so every script reads the same labels."""
    s = str(v).strip().lower()
    if s.startswith(("verif", "verf")):
        return "Verified"
    if s.startswith(("hall", "halu")):
        return "Hallucinated"
    if s.startswith(("uncert", "unsure", "unclear")):
        return "Uncertain"
    return None


def _norm(s: pd.Series) -> pd.Series:
    return s.map(_norm1)


def load_sheet(tag: str):
    p = OUT / f"round2_annotator_{tag}.xlsx"
    if not p.exists():
        raise SystemExit(f"missing {p} — fill both round-2 sheets first.")
    d = pd.read_excel(p)
    d["verdict"] = _norm(d["verdict"])
    return d.set_index("claim_id")


def wilson(k: int, n: int, z: float = 1.96):
    """95% Wilson score interval for a binomial proportion."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return centre - half, centre + half


def kappa_ci(a: np.ndarray, b: np.ndarray, labels, n_boot=N_BOOT, seed=SEED):
    """Point kappa + 95% bootstrap CI. Resamples the paired labels with
    replacement; skips resamples where kappa is undefined (single class)."""
    point = cohen_kappa_score(a, b, labels=labels)
    rng = np.random.default_rng(seed)
    n = len(a)
    ks = []
    # A resample that lands on a single class makes kappa undefined (0/0 -> NaN);
    # that is expected under heavy skew, so we skip those and silence the per-call
    # warning rather than print it thousands of times.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UndefinedMetricWarning)
        for _ in range(n_boot):
            idx = rng.integers(0, n, n)
            k = cohen_kappa_score(a[idx], b[idx], labels=labels)
            if k == k:  # not NaN
                ks.append(k)
    if not ks:
        return point, float("nan"), float("nan"), 0
    lo, hi = np.percentile(ks, [2.5, 97.5])
    return point, float(lo), float(hi), len(ks)


def main() -> None:
    A = load_sheet("A")
    B = load_sheet("B")

    shared = A.index.intersection(B.index)
    both = pd.DataFrame({
        "a": A["verdict"].reindex(shared),
        "b": B["verdict"].reindex(shared),
        "language": A["language"].reindex(shared),
    }).dropna(subset=["a", "b"])
    n = len(both)
    if n < 2:
        raise SystemExit(f"only {n} claims labeled by both annotators — nothing to compute yet.")

    a3, b3 = both["a"].to_numpy(), both["b"].to_numpy()
    aH, bH = (a3 == "Hallucinated"), (b3 == "Hallucinated")

    k3, k3lo, k3hi, k3n = kappa_ci(a3, b3, LABELS)
    kH, kHlo, kHhi, kHn = kappa_ci(aH, bH, [False, True])
    raw3 = float((a3 == b3).mean())
    rawH = float((aH == bH).mean())
    both_hallu = int((aH & bH).sum())
    cm = confusion_matrix(a3, b3, labels=LABELS)

    # 2. label usage
    usage = {tag: {lab: int((s == lab).sum()) for lab in LABELS}
             for tag, s in (("A", a3), ("B", b3))}
    never = [(tag, lab) for tag in ("A", "B") for lab in LABELS if usage[tag][lab] == 0]

    # 3. anchoring: where humans agree, does gold / AI match them?
    agree = both[both["a"] == both["b"]].copy()
    agree["human"] = agree["a"]
    anchor_rows = []
    if KEY.exists():
        key = pd.read_csv(KEY, encoding="utf-8-sig").set_index("claim_id")
        agree["gold"] = _norm(key["gold_verdict"]).reindex(agree.index)
        agree["ai"] = _norm(key["ai_verdict"]).reindex(agree.index)
        for lang in ("overall", "en", "hi"):
            sub = agree if lang == "overall" else agree[agree["language"] == lang]
            if len(sub) == 0:
                continue
            for who in ("gold", "ai"):
                m = int((sub[who] == sub["human"]).sum())
                lo, hi = wilson(m, len(sub))
                anchor_rows.append((lang, who, m, len(sub), m / len(sub), lo, hi))

    # ---------- console + report ----------
    def pc(x):
        return f"{x:.3f}" if x == x else "n/a"

    L = ["# Round-2 label audit\n",
         f"Human–human agreement and an anchoring check on {n} claims labelled by "
         f"both annotators (of 50 issued). The private key (gold + AI verdicts) is "
         f"git-ignored and not reproduced here.\n",
         "## 1. Human–human agreement",
         "| Scheme | kappa | 95% CI (bootstrap) | valid resamples | raw agreement |",
         "| --- | --- | --- | --- | --- |",
         f"| 3-class (V/U/H) | {pc(k3)} | [{pc(k3lo)}, {pc(k3hi)}] | {k3n}/{N_BOOT} | {raw3:.0%} |",
         f"| Binary (Hallucinated vs not) | {pc(kH)} | [{pc(kHlo)}, {pc(kHhi)}] | {kHn}/{N_BOOT} | {rawH:.0%} |",
         "",
         (f"- **Binary kappa {pc(kH)} is {'AT/ABOVE' if kH >= 0.65 else 'BELOW'} the guideline "
          f"target of 0.65.** Raw agreement is high ({rawH:.0%}) but the labels are heavily "
          f"skewed to Verified, so chance agreement is high and kappa stays low — read the two "
          f"together, and note the wide CI on this n."),
         f"- Claims **both** annotators called Hallucinated: **{both_hallu}**.",
         "- Confusion matrix (rows = A, cols = B; order Verified / Uncertain / Hallucinated):",
         "```",
         np.array2string(cm),
         "```", ""]

    L += ["## 2. Label-scheme check",
          "| Label | A used | B used |",
          "| --- | --- | --- |"]
    for lab in LABELS:
        L.append(f"| {lab} | {usage['A'][lab]} | {usage['B'][lab]} |")
    if never:
        L.append("")
        for tag, lab in never:
            L.append(f"> **FLAG: annotator {tag} never used \"{lab}\".**")
        L.append("> Context: this round-2 set is drawn from `ai_agreed` claims — ones clear "
                 "enough that the reviewer and the AI already agreed — which are mostly "
                 "unambiguous. So an unused \"Uncertain\" here most likely means no genuinely "
                 "ambiguous claims appeared in this sample, not that the annotators used the "
                 "wrong scheme. It does mean the Verified/Uncertain boundary was never "
                 "exercised, so the 3-class and binary kappa coincide and this sample cannot "
                 "measure 3-class agreement — it measures the binary hallucinated-vs-not call.")
    L.append("")

    L += ["## 3. Anchoring check (where the two humans agree)",
          "How often the existing gold label — and the AI verdict — matches the humans' "
          "agreed label. A gold match rate well below 1.0 is evidence of anchoring in round 1 "
          "(labels reviewed with the AI verdict visible).\n",
          "| Split | vs | match | n | rate | 95% CI (Wilson) |",
          "| --- | --- | --- | --- | --- | --- |"]
    if anchor_rows:
        for lang, who, m, tot, rate, lo, hi in anchor_rows:
            L.append(f"| {lang} | {who} | {m} | {tot} | {rate:.0%} | [{max(0.0,lo):.0%}, {min(1.0,hi):.0%}] |")
    else:
        L.append("| (key not present) | | | | | |")
    L += ["",
          f"_n = {n} both-labelled claims; agreement subset = {len(agree)}. Small n — read the "
          f"CIs, not the point rates. Hindi round-2 was drawn from `ai_agreed` claims that are "
          f"almost all Verified, so Hindi mainly tests anchoring, not disagreement._\n"]

    Path("results").mkdir(exist_ok=True)
    out = Path("results") / "label_audit.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
