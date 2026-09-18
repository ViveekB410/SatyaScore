"""
Inter-annotator agreement calculation.

PRD refs: Section 11.2 Step 6 ("Compute Cohen's Kappa between annotator
pairs"), Section 5.2 (target kappa >= 0.65, stretch >= 0.75, revised down
from 0.70 based on Mu-SHROOM's documented annotator disagreement), and
Section 3 / 11.2 Step 5 (pilot round of 50-100 claims before committing
to full-scale annotation, specifically to calibrate expectations early).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from sklearn.metrics import cohen_kappa_score

from member2_data.annotation_schema import Annotation, Verdict

PILOT_ROUND_MIN_CLAIMS = 50
PILOT_ROUND_MAX_CLAIMS = 100
TARGET_KAPPA_MINIMUM = 0.65
TARGET_KAPPA_STRETCH = 0.75


@dataclass
class PairwiseAgreement:
    annotator_a: str
    annotator_b: str
    kappa: float
    n_shared_claims: int
    meets_minimum_target: bool


@dataclass
class IAAReport:
    pairwise: list[PairwiseAgreement]
    mean_kappa: float
    meets_minimum_target: bool
    meets_stretch_target: bool
    is_pilot_round: bool
    recommendation: str


def compute_pairwise_kappa(
    annotations_by_claim: dict[str, list[Annotation]],
) -> list[PairwiseAgreement]:
    """
    Builds aligned label sequences for every pair of annotators who share
    at least one annotated claim, and computes Cohen's Kappa for each pair.
    """
    # Reshape: annotator_id -> {claim_id: verdict}
    by_annotator: dict[str, dict[str, Verdict]] = {}
    for claim_id, annotations in annotations_by_claim.items():
        for ann in annotations:
            by_annotator.setdefault(ann.annotator_id, {})[claim_id] = ann.verdict

    results = []
    for annotator_a, annotator_b in combinations(sorted(by_annotator), 2):
        shared_claims = sorted(set(by_annotator[annotator_a]) & set(by_annotator[annotator_b]))
        if len(shared_claims) < 2:
            continue  # not enough overlap to compute a meaningful kappa

        labels_a = [by_annotator[annotator_a][c].value for c in shared_claims]
        labels_b = [by_annotator[annotator_b][c].value for c in shared_claims]
        kappa = cohen_kappa_score(labels_a, labels_b)

        results.append(
            PairwiseAgreement(
                annotator_a=annotator_a,
                annotator_b=annotator_b,
                kappa=kappa,
                n_shared_claims=len(shared_claims),
                meets_minimum_target=kappa >= TARGET_KAPPA_MINIMUM,
            )
        )
    return results


def build_iaa_report(
    annotations_by_claim: dict[str, list[Annotation]],
) -> IAAReport:
    total_claims = len(annotations_by_claim)
    is_pilot = total_claims <= PILOT_ROUND_MAX_CLAIMS

    pairwise = compute_pairwise_kappa(annotations_by_claim)
    if not pairwise:
        return IAAReport(
            pairwise=[],
            mean_kappa=0.0,
            meets_minimum_target=False,
            meets_stretch_target=False,
            is_pilot_round=is_pilot,
            recommendation=(
                "Not enough overlapping claims between annotators to compute "
                "agreement. Ensure multiple annotators label the same claims "
                "(not a disjoint split) for at least the pilot round."
            ),
        )

    mean_kappa = sum(p.kappa for p in pairwise) / len(pairwise)
    meets_min = mean_kappa >= TARGET_KAPPA_MINIMUM
    meets_stretch = mean_kappa >= TARGET_KAPPA_STRETCH

    if is_pilot and total_claims < PILOT_ROUND_MIN_CLAIMS:
        recommendation = (
            f"Only {total_claims} claims annotated so far — the PRD's pilot "
            f"round (Section 11.2 Step 5) calls for {PILOT_ROUND_MIN_CLAIMS}-"
            f"{PILOT_ROUND_MAX_CLAIMS} claims before drawing conclusions about "
            "guideline quality. Keep annotating before adjusting guidelines."
        )
    elif is_pilot and not meets_min:
        recommendation = (
            f"Pilot round mean kappa={mean_kappa:.3f}, below the {TARGET_KAPPA_MINIMUM} "
            "target. Per Section 3's practical guidance, this is the moment to "
            "refine annotation guidelines BEFORE committing to full-scale "
            "annotation — not after 3,000 claims are already labelled."
        )
    elif is_pilot and meets_min:
        recommendation = (
            f"Pilot round mean kappa={mean_kappa:.3f} meets the {TARGET_KAPPA_MINIMUM} "
            "target. Guidelines look workable — safe to proceed to full-scale "
            "annotation."
        )
    elif not meets_min:
        recommendation = (
            f"Full-scale mean kappa={mean_kappa:.3f} is below target. Consider "
            "a guideline-refinement + re-annotation pass on the worst-agreeing "
            "claim categories before finalizing the dataset."
        )
    else:
        recommendation = f"Mean kappa={mean_kappa:.3f} meets target. Dataset agreement is solid."

    return IAAReport(
        pairwise=pairwise,
        mean_kappa=mean_kappa,
        meets_minimum_target=meets_min,
        meets_stretch_target=meets_stretch,
        is_pilot_round=is_pilot,
        recommendation=recommendation,
    )
