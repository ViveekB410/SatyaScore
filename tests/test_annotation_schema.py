import pytest

from member2_data.annotation_schema import (
    Adjudicator,
    Annotation,
    Verdict,
    dataset_balance_check,
)


def _ann(claim_id, annotator_id, verdict):
    return Annotation(claim_id=claim_id, annotator_id=annotator_id, verdict=verdict)


def test_unanimous_resolution():
    adjudicator = Adjudicator()
    annotations = [
        _ann("c1", "alice", Verdict.VERIFIED),
        _ann("c1", "bob", Verdict.VERIFIED),
    ]
    result = adjudicator.resolve("c1", annotations)
    assert result.gold_verdict == Verdict.VERIFIED
    assert result.method == "unanimous"
    assert not result.needs_manual_adjudication


def test_clear_majority_resolution():
    adjudicator = Adjudicator()
    annotations = [
        _ann("c2", "alice", Verdict.HALLUCINATED),
        _ann("c2", "bob", Verdict.HALLUCINATED),
        _ann("c2", "carol", Verdict.UNCERTAIN),
    ]
    result = adjudicator.resolve("c2", annotations)
    assert result.gold_verdict == Verdict.HALLUCINATED
    assert result.method == "majority"
    assert not result.needs_manual_adjudication


def test_tie_flagged_for_manual_adjudication():
    adjudicator = Adjudicator()
    annotations = [
        _ann("c3", "alice", Verdict.VERIFIED),
        _ann("c3", "bob", Verdict.HALLUCINATED),
    ]
    result = adjudicator.resolve("c3", annotations)
    assert result.method == "adjudicated"
    assert result.needs_manual_adjudication


def test_three_way_split_flagged():
    adjudicator = Adjudicator()
    annotations = [
        _ann("c4", "alice", Verdict.VERIFIED),
        _ann("c4", "bob", Verdict.UNCERTAIN),
        _ann("c4", "carol", Verdict.HALLUCINATED),
    ]
    result = adjudicator.resolve("c4", annotations)
    assert result.needs_manual_adjudication


def test_resolve_requires_matching_claim_ids():
    adjudicator = Adjudicator()
    annotations = [_ann("c1", "alice", Verdict.VERIFIED), _ann("c2", "bob", Verdict.VERIFIED)]
    with pytest.raises(ValueError):
        adjudicator.resolve("c1", annotations)


def test_empty_annotations_raises():
    adjudicator = Adjudicator()
    with pytest.raises(ValueError):
        adjudicator.resolve("c1", [])


def test_dataset_balance_check():
    from member2_data.annotation_schema import AdjudicatedLabel

    labels = [
        AdjudicatedLabel("c1", Verdict.HALLUCINATED, "unanimous"),
        AdjudicatedLabel("c2", Verdict.HALLUCINATED, "unanimous"),
        AdjudicatedLabel("c3", Verdict.VERIFIED, "unanimous"),
        AdjudicatedLabel("c4", Verdict.UNCERTAIN, "unanimous"),
    ]
    balance = dataset_balance_check(labels)
    assert balance["Hallucinated"] == 0.5
    assert balance["Verified"] == 0.25
    assert balance["Uncertain"] == 0.25
