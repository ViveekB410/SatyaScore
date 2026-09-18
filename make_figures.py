"""
make_figures.py — the three figures the results chapter needs, generated from
the CSVs so they regenerate with the data.

    figures/fig_roc_synthetic_vs_human.png
        ROC for the composite score with the positive class held fixed at
        human-annotated Verified claims, once against synthetic perturbations
        and once against human-annotated hallucinations. The gap between the
        curves is the evaluation-validity finding.

    figures/fig_score_distributions.png
        Distribution of the composite score for the three populations that
        matter: human-annotated Verified, human-annotated Hallucinated, and
        synthetic perturbations. Shows that the synthetic claims sit in a
        separate mode while the human-annotated hallucinations sit on top of
        the verified claims.

    figures/fig_threshold_sweep.png
        Overall accuracy and human-annotated hallucination recall as the
        lower cut-point moves. Shows that the two cannot be improved at the
        same time on the current score.

Usage:
    python make_figures.py
    python make_figures.py --language hi --outdir figures
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score, roc_curve

from honest_eval import add_fused, load_split, load_weights, verdict

FIGSIZE = (7.0, 4.2)
DPI = 200


def populations(df: pd.DataFrame, language: str) -> dict[str, pd.DataFrame]:
    subset = df[(df["language"] == language) & df["fused"].notna()]
    return {
        "verified_human": subset[(subset["gold_verdict"] == "Verified") & ~subset["is_synthetic"]],
        "hallucinated_human": subset[(subset["gold_verdict"] == "Hallucinated") & ~subset["is_synthetic"]],
        "hallucinated_synthetic": subset[(subset["gold_verdict"] == "Hallucinated") & subset["is_synthetic"]],
    }


def figure_roc(groups: dict[str, pd.DataFrame], language: str, outdir: Path) -> Path | None:
    positives = groups["verified_human"]
    if positives.empty:
        return None

    fig, ax = plt.subplots(figsize=FIGSIZE)
    plotted = False
    for key, label in (("hallucinated_synthetic", "Synthetic perturbations"),
                       ("hallucinated_human", "Human-annotated hallucinations")):
        negatives = groups[key]
        if negatives.empty:
            continue
        y = np.r_[np.ones(len(positives)), np.zeros(len(negatives))]
        scores = np.r_[positives["fused"], negatives["fused"]]
        fpr, tpr, _ = roc_curve(y, scores)
        auc = roc_auc_score(y, scores)
        ax.plot(fpr, tpr, label=f"{label} (n={len(negatives)}, AUC={auc:.3f})")
        plotted = True
    if not plotted:
        plt.close(fig)
        return None

    ax.plot([0, 1], [0, 1], linestyle=":", color="grey", label="Chance")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title(f"Separating verified claims from hallucinations ({language.upper()})\n"
                 f"positive class held fixed at {len(positives)} human-annotated verified claims")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = outdir / "fig_roc_synthetic_vs_human.png"
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def figure_distributions(groups: dict[str, pd.DataFrame], language: str, outdir: Path) -> Path:
    fig, ax = plt.subplots(figsize=FIGSIZE)
    bins = np.linspace(0, 1, 21)
    for key, label in (("verified_human", "Verified (human-annotated)"),
                       ("hallucinated_human", "Hallucinated (human-annotated)"),
                       ("hallucinated_synthetic", "Hallucinated (synthetic perturbation)")):
        group = groups[key]
        if group.empty:
            continue
        ax.hist(group["fused"], bins=bins, density=True, histtype="step", linewidth=1.8,
                label=f"{label}, n={len(group)}, mean={group['fused'].mean():.3f}")
    ax.set_xlabel("Composite score")
    ax.set_ylabel("Density")
    ax.set_title(f"Composite score by claim population ({language.upper()})")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = outdir / "fig_score_distributions.png"
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def figure_threshold_sweep(test_df: pd.DataFrame, language: str, upper: float,
                           outdir: Path) -> Path:
    subset = test_df[(test_df["language"] == language) & test_df["fused"].notna()]
    human = subset[~subset["is_synthetic"]]
    human_hallucinated = human[human["gold_verdict"] == "Hallucinated"]

    # Sweep the lower cut-point across the whole range. The upper cut-point
    # is held at its fitted value but never allowed below the lower one, so
    # the sweep passes through the shipped 0.35 setting instead of stopping
    # short of it.
    grid = np.round(np.arange(0.0, 1.001, 0.01), 2)
    accuracy, recall_human, recall_synthetic = [], [], []
    synthetic_hallucinated = subset[subset["is_synthetic"] &
                                    (subset["gold_verdict"] == "Hallucinated")]

    for low in grid:
        high = max(low, upper)
        predictions = [verdict(s, low, high) for s in subset["fused"]]
        accuracy.append(accuracy_score(subset["gold_verdict"], predictions))
        recall_human.append(
            np.mean([verdict(s, low, high) == "Hallucinated"
                     for s in human_hallucinated["fused"]])
            if len(human_hallucinated) else np.nan)
        recall_synthetic.append(
            np.mean([verdict(s, low, high) == "Hallucinated"
                     for s in synthetic_hallucinated["fused"]])
            if len(synthetic_hallucinated) else np.nan)

    fig, ax = plt.subplots(figsize=FIGSIZE)
    ax.plot(grid, accuracy, label="Overall accuracy (all test claims)")
    if len(human_hallucinated):
        ax.plot(grid, recall_human, label=f"Recall, human-annotated hallucinations "
                                          f"(n={len(human_hallucinated)})")
    if len(synthetic_hallucinated):
        ax.plot(grid, recall_synthetic, linestyle="--",
                label=f"Recall, synthetic perturbations (n={len(synthetic_hallucinated)})")
    ax.axvline(0.35, color="grey", linestyle=":", linewidth=1)
    ax.annotate("shipped 0.35", xy=(0.35, 0.02), fontsize=8, color="grey",
                rotation=90, va="bottom", ha="right")
    ax.set_xlabel(f"Lower cut-point (upper cut-point at max(lower, {upper:.2f}))")
    ax.set_ylabel("Score")
    ax.set_title(f"Accuracy against hallucination recall ({language.upper()})")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = outdir / "fig_threshold_sweep.png"
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--train", type=Path, default=Path("gold_train_v3.csv"))
    parser.add_argument("--test", type=Path, default=Path("gold_test_v3.csv"))
    parser.add_argument("--config-dir", type=Path, default=Path("."))
    parser.add_argument("--language", default="en")
    parser.add_argument("--upper-cutpoint", type=float, default=None,
                        help="defaults to the value in thresholds_{lang}.json, else 0.65")
    parser.add_argument("--outdir", type=Path, default=Path("figures"))
    args = parser.parse_args()

    weights = {args.language: load_weights(args.language, args.config_dir)}
    train_df = add_fused(load_split(args.train), weights)
    test_df = add_fused(load_split(args.test), weights)
    pooled = pd.concat([train_df, test_df], ignore_index=True)

    upper = args.upper_cutpoint
    if upper is None:
        thresholds_path = args.config_dir / f"thresholds_{args.language}.json"
        if thresholds_path.exists():
            import json
            upper = json.loads(thresholds_path.read_text())["verified_above"]
        else:
            upper = 0.65

    args.outdir.mkdir(parents=True, exist_ok=True)
    groups = populations(pooled, args.language)

    written = [
        figure_roc(groups, args.language, args.outdir),
        figure_distributions(groups, args.language, args.outdir),
        figure_threshold_sweep(test_df, args.language, upper, args.outdir),
    ]
    for path in written:
        if path is not None:
            print(f"wrote {path}")


if __name__ == "__main__":
    main()
