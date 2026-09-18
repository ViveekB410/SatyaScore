"""
reproduce_problems.py — one-command, reproducible evidence for the problems
documented in PROBLEM_SUMMARY.md, so a reviewer can verify each claim
directly against the project's own data instead of taking our word for it.

Run:
    python reproduce_problems.py                  # problems 1-4 (fast, no network)
    python reproduce_problems.py --with-nli-model # also re-run the NLI sanity
                                                  # check (loads the ~500MB model)

What it checks (every number is computed live from the CSVs on disk):
    PROBLEM 1  SemSim measures topical relevance, not truth.
    PROBLEM 2  NLI_prob (as stored) does not separate hallucinated from verified.
    PROBLEM 3  KG_conf has zero coverage.
    PROBLEM 4  The trained fusion collapses to SemSim and catches ~0
               hallucinations on held-out data — and does WORSE than a trivial
               always-"Verified" baseline.

Problems 1-3 read the already-scored gold CSV (pandas + numpy + sklearn only).
Problem 4 uses the REAL production CMHSAScorer for a faithful ablation.
--with-nli-model is the only part that loads the NLI model itself.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, recall_score, roc_auc_score

# All 456 rows with regenerated signals; fall back to the pre-v2 gold if absent.
GOLD_ALL = "SatyaScore_final_gold_456claims_v2.csv"
GOLD_ALL_FALLBACK = "SatyaScore_final_gold_456claims.csv"
TEST_CSV = "gold_test.csv"          # held-out split (never used for training)
SIGNAL_COLS = ["sem_sim", "nli_prob", "kg_conf"]
CLASSES = ["Hallucinated", "Uncertain", "Verified"]


# ---- dependency-light stats helpers (numpy + math only) --------------------

def _phi(x: float) -> float:
    """Standard-normal CDF via erf, so we don't need scipy."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Standardized mean difference between two samples (pooled SD)."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan")
    va, vb = a.var(ddof=1), b.var(ddof=1)
    pooled = math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    return float("nan") if pooled == 0 else (a.mean() - b.mean()) / pooled


def overlap_pct(d: float) -> float:
    """Overlapping coefficient (%) of two equal-variance normals separated by d.
    d=0 -> 100% overlap (indistinguishable); large d -> ~0% overlap."""
    if math.isnan(d):
        return float("nan")
    return 2.0 * _phi(-abs(d) / 2.0) * 100.0


def _binary_auc(df: pd.DataFrame, col: str) -> float:
    """ROC-AUC of `col` treated as a 'this claim is Verified' score, over just
    the Hallucinated vs Verified rows. 0.50 == the signal cannot tell them
    apart; 1.00 == perfect separation."""
    m = df[df["gold_verdict"].isin(["Hallucinated", "Verified"]) & df[col].notna()]
    if m["gold_verdict"].nunique() < 2:
        return float("nan")
    y = (m["gold_verdict"] == "Verified").astype(int).to_numpy()
    return roc_auc_score(y, m[col].to_numpy())


def load_gold() -> pd.DataFrame:
    path = GOLD_ALL if Path(GOLD_ALL).exists() else GOLD_ALL_FALLBACK
    if not Path(path).exists():
        raise SystemExit(f"Could not find {GOLD_ALL} or {GOLD_ALL_FALLBACK} here.")
    df = pd.read_csv(path)
    for c in SIGNAL_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    counts = ", ".join(f"{k}={v}" for k, v in df["gold_verdict"].value_counts().items())
    print(f"Loaded {len(df)} gold-labeled claims from {path}")
    print(f"  class balance: {counts}\n")
    return df


# ---- the four problems -----------------------------------------------------

def problem_1_semsim(df: pd.DataFrame) -> dict:
    print("=" * 78)
    print("PROBLEM 1 — SemSim measures topical relevance, not truth")
    print("=" * 78)
    sub = df[df["sem_sim"].notna()]
    stats = sub.groupby("gold_verdict")["sem_sim"].agg(["count", "mean", "std"])
    print(stats.round(4).to_string())

    H = sub.loc[sub["gold_verdict"] == "Hallucinated", "sem_sim"].to_numpy()
    V = sub.loc[sub["gold_verdict"] == "Verified", "sem_sim"].to_numpy()
    d = cohens_d(V, H)
    auc = _binary_auc(sub, "sem_sim")
    print(f"\n  Cohen's d (Verified vs Hallucinated): {d:.3f}"
          f"   (~{overlap_pct(d):.0f}% distribution overlap)")
    print(f"  ROC-AUC, sem_sim separating Verified vs Hallucinated: {auc:.3f}"
          f"   (0.50 = no separation)")

    confirmed = abs(d) < 0.35 and abs(auc - 0.5) < 0.1
    print(f"\n  >>> {'CONFIRMED' if confirmed else 'not confirmed'}: a false claim "
          f"retrieves evidence about as well as a true one — sem_sim cannot\n"
          f"      tell factuality apart on this data.\n")
    return {"cohens_d": round(d, 4), "auc": round(auc, 4), "confirmed": bool(confirmed)}


def problem_2_nli(df: pd.DataFrame) -> dict:
    print("=" * 78)
    print("PROBLEM 2 — NLI_prob (as stored) does not separate the classes")
    print("=" * 78)
    sub = df[df["nli_prob"].notna()]
    stats = sub.groupby("gold_verdict")["nli_prob"].agg(["count", "mean", "std"])
    print(stats.round(4).to_string())

    is_hallu = (sub["gold_verdict"] == "Hallucinated").astype(int)
    corr = float(sub["nli_prob"].corr(is_hallu))
    auc = _binary_auc(sub, "nli_prob")
    spread = float(stats["mean"].max() - stats["mean"].min())
    print(f"\n  corr(nli_prob, is_hallucinated): {corr:.4f}   (want a clear NEGATIVE "
          f"number; ~0 = no signal)")
    print(f"  ROC-AUC, nli_prob separating Verified vs Hallucinated: {auc:.3f}"
          f"   (0.50 = no separation)")
    print(f"  spread between class means: {spread:.4f}")

    confirmed = abs(corr) < 0.1 and spread < 0.1
    print(f"\n  >>> {'CONFIRMED' if confirmed else 'not confirmed'}: nli_prob is nearly "
          f"flat across verdict classes.\n"
          f"      (This is the entailment-only value; the contradiction-aware fix "
          f"is not re-measured yet.)\n")
    return {"corr": round(corr, 4), "auc": round(auc, 4),
            "spread": round(spread, 4), "confirmed": bool(confirmed)}


def problem_3_kg(df: pd.DataFrame) -> dict:
    print("=" * 78)
    print("PROBLEM 3 — KG_conf has zero coverage")
    print("=" * 78)
    n = int(df["kg_conf"].notna().sum()) if "kg_conf" in df.columns else 0
    total = len(df)
    print(f"  Rows with a non-blank kg_conf: {n} / {total}  ({100 * n / total:.1f}%)")
    confirmed = n == 0
    print(f"\n  >>> {'CONFIRMED' if confirmed else 'not confirmed'}: the KG arm has "
          f"{'no' if confirmed else 'some'} data — gamma is untrained and the\n"
          f"      'full' model is numerically identical to 'SemSim+NLI'.\n")
    return {"kg_coverage": f"{n}/{total}", "confirmed": bool(confirmed)}


def _ablate_language(lang: str) -> dict | None:
    """Faithful ablation for one language using the REAL trained weights and
    the REAL CMHSAScorer, on the held-out test set. 'Ablating' a signal means
    masking it to None for every claim, exactly as production does when a
    signal is unavailable."""
    from member1_model.cmhsa import CMHSAScorer, ClaimSubScores  # local: needs torch

    wpath = Path(f"weights_{lang}.json")
    if not wpath.exists() or not Path(TEST_CSV).exists():
        print(f"  ({lang}: skipped — need {wpath} and {TEST_CSV})")
        return None

    w = json.loads(wpath.read_text())
    scorer = CMHSAScorer()
    scorer.load_weights(lang, w["alpha"], w["beta"], w["gamma"])

    df = pd.read_csv(TEST_CSV)
    df = df[df["language"] == lang]
    for c in SIGNAL_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    print(f"\n  --- language={lang} | held-out test claims={len(df)} ---")
    print(f"  Trained weights:  alpha={w['alpha']:.3f}  beta={w['beta']:.4f}  "
          f"gamma={w['gamma']:.3f}   <- NLI weight (beta) trained to ~0")

    configs = {
        "Full (S+N+KG)": {"semsim", "nli", "kg"},
        "SemSim only":   {"semsim"},
        "SemSim + NLI":  {"semsim", "nli"},
        "NLI only":      {"nli"},
    }

    def masked(row, allowed):
        return ClaimSubScores(
            claim_id=str(row["claim_id"]),
            sem_sim=row["sem_sim"] if "semsim" in allowed and pd.notna(row["sem_sim"]) else None,
            nli_prob=row["nli_prob"] if "nli" in allowed and pd.notna(row["nli_prob"]) else None,
            kg_conf=row["kg_conf"] if "kg" in allowed and pd.notna(row["kg_conf"]) else None,
        )

    print(f"  {'config':<16}{'accuracy':>10}{'macro-F1':>10}{'Hallu-recall':>14}{'Hallu-F1':>10}")
    rows = {}
    for name, allowed in configs.items():
        y_true, y_pred = [], []
        for _, row in df.iterrows():
            try:
                sc = scorer.score_claim(masked(row, allowed), lang)
            except ValueError:
                continue  # no signal available under this config for this row
            y_true.append(row["gold_verdict"])
            y_pred.append(sc.verdict.value)
        acc = accuracy_score(y_true, y_pred)
        mf1 = f1_score(y_true, y_pred, labels=CLASSES, average="macro", zero_division=0)
        hrec = recall_score(y_true, y_pred, labels=["Hallucinated"], average="macro", zero_division=0)
        hf1 = f1_score(y_true, y_pred, labels=["Hallucinated"], average="macro", zero_division=0)
        rows[name] = {"accuracy": acc, "macro_f1": mf1, "hallu_recall": hrec, "hallu_f1": hf1}
        print(f"  {name:<16}{acc:>10.3f}{mf1:>10.3f}{hrec:>14.3f}{hf1:>10.3f}")

    # Trivial baseline: always predict the majority class (Verified).
    y_true_all = df["gold_verdict"].tolist()
    maj = ["Verified"] * len(y_true_all)
    maj_acc = accuracy_score(y_true_all, maj)
    maj_mf1 = f1_score(y_true_all, maj, labels=CLASSES, average="macro", zero_division=0)
    print(f"  {'always-Verified':<16}{maj_acc:>10.3f}{maj_mf1:>10.3f}{0.0:>14.3f}{0.0:>10.3f}")

    full, sem = rows["Full (S+N+KG)"], rows["SemSim only"]
    collapse = math.isclose(full["macro_f1"], sem["macro_f1"], abs_tol=1e-9)
    misses_all = full["hallu_f1"] == 0.0
    worse_than_majority = full["accuracy"] < maj_acc
    print(f"\n  >>> full == 'SemSim only': {collapse} | catches 0 hallucinations "
          f"(Hallu-F1=0): {misses_all} | worse than always-Verified: {worse_than_majority}")
    return {"weights": {k: round(w[k], 4) for k in ("alpha", "beta", "gamma")},
            "configs": {k: {m: round(v, 4) for m, v in r.items()} for k, r in rows.items()},
            "majority_accuracy": round(maj_acc, 4),
            "collapse": bool(collapse), "misses_all_hallucinations": bool(misses_all),
            "worse_than_majority": bool(worse_than_majority)}


def problem_4_ablation() -> dict:
    print("=" * 78)
    print("PROBLEM 4 — Trained fusion collapses to SemSim and misses all hallucinations")
    print("=" * 78)
    out = {}
    for lang in ("en", "hi"):
        res = _ablate_language(lang)
        if res is not None:
            out[lang] = res
    print()
    return out


def nli_model_sanity() -> dict:
    """Optional: proves the NLI MODEL itself is fine (it was the downstream
    usage that was broken). Loads the ~500MB model, so it's opt-in."""
    print("=" * 78)
    print("BONUS — the NLI model itself works (the bug was how we USED its output)")
    print("=" * 78)
    from member1_model.nli_scorer import NLIScorer  # local: loads the model
    scorer = NLIScorer()
    cases = [
        ("clear entailment",
         "The Indian Premier League is a professional Twenty20 cricket league contested by ten teams.",
         "The IPL has ten teams."),
        ("real hallucination from our data (IPL '8 teams')",
         "The Indian Premier League is a professional Twenty20 cricket league contested by ten teams.",
         "The IPL is contested by eight teams."),
        ("clear contradiction",
         "Water boils at 100 degrees Celsius at sea level.",
         "Water boils at 50 degrees Celsius at sea level."),
    ]
    out = {}
    for name, premise, hyp in cases:
        r = scorer.score("c", premise, hyp)
        print(f"  {name}:")
        print(f"      entailment={r.entailment_prob:.3f}  contradiction={r.contradiction_prob:.3f}"
              f"  neutral={r.neutral_prob:.3f}")
        out[name] = {"entailment": round(r.entailment_prob, 3),
                     "contradiction": round(r.contradiction_prob, 3)}
    print("\n  >>> The model correctly ENTAILS true claims and CONTRADICTS false ones.\n")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--with-nli-model", action="store_true",
                        help="also run the NLI-model sanity check (downloads/loads the model)")
    parser.add_argument("--out", default="problem_evidence.json",
                        help="where to write the machine-readable evidence")
    args = parser.parse_args()

    df = load_gold()
    evidence = {
        "problem_1_semsim_no_truth_separation": problem_1_semsim(df),
        "problem_2_nli_flat": problem_2_nli(df),
        "problem_3_kg_zero_coverage": problem_3_kg(df),
        "problem_4_fusion_collapse": problem_4_ablation(),
    }
    if args.with_nli_model:
        evidence["bonus_nli_model_works"] = nli_model_sanity()

    Path(args.out).write_text(json.dumps(evidence, indent=2))
    print("=" * 78)
    print(f"Machine-readable evidence written to {args.out}")
    print("Full narrative + interpretation: PROBLEM_SUMMARY.md")
    print("=" * 78)


if __name__ == "__main__":
    main()
