"""
Trains language-specific (alpha, beta, gamma) weights for CMHSA.

PRD ref: Section 7.2 — "learned via a softmax-constrained linear model
... fit on annotated training data by minimizing cross-entropy against
gold verdict labels — not plain unconstrained logistic regression."

Expects a training CSV with columns:
    claim_id, language, sem_sim, nli_prob, kg_conf, gold_verdict
where gold_verdict in {Hallucinated, Uncertain, Verified}.

For training we collapse gold_verdict to a binary target
(Hallucinated=0 / not-hallucinated=1) so the fused score can be trained
with binary cross-entropy — Uncertain claims are treated as a soft label
(0.5) rather than dropped, so the model still learns from them.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import torch
import torch.nn as nn

from member1_model.cmhsa import Language, _SoftmaxWeightModel

GOLD_TO_TARGET = {
    "Hallucinated": 0.0,
    "Uncertain": 0.5,
    "Verified": 1.0,
}


def _parse_signal(value: str | None) -> float:
    """A missing/blank signal becomes NaN so it can be masked out per-row
    during training. kg_conf in particular is very often blank (Wikidata /
    relation-phrase coverage is sparse); treating blank as 0.0 would be a
    silent lie — 0.0 means "maximally hallucinated on this signal", not
    "this signal is unavailable"."""
    if value is None or value == "":
        return float("nan")
    return float(value)


def load_training_rows(csv_path: Path, language: Language, semsim_votes: bool = True):
    """Returns (X, mask, y, verdicts): X is (N, 3) of [sem_sim, nli_prob,
    kg_conf] with NaN for any absent signal, mask is (N, 3) bool (True where
    present), y is (N,) the soft target, and verdicts is the raw gold_verdict
    string per row (used to build class-balanced sample weights -- see
    train_language_weights). Rows without a gold_verdict, or with no signal at
    all, are skipped.

    semsim_votes=False (the recommended default -- see --no-semsim-vote in
    main()) masks sem_sim out of every row for TRAINING purposes only, using
    the exact same mask/renormalise mechanism that already correctly handles
    kg_conf's 0% coverage. This does NOT touch the sem_sim column itself (it's
    still read and would remain available for the ablation study / research
    tables) -- it only stops alpha from receiving gradient, so it settles
    near its prior instead of dominating the fused score.

    WHY: ablation evidence (see conversation/PR notes) showed NLI alone
    reaches Hallucinated-F1=0.38, but blending in SemSim collapses that to
    0.00 -- SemSim measures topical relevance (Cohen's d ~0.14 vs actual
    truth), not veracity, and linearly averaging a near-random signal with a
    working one dilutes the working one. SemSim's real job (deciding whether
    there's any relevant evidence at all) is untouched -- that gate lives in
    pipeline.py's MIN_RELEVANCE_THRESHOLD check, entirely separate from this
    training step."""
    sub_scores, targets, verdicts = [], [], []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["language"] != language:
                continue
            if not row.get("gold_verdict"):
                continue
            signals = [
                _parse_signal(row.get("sem_sim")) if semsim_votes else float("nan"),
                _parse_signal(row.get("nli_prob")),
                _parse_signal(row.get("kg_conf")),
            ]
            if all(s != s for s in signals):  # all NaN -> nothing to learn from
                continue
            sub_scores.append(signals)
            targets.append(GOLD_TO_TARGET[row["gold_verdict"]])
            verdicts.append(row["gold_verdict"])
    if not sub_scores:
        raise ValueError(f"No training rows found for language={language} in {csv_path}")
    X = torch.tensor(sub_scores, dtype=torch.float32)
    mask = ~torch.isnan(X)
    return X, mask, torch.tensor(targets, dtype=torch.float32), verdicts


def _fused_scores(model: _SoftmaxWeightModel, X: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Fuse whichever signals are present per row, renormalising the softmax
    weights over just those signals. This is exactly CMHSAScorer.score_claim's
    behaviour (member1_model/cmhsa.py) — keeping training and inference fusion
    identical, so a learned weight triple means the same thing at serving time
    even when some signals are absent. For a row with all three signals present
    the denominator is alpha+beta+gamma = 1, so this reduces to the plain
    weighted sum."""
    w = model.weights()                          # (3,) softmax weights
    weighted = mask.float() * w                  # (N, 3), zero where absent
    denom = weighted.sum(dim=1).clamp_min(1e-8)  # (N,)
    x = torch.nan_to_num(X, nan=0.0)             # masked entries contribute 0
    return (weighted * x).sum(dim=1) / denom


def train_language_weights(
    csv_path: Path,
    language: Language,
    epochs: int = 300,
    lr: float = 0.05,
    weight_decay: float = 1e-4,
    semsim_votes: bool = True,
) -> tuple[float, float, float]:
    X, mask, y, verdicts = load_training_rows(csv_path, language, semsim_votes=semsim_votes)

    # Honest diagnostic: a signal absent from EVERY row gets no loss gradient,
    # so its weight is NOT learned from data (it only drifts under weight
    # decay). With the current dataset kg_conf is ~0% present, which means
    # gamma is effectively unlearned and the KG ablation has nothing to show —
    # surface that here instead of letting it hide inside a plausible-looking
    # weight triple.
    coverage = mask.float().mean(dim=0).tolist()
    for name, frac in zip(("alpha/sem_sim", "beta/nli_prob", "gamma/kg_conf"), coverage):
        if frac == 0.0:
            print(f"[{language}] WARNING: {name} present in 0% of rows — its weight "
                  f"cannot be learned from this data (stays near its prior).")
        elif frac < 0.2:
            print(f"[{language}] NOTE: {name} present in only {frac * 100:.0f}% of rows — weakly constrained.")

    # Class-balanced sample weights: preds is a RAW weighted average of the
    # signals (clamped to (0,1)), not passed through a sigmoid, fed directly
    # into unweighted BCELoss. With 78% Verified rows, plain BCELoss makes it
    # "cheap" for gradient descent to lean on whichever signal's raw values
    # happen to sit closer to the majority class's target -- independent of
    # whether that signal actually separates Hallucinated from Verified.
    # Inverse-frequency weighting makes minority-class rows (Hallucinated,
    # Uncertain) count as much in total loss as the majority Verified rows.
    from collections import Counter
    counts = Counter(verdicts)
    n = len(verdicts)
    num_classes = len(counts)
    class_weight = {cls: n / (num_classes * count) for cls, count in counts.items()}
    sample_weight = torch.tensor([class_weight[v] for v in verdicts], dtype=torch.float32)
    print(f"[{language}] class counts: {dict(counts)} -> per-class weight: "
          f"{ {k: round(v, 3) for k, v in class_weight.items()} }")

    model = _SoftmaxWeightModel()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    loss_fn = nn.BCELoss(weight=sample_weight)

    for epoch in range(epochs):
        optimizer.zero_grad()
        preds = _fused_scores(model, X, mask).clamp(1e-6, 1 - 1e-6)  # avoid log(0) in BCE
        loss = loss_fn(preds, y)
        loss.backward()
        optimizer.step()

        if epoch % 50 == 0 or epoch == epochs - 1:
            alpha, beta, gamma = model.weights().tolist()
            print(
                f"[{language}] epoch {epoch:4d}  loss={loss.item():.4f}  "
                f"alpha={alpha:.3f} beta={beta:.3f} gamma={gamma:.3f}"
            )

    alpha, beta, gamma = model.weights().tolist()

    if not semsim_votes:
        # CRITICAL: don't trust gradient descent to have pushed alpha toward
        # zero -- when gamma ALSO has 0% coverage (true throughout this
        # project), masking alpha too leaves only ONE signal with any real
        # data. cmhsa.py's renormalization then divides a single active
        # signal's weighted contribution by that same weight, which cancels
        # out exactly regardless of the weight's value -- the loss becomes
        # completely independent of alpha/beta/gamma, so training is
        # gradient-free and settles at the uniform (1/3, 1/3, 1/3) prior via
        # weight decay alone (confirmed empirically: flat loss curve, no
        # movement across 300 epochs). An arbitrary alpha~0.33 would then
        # silently re-admit SemSim at inference, since sem_sim (unlike
        # kg_conf) IS almost always present in production -- undoing the
        # whole point of excluding it. Force it to an EXACT zero instead:
        # 1.0 * 0.0 = 0.0 always, robustly excluding SemSim's contribution
        # even when a real sem_sim value is passed at serving time.
        alpha = 0.0
        total = beta + gamma
        beta, gamma = beta / total, gamma / total
        print(f"[{language}] --no-semsim-vote: forcing alpha=0.000 exactly "
              f"(training alone can only push it toward, not to, zero) -- "
              f"renormalized: beta={beta:.3f} gamma={gamma:.3f}")

    return alpha, beta, gamma


def main():
    parser = argparse.ArgumentParser(description="Train CMHSA fusion weights per language.")
    parser.add_argument("--csv", type=Path, required=True, help="Path to annotated training CSV")
    parser.add_argument("--languages", nargs="+", default=["en", "hi"], help="Languages to train")
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--lr", type=float, default=0.05)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("."),
        help="Directory to write weights_<lang>.json into (previously weights were "
             "only printed to console and never persisted anywhere -- fixed here "
             "so the API, ablation study, etc. can actually load a trained model)",
    )
    parser.add_argument(
        "--semsim-vote", dest="semsim_votes", action="store_true",
        help="Let SemSim participate in the weighted fusion vote (the ORIGINAL "
             "3-signal design). Not recommended by default -- ablation evidence "
             "showed NLI alone reaches Hallucinated-F1=0.38 but blending in "
             "SemSim collapses it to 0.00 (SemSim measures topical relevance, "
             "not truth; Cohen's d ~0.14 vs actual verdict). Pass this flag only "
             "to reproduce/compare against the original full-fusion behavior.",
    )
    parser.set_defaults(semsim_votes=False)
    args = parser.parse_args()

    if not args.semsim_votes:
        print("NOTE: training with --no-semsim-vote behavior (default) -- SemSim is "
              "excluded from the fusion vote and will train near its prior, same "
              "mechanism already used for kg_conf's 0% coverage. Pass --semsim-vote "
              "to restore the original 3-signal design for comparison.\n")

    results = {}
    for lang in args.languages:
        print(f"\n=== Training weights for language: {lang} ===")
        results[lang] = train_language_weights(
            args.csv, lang, epochs=args.epochs, lr=args.lr, semsim_votes=args.semsim_votes,
        )

    print("\nFinal learned weights (alpha=SemSim, beta=NLI, gamma=KG):")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for lang, (a, b, g) in results.items():
        print(f"  {lang}: alpha={a:.3f}  beta={b:.3f}  gamma={g:.3f}  (sum={a+b+g:.3f})")
        out_path = args.output_dir / f"weights_{lang}.json"
        with open(out_path, "w") as f:
            json.dump({"language": lang, "alpha": a, "beta": b, "gamma": g,
                       "semsim_votes": args.semsim_votes}, f, indent=2)
        print(f"    -> saved to {out_path}")


if __name__ == "__main__":
    main()
