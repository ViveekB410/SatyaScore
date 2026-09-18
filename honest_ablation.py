"""
honest_ablation.py — the ablation study, reported in a form that does not
mislead.

`results/ablation_results_v3.json` has three problems as a paper table:

  1. Each configuration was scored with the shipped 0.35/0.65 cut-points,
     which were chosen for a three-signal fused score. Dropping a signal
     changes the scale of the fused score, so a configuration can look worse
     purely because the fixed cut-points no longer sit anywhere sensible on
     its distribution. This script refits cut-points per configuration, on
     the training split only, so configurations are compared at each one's
     own best operating point rather than at one arbitrary shared point.

  2. Every number was computed over a test set in which two thirds of the
     English hallucinated claims are synthetic perturbations. Each
     configuration is therefore reported twice here, once over the full test
     split and once over human-annotated claims only.

  3. Four of the seven configurations produce identical predictions, and the
     table gave no indication that this was arithmetic rather than
     coincidence. This script detects identical prediction vectors and says
     so explicitly.

No torch, no network: fusion is recomputed from the CSVs exactly as
CMHSAScorer does it.

Usage:
    python honest_ablation.py
    python honest_ablation.py --mode with_semsim
    python honest_ablation.py --out results/honest_ablation.json --table ablation_table.md
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from honest_eval import (
    CLASS_CODES,
    DEFAULT_CUTPOINTS,
    WEIGHT_FLOOR,
    load_split,
    metrics,
    search_cutpoints,
    verdict,
)

CONFIGS = {
    "Full (S+N+KG)": {"semsim", "nli", "kg"},
    "SemSim only": {"semsim"},
    "NLI only": {"nli"},
    "SemSim + NLI": {"semsim", "nli"},
    "NLI + KG": {"nli", "kg"},
    "SemSim + KG": {"semsim", "kg"},
    "KG only": {"kg"},
}

SIGNAL_COLUMN = {"semsim": "sem_sim", "nli": "nli_prob", "kg": "kg_conf"}
WEIGHT_KEY = {"semsim": "alpha", "nli": "beta", "kg": "gamma"}


def weights_path(language: str, mode: str, config_dir: Path) -> Path:
    """no_semsim uses the shipped weights_{lang}.json; with_semsim uses the
    variant trained with the semsim-votes objective."""
    if mode == "no_semsim":
        candidate = config_dir / f"weights_{language}_no_semsim.json"
        return candidate if candidate.exists() else config_dir / f"weights_{language}.json"
    return config_dir / f"weights_{language}_{mode}.json"


def fuse_config(df: pd.DataFrame, weights: dict, allowed: set[str]) -> pd.Series:
    """Fuse only the allowed signals, renormalising over whichever of them are
    actually present on each row. Mirrors CMHSAScorer.score_claim under
    ablation, where a disabled signal is passed as None."""
    scores = []
    for _, row in df.iterrows():
        active = [
            (max(weights[WEIGHT_KEY[signal]], WEIGHT_FLOOR), row[SIGNAL_COLUMN[signal]])
            for signal in allowed
            if pd.notna(row[SIGNAL_COLUMN[signal]])
        ]
        if not active:
            scores.append(float("nan"))
            continue
        total = sum(w for w, _ in active)
        if total <= 0:
            scores.append(float("nan"))
            continue
        scores.append(float(np.clip(sum((w / total) * v for w, v in active), 0.0, 1.0)))
    return pd.Series(scores, index=df.index)


def fit_cutpoints(train_scores: pd.DataFrame, objective: str) -> tuple[float, float]:
    scored = train_scores[train_scores["fused"].notna()]
    if scored.empty:
        return DEFAULT_CUTPOINTS
    labels = scored["gold_verdict"].map(CLASS_CODES).fillna(-1).to_numpy(dtype=int)
    return search_cutpoints(scored["fused"].to_numpy(dtype=float), labels, objective)


def predictions(df: pd.DataFrame, cutpoints: tuple[float, float]) -> tuple[str, ...]:
    """Prediction vector, keyed for identity comparison between configs."""
    return tuple(
        "unscored" if pd.isna(score) else verdict(score, *cutpoints)
        for score in df["fused"]
    )


def run_language(language: str, mode: str, train_df: pd.DataFrame, test_df: pd.DataFrame,
                 config_dir: Path, objective: str) -> dict:
    with open(weights_path(language, mode, config_dir), encoding="utf-8") as handle:
        weights = json.load(handle)

    train_lang = train_df[train_df["language"] == language]
    test_lang = test_df[test_df["language"] == language]

    results: dict[str, dict] = {}
    prediction_vectors: dict[str, tuple[str, ...]] = {}

    for name, allowed in CONFIGS.items():
        train_scored = train_lang.assign(fused=fuse_config(train_lang, weights, allowed))
        test_scored = test_lang.assign(fused=fuse_config(test_lang, weights, allowed))
        human_only = test_scored[~test_scored["is_synthetic"]]

        if test_scored["fused"].notna().sum() == 0:
            results[name] = {"n_scored": 0, "note": "no claim carried any signal in this configuration"}
            continue

        cutpoints = fit_cutpoints(train_scored, objective)
        results[name] = {
            "cutpoints_fitted_on_train": list(cutpoints),
            "test_all": metrics(test_scored, cutpoints),
            "test_human_annotated_only": metrics(human_only, cutpoints),
            "test_all_shipped_cutpoints": metrics(test_scored, DEFAULT_CUTPOINTS),
        }
        prediction_vectors[name] = predictions(test_scored, cutpoints)

    # Which configurations are the same system wearing different labels.
    groups: list[list[str]] = []
    for name, vector in prediction_vectors.items():
        for group in groups:
            if prediction_vectors[group[0]] == vector:
                group.append(name)
                break
        else:
            groups.append([name])

    for group in groups:
        if len(group) > 1:
            for name in group:
                results[name]["identical_predictions_with"] = [n for n in group if n != name]

    baseline_true = test_lang["gold_verdict"].tolist()
    baseline_pred = ["Verified"] * len(baseline_true)
    from sklearn.metrics import accuracy_score, f1_score
    results["always_verified_baseline"] = {
        "test_all": {
            "n": len(baseline_true),
            "accuracy": round(accuracy_score(baseline_true, baseline_pred), 4),
            "macro_f1": round(f1_score(baseline_true, baseline_pred,
                                       labels=["Hallucinated", "Uncertain", "Verified"],
                                       average="macro", zero_division=0), 4),
            "hallucinated_f1": 0.0,
        }
    }

    return {
        "weights": {k: weights[k] for k in ("alpha", "beta", "gamma")},
        "configurations": results,
        "identical_groups": [group for group in groups if len(group) > 1],
    }


def markdown_table(report: dict) -> str:
    lines = []
    for language, block in report["languages"].items():
        alpha, beta, gamma = (block["weights"][k] for k in ("alpha", "beta", "gamma"))
        lines.append(f"### {language.upper()} "
                     f"(alpha={alpha:.3f}, beta={beta:.3f}, gamma={gamma:.3f})\n")
        lines.append("| Configuration | Cut-points | Acc (all) | Macro-F1 (all) | "
                     "Hallu-F1 (all) | Acc (human) | Hallu-F1 (human) |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for name, result in block["configurations"].items():
            if name == "always_verified_baseline":
                base = result["test_all"]
                lines.append(f"| Always-Verified baseline | n/a | {base['accuracy']:.3f} | "
                             f"{base['macro_f1']:.3f} | 0.000 | n/a | n/a |")
                continue
            if result.get("n_scored") == 0:
                lines.append(f"| {name} | n/a | not scoreable | | | | |")
                continue
            low, high = result["cutpoints_fitted_on_train"]
            all_m, human_m = result["test_all"], result["test_human_annotated_only"]
            lines.append(
                f"| {name} | {low:.2f}/{high:.2f} | {all_m['accuracy']:.3f} | "
                f"{all_m['macro_f1']:.3f} | {all_m['hallucinated_f1']:.3f} | "
                f"{human_m['accuracy']:.3f} | {human_m['hallucinated_f1']:.3f} |"
            )
        for group in block["identical_groups"]:
            lines.append(f"\nIdentical predictions on the test split: {', '.join(group)}.")
        lines.append("")
    lines.append("Cut-points are fitted on the training split separately for each "
                 "configuration, because dropping a signal changes the scale of the "
                 "fused score. The human columns cover the test claims that were "
                 "annotated by hand, excluding synthetic perturbations.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--train", type=Path, default=Path("gold_train_v3.csv"))
    parser.add_argument("--test", type=Path, default=Path("gold_test_v3.csv"))
    parser.add_argument("--config-dir", type=Path, default=Path("."))
    parser.add_argument("--languages", nargs="+", default=["en", "hi"])
    parser.add_argument("--mode", default="no_semsim", choices=["no_semsim", "with_semsim"])
    parser.add_argument("--objective", default="macro_f1",
                        choices=["macro_f1", "accuracy", "hallucinated_f1"])
    parser.add_argument("--out", type=Path, default=Path("results/honest_ablation.json"))
    parser.add_argument("--table", type=Path, default=Path("ablation_table.md"))
    args = parser.parse_args()

    train_df = load_split(args.train)
    test_df = load_split(args.test)

    report = {
        "generated_at": date.today().isoformat(),
        "mode": args.mode,
        "objective": args.objective,
        "train_csv": str(args.train),
        "test_csv": str(args.test),
        "languages": {
            language: run_language(language, args.mode, train_df, test_df,
                                   args.config_dir, args.objective)
            for language in args.languages
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    table = markdown_table(report)
    args.table.write_text(table + "\n", encoding="utf-8")
    print(table)
    print(f"\nWritten to {args.out} and {args.table}")


if __name__ == "__main__":
    main()
