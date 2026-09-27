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


@dataclass
class DocumentSummary:
    """Whole-text result, aggregated from the per-claim verdicts."""
    document_verdict: Verdict
    n_claims: int
    n_verified: int
    n_uncertain: int
    n_hallucinated: int
    supported_fraction: float  # share of claims Verified


# Whole-text rule: a text is Hallucinated when at least this share of its claims
# is Hallucinated. (Earlier rule, changed on request: ANY Hallucinated claim made
# the whole text Hallucinated, so nearly every long text was Hallucinated.)
DOC_HALLUCINATED_SHARE = 1 / 3


def aggregate_document(verdicts: list[Verdict | str]) -> DocumentSummary:
    """Whole-text verdict from the per-claim verdicts, by share:
      - Hallucinated claims >= DOC_HALLUCINATED_SHARE of all claims -> Hallucinated;
      - otherwise any Hallucinated or Uncertain claim -> Uncertain;
      - otherwise (every claim Verified) -> Verified.
    A text containing a hallucinated claim is therefore never Verified: one false
    claim among many true ones cannot average away, as it would with a mean score.
    """
    if not verdicts:
        raise ValueError("aggregate_document needs at least one claim verdict")
    vs = [Verdict(v) for v in verdicts]
    n_v = sum(v is Verdict.VERIFIED for v in vs)
    n_u = sum(v is Verdict.UNCERTAIN for v in vs)
    n_h = sum(v is Verdict.HALLUCINATED for v in vs)
    if n_h and n_h * 3 >= len(vs):  # exact integer form of n_h / n >= 1/3
        doc = Verdict.HALLUCINATED
    elif n_h or n_u:
        doc = Verdict.UNCERTAIN
    else:
        doc = Verdict.VERIFIED
    return DocumentSummary(document_verdict=doc, n_claims=len(vs), n_verified=n_v,
                           n_uncertain=n_u, n_hallucinated=n_h,
                           supported_fraction=n_v / len(vs))


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


# When the knowledge graph gives an answer (supported / contradicted), it decides
# the claim; the weighted fusion is used only when it has none. Measured on the
# round-3 relational pilot (results/round3_kg_decides.md, exploratory): in the 9
# claims where the KG and NLI disagreed by >= 0.5 the KG was right 9 times; AUC
# 0.848 -> 0.872 [-0.000, +0.083] vs 50/50 fusion. Language-neutral: applies to
# any claim the KG can check (English and Hindi relation patterns).
# Known limit: the KG checks one relation; other facts in the same claim are not
# checked when it decides.
KG_DECIDES = True
KG_NOTE = "decided by the knowledge graph (Wikidata)"


class CMHSAScorer:
    """
    Fuses SemSim, NLI_prob, and KG_conf into one HalluScore per claim, with
    language-specific weight sets and support for ablation mode (dropping
    one or more signals and re-normalising over whatever remains active).
    If KG_DECIDES and the KG answered, the KG answer is the score.
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

        note = None
        if KG_DECIDES and "kg" in active:
            hallu_score = float(sub_scores.kg_conf)
            note = KG_NOTE
        else:
            weight_sum = sum(w for w, _ in active.values())
            hallu_score = sum((w / weight_sum) * v for w, v in active.values())
        hallu_score = float(np.clip(hallu_score, 0.0, 1.0))

        return ClaimScore(
            claim_id=sub_scores.claim_id,
            hallu_score=hallu_score,
            verdict=self._verdict(hallu_score),
            active_signals=list(active.keys()),
            note=note,
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
