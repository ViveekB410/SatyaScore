"""
Ablation study: evaluates the trained CMHSA weights under different
signal-availability configurations on the HELD-OUT test set (never used
for training), and reports accuracy + per-class F1 for each.

This reuses CMHSAScorer's existing renormalization mechanism -- the same
one that already handles a signal being unavailable in production (e.g.
KG linking failing). "Ablating" a signal here means: pretend it's
unavailable for every claim (mask it to None), regardless of whether it
was actually computed, and see how much the verdict quality degrades.
No retraining per configuration -- same trained alpha/beta/gamma weights
throughout, just testing reliance on each signal.

Usage:
    python run_ablation.py --weights weights_en.json --test gold_test.csv --language en
"""

import argparse
import json
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score

from member1_model.cmhsa import CMHSAScorer, ClaimSubScores

CONFIGURATIONS = {
    "full (SemSim+NLI+KG)": {"semsim", "nli", "kg"},
    "SemSim only":          {"semsim"},
    "NLI only":             {"nli"},
    "KG only":              {"kg"},
    "SemSim + NLI":         {"semsim", "nli"},
    "SemSim + KG":          {"semsim", "kg"},
    "NLI + KG":             {"nli", "kg"},
}


def load_weights_from_file(path: str) -> tuple[float, float, float]:
    with open(path) as f:
        w = json.load(f)
    return w["alpha"], w["beta"], w["gamma"]


def masked_sub_scores(row, allowed_signals: set[str]) -> ClaimSubScores:
    return ClaimSubScores(
        claim_id=row["claim_id"],
        sem_sim=row["sem_sim"] if "semsim" in allowed_signals and pd.notna(row["sem_sim"]) else None,
        nli_prob=row["nli_prob"] if "nli" in allowed_signals and pd.notna(row["nli_prob"]) else None,
        kg_conf=row["kg_conf"] if "kg" in allowed_signals and pd.notna(row["kg_conf"]) else None,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True, help="JSON file with trained alpha/beta/gamma")
    parser.add_argument("--test", required=True, help="held-out test CSV (must have gold_verdict)")
    parser.add_argument("--language", required=True)
    args = parser.parse_args()

    alpha, beta, gamma = load_weights_from_file(args.weights)
    scorer = CMHSAScorer()
    scorer.load_weights(args.language, alpha, beta, gamma)

    df = pd.read_csv(args.test)
    df = df[df["language"] == args.language]
    print(f"Evaluating on {len(df)} held-out test claims (language={args.language})")
    print(f"Weights: alpha={alpha:.3f} beta={beta:.3f} gamma={gamma:.3f}\n")

    results_summary = []

    for config_name, allowed in CONFIGURATIONS.items():
        y_true, y_pred = [], []
        skipped = 0
        for _, row in df.iterrows():
            sub_scores = masked_sub_scores(row, allowed)
            try:
                score = scorer.score_claim(sub_scores, args.language)
            except ValueError:
                skipped += 1
                continue  # zero signals available under this configuration for this row
            y_true.append(row["gold_verdict"])
            y_pred.append(score.verdict.value)

        if not y_true:
            print(f"=== {config_name} === SKIPPED: no claims had any of {allowed} available\n")
            continue

        acc = accuracy_score(y_true, y_pred)
        macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
        hallu_f1 = f1_score(y_true, y_pred, labels=["Hallucinated"], average="macro", zero_division=0)

        print(f"=== {config_name} ===")
        print(f"  Accuracy: {acc:.3f}  |  Macro F1: {macro_f1:.3f}  |  Hallucinated-class F1: {hallu_f1:.3f}")
        print(f"  ({len(y_true)} scored, {skipped} skipped -- no signal available under this config)")
        print(classification_report(y_true, y_pred, zero_division=0))
        print()

        results_summary.append({
            "configuration": config_name, "accuracy": acc, "macro_f1": macro_f1,
            "hallucinated_f1": hallu_f1, "n_scored": len(y_true), "n_skipped": skipped,
        })

    summary_df = pd.DataFrame(results_summary)
    out_path = f"ablation_results_{args.language}.csv"
    summary_df.to_csv(out_path, index=False)
    print(f"Summary table written to {out_path}")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
