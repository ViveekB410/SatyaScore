"""
honest_eval.py — evaluate SatyaScore the way the results section has to
report it: from the CSVs alone, with synthetic perturbations separated from
human-annotated claims, and with verdict cut-points fitted on the training
split only.

No GPU, no network, no model loading. Everything below is recomputed from
gold_train_v3.csv, gold_test_v3.csv and weights_{lang}.json, so this file is
the fastest way to check whether a regeneration actually changed anything.

WHY THIS EXISTS
---------------
Three ways this project's headline numbers have been wrong before:

  1. Synthetic perturbations inflate recall. A perturbed claim is re-scored
     against a corpus rebuilt from its own source topic, so its contradiction
     is easy to retrieve. Human-annotated hallucinations are not like that.
     Any Hallucinated-F1 quoted over a mixed test set is a blend of an easy
     and a hard population, dominated by whichever is more numerous.

  2. The shipped 0.35/0.65 cut-points were chosen for a three-signal fused
     score. With kg_conf absent for every claim, gamma renormalises away and
     the fused score equals nli_prob, whose Verified-class mean is near 0.50.
     The old cut-points therefore dump most Verified claims into Uncertain.

  3. Cut-points fitted on the test split turn a held-out number into a
     training number. --calibrate fits on train and never touches test.

USAGE
    python honest_eval.py                     # full report -> results/honest_eval.json
    python honest_eval.py --calibrate         # print train-fitted cut-points only
    python honest_eval.py --calibrate --write-thresholds   # also write thresholds_{lang}.json

READING THE OUTPUT
    test_tuned_human_annotated_only is the headline result. Every other block
    is context. Never quote a Hallucinated-F1 from a block whose name does not
    say human_annotated without printing the human-annotated number beside it.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

CLASSES = ["Hallucinated", "Uncertain", "Verified"]
SIGNALS = ["sem_sim", "nli_prob", "kg_conf"]
SYNTHETIC_SOURCE = "synthetic_perturbation"
DEFAULT_CUTPOINTS = (0.35, 0.65)
CALIBRATION_GRID = np.round(np.arange(0.0, 1.001, 0.01), 2)


# ── Loading and fusion ──────────────────────────────────────────────────

def load_split(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    for column in SIGNALS:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["gold_source"] = df.get("gold_source", pd.Series([""] * len(df))).fillna("")
    df["is_synthetic"] = df["gold_source"] == SYNTHETIC_SOURCE
    return df


def load_weights(language: str, config_dir: Path) -> dict:
    path = config_dir / f"weights_{language}.json"
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# CMHSAScorer.load_weights clamps each weight to 1e-8 before recovering
# logits, so a weight saved as 0.0 comes back as a tiny positive number
# rather than a true zero. That detail matters: it is the only reason a
# SemSim-only ablation is scoreable at all when alpha trained to 0.
WEIGHT_FLOOR = 1e-8


def fuse(row: pd.Series, weights: dict) -> float:
    """Mirror of CMHSAScorer.score_claim: weighted mean over whichever signals
    are present, renormalised so the active weights sum to 1. Kept as plain
    numpy here so this script has no torch dependency."""
    active = [
        (max(weights["alpha"], WEIGHT_FLOOR), row["sem_sim"]),
        (max(weights["beta"], WEIGHT_FLOOR), row["nli_prob"]),
        (max(weights["gamma"], WEIGHT_FLOOR), row["kg_conf"]),
    ]
    active = [(w, v) for w, v in active if pd.notna(v)]
    if not active:
        return float("nan")
    total = sum(w for w, _ in active)
    if total <= 0:
        return float("nan")
    return float(np.clip(sum((w / total) * v for w, v in active), 0.0, 1.0))


def add_fused(df: pd.DataFrame, weights_by_language: dict) -> pd.DataFrame:
    df = df.copy()
    df["fused"] = [
        fuse(row, weights_by_language[row["language"]])
        if row["language"] in weights_by_language else float("nan")
        for _, row in df.iterrows()
    ]
    return df


def verdict(score: float, hallucinated_below: float, verified_above: float) -> str:
    if score < hallucinated_below:
        return "Hallucinated"
    if score > verified_above:
        return "Verified"
    return "Uncertain"


# ── Metrics ─────────────────────────────────────────────────────────────

# Below this many Hallucinated test claims, Hallu-F1 is reported but marked
# "too few positives to interpret" (corrections spec B2).
MIN_POSITIVES_TO_INTERPRET = 10
N_BOOT = 2000
BOOT_SEED = 42


def bootstrap_ci(y_true: list[str], y_pred: list[str], n_boot: int = N_BOOT,
                 seed: int = BOOT_SEED) -> dict:
    """95% bootstrap CIs (resampling claims) for accuracy and Hallucinated-F1."""
    t = np.array(y_true)
    p = np.array(y_pred)
    rng = np.random.default_rng(seed)
    n = len(t)
    acc, hf1 = [], []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        tb, pb = t[idx], p[idx]
        acc.append(float((tb == pb).mean()))
        tp = int(((tb == "Hallucinated") & (pb == "Hallucinated")).sum())
        fp = int(((tb != "Hallucinated") & (pb == "Hallucinated")).sum())
        fn = int(((tb == "Hallucinated") & (pb != "Hallucinated")).sum())
        denom = 2 * tp + fp + fn
        hf1.append(2 * tp / denom if denom else 0.0)

    def ci(values):
        lo, hi = np.percentile(values, [2.5, 97.5])
        return [round(float(lo), 4), round(float(hi), 4)]

    return {"accuracy_ci95": ci(acc), "hallucinated_f1_ci95": ci(hf1), "n_boot": n_boot}


def metrics(df: pd.DataFrame, cutpoints: tuple[float, float], ci: bool = False) -> dict | None:
    """Test metrics. Always reports n and n_hallucinated. With ci=True also adds
    95% bootstrap CIs for accuracy and Hallu-F1 (off by default: the cut-point
    search calls this hundreds of times)."""
    scored = df[df["fused"].notna()]
    if scored.empty:
        return None
    y_true = scored["gold_verdict"].tolist()
    y_pred = [verdict(s, *cutpoints) for s in scored["fused"]]
    n_hallucinated = int((scored["gold_verdict"] == "Hallucinated").sum())
    out = {
        "n": len(y_true),
        "n_hallucinated": n_hallucinated,
        "too_few_positives": n_hallucinated < MIN_POSITIVES_TO_INTERPRET,
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "macro_f1": round(f1_score(y_true, y_pred, labels=CLASSES,
                                   average="macro", zero_division=0), 4),
        "hallucinated_f1": round(f1_score(y_true, y_pred, labels=["Hallucinated"],
                                          average="macro", zero_division=0), 4),
        "verified_f1": round(f1_score(y_true, y_pred, labels=["Verified"],
                                      average="macro", zero_division=0), 4),
        "hallucinated_recall": _recall(scored, y_pred, "Hallucinated"),
    }
    if ci:
        out.update(bootstrap_ci(y_true, y_pred))
    return out


def _recall(scored: pd.DataFrame, y_pred: list[str], label: str) -> float | None:
    mask = (scored["gold_verdict"] == label).to_numpy()
    if not mask.any():
        return None
    predicted = np.array(y_pred)[mask]
    return round(float((predicted == label).mean()), 4)


def recall_by_population(df: pd.DataFrame, cutpoints: tuple[float, float]) -> dict:
    """Hallucinated recall, synthetic perturbations against human annotations.

    This gap is the single most load-bearing number in the limitations
    section: it says how much of the reported detection rate is an artefact
    of how the hard negatives were manufactured.
    """
    out = {}
    scored = df[df["fused"].notna()]
    for name, subset in (("synthetic_perturbation", scored[scored["is_synthetic"]]),
                         ("human_annotated", scored[~scored["is_synthetic"]])):
        hallucinated = subset[subset["gold_verdict"] == "Hallucinated"]
        if hallucinated.empty:
            out[name] = {"n": 0, "recall": None}
            continue
        predicted = [verdict(s, *cutpoints) for s in hallucinated["fused"]]
        out[name] = {
            "n": int(len(hallucinated)),
            "recall": round(float(np.mean([p == "Hallucinated" for p in predicted])), 4),
        }
    return out


def coverage(df: pd.DataFrame) -> dict:
    return {
        "n_rows": int(len(df)),
        "n_scored": int(df["fused"].notna().sum()),
        "dropped_no_signal": int(df["fused"].isna().sum()),
        "signal_presence": {
            column: round(float(df[column].notna().mean()), 4) for column in SIGNALS
        },
        "fused_equals_nli_prob": bool(
            np.allclose(
                df.loc[df["fused"].notna(), "fused"],
                df.loc[df["fused"].notna(), "nli_prob"],
                equal_nan=True,
            )
        ) if df["fused"].notna().any() else None,
    }


def class_conditional_means(df: pd.DataFrame) -> dict:
    """Mean of each raw signal per gold class.

    For English, sem_sim is HIGHER for Hallucinated claims than for Verified
    ones. That is not noise to be trained away; it is the finding that
    semantic similarity measures topicality rather than truth.
    """
    out = {}
    for column in SIGNALS:
        subset = df[df[column].notna()]
        if subset.empty:
            continue
        out[column] = {
            str(verdict_label): round(float(group[column].mean()), 4)
            for verdict_label, group in subset.groupby("gold_verdict")
        }
    return out


def discrimination_auc(pooled: pd.DataFrame, language: str) -> dict:
    """Threshold-free separability, holding the positive class fixed.

    Positives are always human-annotated Verified claims. Negatives are once
    the synthetic perturbations and once the human-annotated hallucinations.
    Any difference between the two AUCs is attributable to how the negative
    was manufactured, not to the classifier or the cut-points, because the
    positive class and the score are identical in both comparisons.

    Pooled over train and test deliberately: this is a statement about signal
    separability on the dataset, not a held-out performance claim, and the
    human-annotated hallucinated class is far too small to split further.
    """
    subset = pooled[(pooled["language"] == language) & pooled["fused"].notna()]
    positives = subset[(subset["gold_verdict"] == "Verified") & ~subset["is_synthetic"]]
    out = {"pooled_train_and_test": True, "positive_class": "human-annotated Verified",
           "n_positive": int(len(positives))}

    for name, negatives in (
        ("vs_synthetic_hallucinated",
         subset[(subset["gold_verdict"] == "Hallucinated") & subset["is_synthetic"]]),
        ("vs_human_annotated_hallucinated",
         subset[(subset["gold_verdict"] == "Hallucinated") & ~subset["is_synthetic"]]),
    ):
        if positives.empty or negatives.empty:
            out[name] = {"n_negative": int(len(negatives)), "fused_auc": None, "sem_sim_auc": None}
            continue
        labels = np.r_[np.ones(len(positives)), np.zeros(len(negatives))]
        fused_scores = np.r_[positives["fused"], negatives["fused"]]
        sem_scores = np.r_[positives["sem_sim"].fillna(0.5), negatives["sem_sim"].fillna(0.5)]
        out[name] = {
            "n_negative": int(len(negatives)),
            "fused_auc": round(float(roc_auc_score(labels, fused_scores)), 4),
            "sem_sim_auc": round(float(roc_auc_score(labels, sem_scores)), 4),
        }
    return out


# ── Fast cut-point search ──────────────────────────────────────────────

CLASS_CODES = {label: i for i, label in enumerate(CLASSES)}


def _confusion_metrics(confusion: np.ndarray) -> dict:
    """accuracy, macro-F1 and per-class F1 from a 3x3 true-by-predicted count
    matrix. Matches sklearn with labels=CLASSES, average='macro',
    zero_division=0, and is fast enough to call inside a grid search."""
    total = confusion.sum()
    accuracy = float(np.trace(confusion) / total) if total else 0.0
    f1s = []
    for k in range(3):
        tp = confusion[k, k]
        denominator = 2 * tp + (confusion[:, k].sum() - tp) + (confusion[k, :].sum() - tp)
        f1s.append(float(2 * tp / denominator) if denominator else 0.0)
    return {"accuracy": accuracy, "macro_f1": float(np.mean(f1s)),
            "hallucinated_f1": f1s[CLASS_CODES["Hallucinated"]]}


def search_cutpoints(scores: np.ndarray, labels: np.ndarray,
                     objective: str = "macro_f1") -> tuple[float, float]:
    """Exhaustive search over CALIBRATION_GRID for the cut-points that
    maximise `objective`, ties broken towards a wider Uncertain band.

    Implemented on cumulative class counts rather than by re-scoring the
    split for every candidate pair, because the ablation calls this once per
    configuration per language.
    """
    order = np.argsort(scores, kind="stable")
    sorted_scores = scores[order]
    sorted_labels = labels[order]
    cumulative = np.zeros((3, len(sorted_scores) + 1), dtype=int)
    for k in range(3):
        cumulative[k, 1:] = np.cumsum(sorted_labels == k)

    below = np.searchsorted(sorted_scores, CALIBRATION_GRID, side="left")
    at_or_below = np.searchsorted(sorted_scores, CALIBRATION_GRID, side="right")

    best_key, best_cutpoints = None, DEFAULT_CUTPOINTS
    confusion = np.zeros((3, 3), dtype=int)
    for i, low in enumerate(CALIBRATION_GRID):
        a = below[i]
        for j in range(i, len(CALIBRATION_GRID)):
            b = at_or_below[j]
            confusion[:, 0] = cumulative[:, a]
            confusion[:, 1] = cumulative[:, b] - cumulative[:, a]
            confusion[:, 2] = cumulative[:, -1] - cumulative[:, b]
            scores_dict = _confusion_metrics(confusion)
            key = (round(scores_dict[objective], 4), round(scores_dict["macro_f1"], 4),
                   round(float(CALIBRATION_GRID[j] - low), 4))
            if best_key is None or key > best_key:
                best_key = key
                best_cutpoints = (float(low), float(CALIBRATION_GRID[j]))
    return best_cutpoints


# ── Calibration (train split only) ──────────────────────────────────────

def calibrate(train_df: pd.DataFrame, objective: str = "macro_f1") -> dict:
    """Grid-search verdict cut-points on the TRAINING split.

    Ties are broken towards the wider Uncertain band, which is the
    conservative choice for a system whose Uncertain verdict means "ask a
    human" rather than "assert something".
    """
    scored = train_df[train_df["fused"].notna()]
    if scored.empty:
        return {"error": "no scored training rows"}

    labels = scored["gold_verdict"].map(CLASS_CODES).fillna(-1).to_numpy(dtype=int)
    cutpoints = search_cutpoints(scored["fused"].to_numpy(dtype=float), labels, objective)
    train_metrics = metrics(scored, cutpoints)
    return {
        "cutpoints": cutpoints,
        "objective": objective,
        "train_metrics": train_metrics,
        "n_train_scored": int(len(scored)),
        "n_train_hallucinated": int((scored["gold_verdict"] == "Hallucinated").sum()),
    }


def write_thresholds_file(language: str, calibration: dict, train_csv: Path,
                          config_dir: Path) -> Path:
    path = config_dir / f"thresholds_{language}.json"
    low, high = calibration["cutpoints"]
    payload = {
        "language": language,
        "hallucinated_below": low,
        "verified_above": high,
        "fitted_on": str(train_csv),
        "fitted_on_split": "train",
        "objective": calibration["objective"],
        "n_train_scored": calibration["n_train_scored"],
        "n_train_hallucinated": calibration["n_train_hallucinated"],
        "fitted_at": date.today().isoformat(),
        "note": (
            "Cut-points fitted on the training split against the current fused "
            "score. Refit with `python honest_eval.py --calibrate "
            "--write-thresholds` after any regeneration that changes sem_sim, "
            "nli_prob or kg_conf."
        ),
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


# ── Report ──────────────────────────────────────────────────────────────

def evaluate_language(language: str, train_df: pd.DataFrame, test_df: pd.DataFrame,
                      objective: str) -> dict:
    train_lang = train_df[train_df["language"] == language]
    test_lang = test_df[test_df["language"] == language]
    human_only = test_lang[~test_lang["is_synthetic"]]

    calibration = calibrate(train_lang, objective=objective)
    tuned = tuple(calibration["cutpoints"])

    report = {
        "n_train": int(len(train_lang)),
        "n_test": int(len(test_lang)),
        "train_coverage": coverage(train_lang),
        "test_coverage": coverage(test_lang),
        "class_conditional_means_train": class_conditional_means(train_lang),
        "cutpoints": {"shipped": list(DEFAULT_CUTPOINTS), "tuned_on_train": list(tuned)},
        "calibration": calibration,
        "test_shipped_all": metrics(test_lang, DEFAULT_CUTPOINTS),
        "test_shipped_human_annotated_only": metrics(human_only, DEFAULT_CUTPOINTS),
        "test_tuned_all": metrics(test_lang, tuned),
        "test_tuned_human_annotated_only": metrics(human_only, tuned),
        "hallucinated_recall_shipped": recall_by_population(test_lang, DEFAULT_CUTPOINTS),
        "hallucinated_recall_tuned": recall_by_population(test_lang, tuned),
        "discrimination_auc": discrimination_auc(
            pd.concat([train_df, test_df], ignore_index=True), language),
    }
    report["warnings"] = _warnings(language, report)
    return report


def _warnings(language: str, report: dict) -> list[str]:
    warnings = []
    headline = report["test_tuned_human_annotated_only"]
    if headline is None:
        warnings.append(f"{language}: no scored human-annotated test rows at all")
        return warnings
    if headline["n_hallucinated"] < 10:
        warnings.append(
            f"{language}: headline Hallucinated-F1 rests on "
            f"{headline['n_hallucinated']} human-annotated hallucinated test claims; "
            f"quote it with the count attached"
        )
    dropped = report["test_coverage"]["dropped_no_signal"]
    if dropped:
        warnings.append(
            f"{language}: {dropped} test claims retrieved nothing and were dropped "
            f"before scoring; they are silently absent from every metric above"
        )
    if report["test_coverage"]["signal_presence"]["kg_conf"] == 0.0:
        warnings.append(
            f"{language}: kg_conf coverage is zero, so gamma renormalises away and "
            f"the fused score is arithmetically identical to nli_prob"
        )
    auc = report.get("discrimination_auc", {})
    synthetic_auc = auc.get("vs_synthetic_hallucinated", {}).get("fused_auc")
    human_auc = auc.get("vs_human_annotated_hallucinated", {}).get("fused_auc")
    if synthetic_auc is not None and human_auc is not None and synthetic_auc - human_auc > 0.1:
        warnings.append(
            f"{language}: fused score separates synthetic perturbations at AUC "
            f"{synthetic_auc:.3f} but human-annotated hallucinations at AUC "
            f"{human_auc:.3f} against the same positive class; report both or neither"
        )

    means = report["class_conditional_means_train"].get("sem_sim", {})
    if means.get("Hallucinated") is not None and means.get("Verified") is not None:
        if means["Hallucinated"] > means["Verified"]:
            warnings.append(
                f"{language}: mean sem_sim is higher for Hallucinated "
                f"({means['Hallucinated']:.3f}) than Verified ({means['Verified']:.3f}); "
                f"semantic similarity is anti-correlated with truth on this data"
            )
    return warnings


def print_report(report: dict) -> None:
    for language, block in report["languages"].items():
        print(f"\n{'=' * 72}\n{language.upper()}  "
              f"(train {block['n_train']}, test {block['n_test']})\n{'=' * 72}")
        low, high = block["cutpoints"]["tuned_on_train"]
        print(f"cut-points: shipped {DEFAULT_CUTPOINTS[0]:.2f}/{DEFAULT_CUTPOINTS[1]:.2f}  "
              f"tuned-on-train {low:.2f}/{high:.2f}")
        header = f"  {'block':<38}{'n':>5}{'acc':>8}{'macroF1':>9}{'halluF1':>9}{'halluRec':>10}"
        print(header)
        for key in ("test_shipped_all", "test_shipped_human_annotated_only",
                    "test_tuned_all", "test_tuned_human_annotated_only"):
            m = block[key]
            if m is None:
                print(f"  {key:<38}{'--':>5}")
                continue
            recall = "--" if m["hallucinated_recall"] is None else f"{m['hallucinated_recall']:.3f}"
            marker = "*" if key == "test_tuned_human_annotated_only" else " "
            print(f" {marker}{key:<38}{m['n']:>5}{m['accuracy']:>8.3f}"
                  f"{m['macro_f1']:>9.3f}{m['hallucinated_f1']:>9.3f}{recall:>10}")

        print("  Hallucinated recall, tuned cut-points:")
        for population, stats in block["hallucinated_recall_tuned"].items():
            value = "--" if stats["recall"] is None else f"{stats['recall']:.3f}"
            print(f"    {population:<26}n={stats['n']:<4} recall={value}")

        auc = block["discrimination_auc"]
        print("  Separability (pooled, positives = human-annotated Verified):")
        for key in ("vs_synthetic_hallucinated", "vs_human_annotated_hallucinated"):
            stats = auc[key]
            value = "--" if stats["fused_auc"] is None else f"{stats['fused_auc']:.3f}"
            print(f"    {key:<34}n={stats['n_negative']:<4} fused AUC={value}")

        for warning in block["warnings"]:
            print(f"  ! {warning}")

    print("\n* = the number that goes in the paper.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--train", type=Path, default=Path("gold_train_v3.csv"))
    parser.add_argument("--test", type=Path, default=Path("gold_test_v3.csv"))
    parser.add_argument("--config-dir", type=Path, default=Path("."))
    parser.add_argument("--languages", nargs="+", default=["en", "hi"])
    parser.add_argument("--objective", default="macro_f1",
                        choices=["macro_f1", "accuracy", "hallucinated_f1"])
    parser.add_argument("--calibrate", action="store_true",
                        help="print train-fitted cut-points and exit")
    parser.add_argument("--write-thresholds", action="store_true",
                        help="with --calibrate, write thresholds_{lang}.json")
    parser.add_argument("--out", type=Path, default=Path("results/honest_eval.json"))
    args = parser.parse_args()

    weights = {lang: load_weights(lang, args.config_dir) for lang in args.languages}
    train_df = add_fused(load_split(args.train), weights)
    test_df = add_fused(load_split(args.test), weights)

    if args.calibrate:
        for language in args.languages:
            train_lang = train_df[train_df["language"] == language]
            calibration = calibrate(train_lang, objective=args.objective)
            low, high = calibration["cutpoints"]
            print(f"{language}: hallucinated_below={low:.2f} verified_above={high:.2f} "
                  f"(objective={args.objective}, fitted on {calibration['n_train_scored']} "
                  f"train rows, {calibration['n_train_hallucinated']} of them Hallucinated)")
            if calibration["n_train_hallucinated"] < 10:
                print(f"   ! only {calibration['n_train_hallucinated']} Hallucinated training "
                      f"rows: these cut-points are barely identified, treat any test gain "
                      f"as provisional")
            if args.write_thresholds:
                path = write_thresholds_file(language, calibration, args.train, args.config_dir)
                print(f"   wrote {path}")
        return

    report = {
        "train_csv": str(args.train),
        "test_csv": str(args.test),
        "generated_at": date.today().isoformat(),
        "objective": args.objective,
        "languages": {
            language: evaluate_language(language, train_df, test_df, args.objective)
            for language in args.languages
        },
    }
    report["headline"] = {
        language: block["test_tuned_human_annotated_only"]
        for language, block in report["languages"].items()
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print_report(report)
    print(f"\nWritten to {args.out}")


if __name__ == "__main__":
    main()
