from member2_data.annotation_schema import Annotation, Verdict
from member2_data.iaa import build_iaa_report, compute_pairwise_kappa


def _make_annotations_by_claim(rows):
    """rows: list of (claim_id, {annotator_id: verdict})"""
    result = {}
    for claim_id, votes in rows:
        result[claim_id] = [
            Annotation(claim_id=claim_id, annotator_id=aid, verdict=v)
            for aid, v in votes.items()
        ]
    return result


def test_perfect_agreement_gives_kappa_one():
    rows = [
        ("c1", {"alice": Verdict.VERIFIED, "bob": Verdict.VERIFIED}),
        ("c2", {"alice": Verdict.HALLUCINATED, "bob": Verdict.HALLUCINATED}),
        ("c3", {"alice": Verdict.UNCERTAIN, "bob": Verdict.UNCERTAIN}),
        ("c4", {"alice": Verdict.VERIFIED, "bob": Verdict.VERIFIED}),
    ]
    annotations_by_claim = _make_annotations_by_claim(rows)
    pairwise = compute_pairwise_kappa(annotations_by_claim)
    assert len(pairwise) == 1
    assert pairwise[0].kappa == 1.0
    assert pairwise[0].meets_minimum_target


def test_disagreement_lowers_kappa():
    rows = [
        ("c1", {"alice": Verdict.VERIFIED, "bob": Verdict.HALLUCINATED}),
        ("c2", {"alice": Verdict.HALLUCINATED, "bob": Verdict.VERIFIED}),
        ("c3", {"alice": Verdict.UNCERTAIN, "bob": Verdict.HALLUCINATED}),
        ("c4", {"alice": Verdict.VERIFIED, "bob": Verdict.UNCERTAIN}),
    ]
    annotations_by_claim = _make_annotations_by_claim(rows)
    pairwise = compute_pairwise_kappa(annotations_by_claim)
    assert pairwise[0].kappa < 0.65
    assert not pairwise[0].meets_minimum_target


def test_pilot_round_flagged_when_under_50_claims():
    rows = [
        (f"c{i}", {"alice": Verdict.VERIFIED, "bob": Verdict.VERIFIED}) for i in range(10)
    ]
    annotations_by_claim = _make_annotations_by_claim(rows)
    report = build_iaa_report(annotations_by_claim)
    assert report.is_pilot_round
    assert "pilot round" in report.recommendation.lower() or "Section 11.2" in report.recommendation


def test_no_overlap_between_annotators_reports_gracefully():
    annotations_by_claim = {
        "c1": [Annotation(claim_id="c1", annotator_id="alice", verdict=Verdict.VERIFIED)],
        "c2": [Annotation(claim_id="c2", annotator_id="bob", verdict=Verdict.VERIFIED)],
    }
    report = build_iaa_report(annotations_by_claim)
    assert report.pairwise == []
    assert not report.meets_minimum_target
    assert "overlapping" in report.recommendation.lower()
