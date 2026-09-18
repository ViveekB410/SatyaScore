"""
NLI (Natural Language Inference) entailment scorer — produces the
NLI_prob(c, E) signal for CMHSA.

PRD ref: Section 7.2:
    NLI_prob(c, E) — Entailment probability from a fine-tuned DeBERTa-v3
    NLI model, extended to Hindi via IndicXNLI fine-tuning (0-1).

HONESTY NOTE: the PRD calls for a DeBERTa-v3-large model FINE-TUNED
specifically on MNLI + IndicXNLI (Section 10 tech stack) — that fine-tuning
hasn't happened (it needs the annotated dataset Member 2 is building).
This module uses a pretrained, publicly available multilingual NLI model
(mDeBERTa-v3-base-mnli-xnli) as a working stand-in — it already covers
Hindi via XNLI, so it produces real, meaningful NLI_prob scores today, but
swapping in the project's own fine-tuned checkpoint (once it exists) is a
one-line change to MODEL_NAME below, since the interface stays the same.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

Language = Literal["en", "hi", "mr"]

MODEL_NAME = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
MAX_SEQUENCE_LENGTH = 256


@dataclass
class NLIResult:
    claim_id: str
    entailment_prob: float
    contradiction_prob: float
    neutral_prob: float


class NLIScorer:
    """
    Usage:
        scorer = NLIScorer()
        result = scorer.score(
            claim_id="c1",
            premise="The Ganga river originates at Gangotri glacier in Uttarakhand.",
            hypothesis="The Ganga originates in Gangotri.",
        )
        # result.entailment_prob -> NLI_prob for the CMHSA formula
    """

    def __init__(self, device: str | None = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._tokenizer = None
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            self._tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            self._model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME).to(self.device)
            self._model.eval()

    def score(self, claim_id: str, premise: str, hypothesis: str) -> NLIResult:
        """premise = evidence passage, hypothesis = the claim being checked."""
        self._ensure_loaded()

        inputs = self._tokenizer(
            premise,
            hypothesis,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_SEQUENCE_LENGTH,
        ).to(self.device)

        with torch.no_grad():
            logits = self._model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)[0]

        # This model's label order is entailment/neutral/contradiction —
        # verified against the model card. A different checkpoint (e.g. the
        # project's own fine-tune) may use a different order; check
        # model.config.id2label when swapping MODEL_NAME.
        label_order = self._model.config.id2label
        prob_by_label = {label_order[i].lower(): float(probs[i]) for i in range(len(probs))}

        return NLIResult(
            claim_id=claim_id,
            entailment_prob=prob_by_label.get("entailment", 0.0),
            contradiction_prob=prob_by_label.get("contradiction", 0.0),
            neutral_prob=prob_by_label.get("neutral", 0.0),
        )

    def score_batch(
        self, claim_ids: list[str], premises: list[str], hypotheses: list[str]
    ) -> list[NLIResult]:
        """Batched: a SINGLE forward pass over all (premise, hypothesis) pairs,
        instead of one model call per pair. Same results, ~Nx faster on CPU —
        this is what keeps the pipeline's top-k NLI check affordable."""
        if not claim_ids:
            return []
        self._ensure_loaded()

        inputs = self._tokenizer(
            premises, hypotheses, return_tensors="pt", truncation=True,
            max_length=MAX_SEQUENCE_LENGTH, padding=True,
        ).to(self.device)

        with torch.no_grad():
            probs = torch.softmax(self._model(**inputs).logits, dim=-1)

        label_order = self._model.config.id2label
        idx = {label_order[i].lower(): i for i in range(len(label_order))}
        results = []
        for row, cid in zip(probs, claim_ids):
            results.append(NLIResult(
                claim_id=cid,
                entailment_prob=float(row[idx.get("entailment", 0)]),
                contradiction_prob=float(row[idx.get("contradiction", 2)]),
                neutral_prob=float(row[idx.get("neutral", 1)]),
            ))
        return results
