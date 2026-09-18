"""
Composite Multilingual Hallucination Scoring Algorithm (CMHSA).

PRD refs: Section 7.2 (patent core), FR-04
    HalluScore(c) = alpha * SemSim(c, E) + beta * NLI_prob(c, E) + gamma * KG_conf(c, G)

Weights (alpha, beta, gamma) are language-specific and learned via a
softmax-constrained linear model — NOT plain unconstrained logistic
regression — so that alpha + beta + gamma = 1 by construction.

Verdict thresholds: < 0.35 Hallucinated | 0.35-0.65 Uncertain | > 0.65 Verified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

import numpy as np
import torch
import torch.nn as nn

Language = Literal["en", "hi", "mr"]
Signal = Literal["semsim", "nli", "kg"]

HALLUCINATED_THRESHOLD = 0.35
VERIFIED_THRESHOLD = 0.65


class Verdict(str, Enum):
    HALLUCINATED = "Hallucinated"
    UNCERTAIN = "Uncertain"
    VERIFIED = "Verified"


@dataclass
class ClaimSubScores:
    claim_id: str
    sem_sim: float | None  # None => signal unavailable (ablation mode or retrieval failure)
    nli_prob: float | None
    kg_conf: float | None


@dataclass
class ClaimScore:
    claim_id: str
    hallu_score: float
    verdict: Verdict
    active_signals: list[Signal] = field(default_factory=list)
    note: str | None = None  # optional context for fallback verdicts, e.g.
                              # "insufficient evidence" (see pipeline.py) —
                              # None for normal fully-scored claims, so this
                              # is backward compatible with existing callers


class _SoftmaxWeightModel(nn.Module):
    """
    Learns raw logits (a, b, g) such that
        (alpha, beta, gamma) = softmax(a, b, g)
    This enforces alpha + beta + gamma = 1 by construction, unlike plain
    logistic regression over the three sub-scores, which has no such
    constraint and can produce negative or unbounded coefficients.
    """

    def __init__(self):
        super().__init__()
        # Initialise close to equal weighting.
        self.logits = nn.Parameter(torch.zeros(3))

    def weights(self) -> torch.Tensor:
        return torch.softmax(self.logits, dim=0)  # (alpha, beta, gamma)

    def forward(self, sub_scores: torch.Tensor) -> torch.Tensor:
        # sub_scores: (N, 3) -> (N,) fused score in [0, 1]
        w = self.weights()
        return sub_scores @ w


class CMHSAScorer:
    """
    Fuses SemSim, NLI_prob, and KG_conf into one HalluScore per claim, with
    language-specific weight sets and support for ablation mode (dropping
    one or more signals and re-normalising over whatever remains active).
    """

    def __init__(self):
        # Per-language weight models — trained separately (see train_weights.py).
        self._models: dict[Language, _SoftmaxWeightModel] = {
            "en": _SoftmaxWeightModel(),
            "hi": _SoftmaxWeightModel(),
            "mr": _SoftmaxWeightModel(),
        }

    def load_weights(self, language: Language, alpha: float, beta: float, gamma: float) -> None:
        """Set trained weights directly (e.g. after loading a checkpoint)."""
        total = alpha + beta + gamma
        if not np.isclose(total, 1.0, atol=1e-3):
            raise ValueError(f"alpha+beta+gamma must sum to 1, got {total}")
        # Recover logits that produce this softmax (up to an additive constant).
        probs = torch.tensor([alpha, beta, gamma], dtype=torch.float32).clamp_min(1e-8)
        logits = torch.log(probs)
        with torch.no_grad():
            self._models[language].logits.copy_(logits)

    def get_weights(self, language: Language) -> tuple[float, float, float]:
        w = self._models[language].weights().detach().numpy()
        return float(w[0]), float(w[1]), float(w[2])

    def score_claim(self, sub_scores: ClaimSubScores, language: Language) -> ClaimScore:
        """
        Compute HalluScore for one claim. Any sub-score that is None (either
        because ablation mode disabled that signal, or retrieval/verification
        failed) is excluded, and the remaining weights are re-normalised so
        they still sum to 1 — this preserves the alpha+beta+gamma=1 invariant
        even in degraded/ablation conditions.
        """
        alpha, beta, gamma = self.get_weights(language)
        raw = {"semsim": (alpha, sub_scores.sem_sim),
               "nli": (beta, sub_scores.nli_prob),
               "kg": (gamma, sub_scores.kg_conf)}

        active = {k: (w, v) for k, (w, v) in raw.items() if v is not None}
        if not active:
            raise ValueError(f"claim {sub_scores.claim_id}: no active signals to score")

        weight_sum = sum(w for w, _ in active.values())
        hallu_score = sum((w / weight_sum) * v for w, v in active.values())
        hallu_score = float(np.clip(hallu_score, 0.0, 1.0))

        return ClaimScore(
            claim_id=sub_scores.claim_id,
            hallu_score=hallu_score,
            verdict=self._verdict(hallu_score),
            active_signals=list(active.keys()),
        )

    def score_batch(
        self, batch: list[ClaimSubScores], language: Language
    ) -> list[ClaimScore]:
        return [self.score_claim(s, language) for s in batch]

    @staticmethod
    def _verdict(score: float) -> Verdict:
        if score < HALLUCINATED_THRESHOLD:
            return Verdict.HALLUCINATED
        if score > VERIFIED_THRESHOLD:
            return Verdict.VERIFIED
        return Verdict.UNCERTAIN
