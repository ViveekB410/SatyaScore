"""
Annotation schema for the SatyaScore benchmark dataset.

PRD refs: Section 11.2 (dataset creation steps), Section 11.3 (guidelines),
FR-07 (benchmark dataset requirements).

Step 4 — Expert Annotation: 2-3 annotators label each claim as
    Verified / Uncertain / Hallucinated, with an evidence URL.
Step 6 — IAA Calculation: resolve disagreements by majority vote or
    adjudication.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

Language = Literal["en", "hi", "mr"]


class Verdict(str, Enum):
    VERIFIED = "Verified"
    UNCERTAIN = "Uncertain"
    HALLUCINATED = "Hallucinated"


@dataclass
class Claim:
    """One atomic claim extracted from an LLM response (Section 11.2 Step 3)."""
    claim_id: str
    text: str
    language: Language
    source_llm: str  # e.g. "gpt-4", "llama-3", "gemini" (Section 11.2 Step 2)
    source_query: str


@dataclass
class Annotation:
    """One annotator's judgement on one claim."""
    claim_id: str
    annotator_id: str
    verdict: Verdict
    evidence_url: str | None = None


@dataclass
class AdjudicatedLabel:
    claim_id: str
    gold_verdict: Verdict
    method: Literal["unanimous", "majority", "adjudicated"]
    annotator_votes: dict[str, Verdict] = field(default_factory=dict)
    needs_manual_adjudication: bool = False


class Adjudicator:
    """
    Resolves multiple annotators' labels for a claim into one gold label.

    Rule: unanimous -> that label. Clear majority (more votes for one
    label than all others combined) -> majority label. A tie (e.g. 2
    annotators split 1-1, or 3 annotators split evenly across all three
    verdicts) is NOT auto-resolved — it's flagged for a human adjudicator,
    per Section 11.2 Step 6 ("Resolve disagreements by majority vote or
    adjudication").
    """

    def resolve(self, claim_id: str, annotations: list[Annotation]) -> AdjudicatedLabel:
        if not annotations:
            raise ValueError(f"No annotations provided for claim {claim_id}")
        if any(a.claim_id != claim_id for a in annotations):
            raise ValueError("All annotations must belong to the same claim_id")

        votes = {a.annotator_id: a.verdict for a in annotations}
        tally = Counter(votes.values())
        top_verdict, top_count = tally.most_common(1)[0]

        if len(tally) == 1:
            return AdjudicatedLabel(claim_id, top_verdict, "unanimous", votes)

        # Clear majority = top choice strictly beats the sum of all others.
        other_votes = sum(tally.values()) - top_count
        if top_count > other_votes:
            return AdjudicatedLabel(claim_id, top_verdict, "majority", votes)

        # No clear majority — flag for manual adjudication rather than
        # silently picking a winner (e.g. via Counter's arbitrary tie order).
        return AdjudicatedLabel(
            claim_id, top_verdict, "adjudicated", votes, needs_manual_adjudication=True
        )

    def resolve_batch(
        self, annotations_by_claim: dict[str, list[Annotation]]
    ) -> list[AdjudicatedLabel]:
        return [self.resolve(cid, anns) for cid, anns in annotations_by_claim.items()]


def dataset_balance_check(labels: list[AdjudicatedLabel]) -> dict[str, float]:
    """
    FR-07: dataset should be balanced ~40% Hallucinated / 30% Uncertain /
    30% Verified. Returns the actual proportions so annotation leads can
    check drift against that target as data comes in.
    """
    if not labels:
        return {}
    counts = Counter(label.gold_verdict for label in labels)
    total = len(labels)
    return {verdict.value: counts.get(verdict, 0) / total for verdict in Verdict}
