from types import SimpleNamespace

from member1_model.cmhsa import KG_NOTE, Verdict
from member3_backend.pipeline import _crosscheck_score, error_spans


def test_only_hallucinated_claims_have_error_spans():
    assert error_spans("Gandhi was born in Delhi.", Verdict.VERIFIED, None, None, "Delhi") == []


def test_kg_contradiction_marks_the_claimed_value():
    kg_v = SimpleNamespace(status="contradicted", expected_value="Canadian")
    assert error_spans("Janet Leigh was Canadian.", Verdict.HALLUCINATED, KG_NOTE, kg_v) == [[16, 24]]


def test_llm_wrong_span_then_whole_claim():
    c = "Gandhi was born in Delhi."
    assert error_spans(c, Verdict.HALLUCINATED, "cross-checked: ...", None, "Delhi") == [[19, 24]]
    assert error_spans(c, Verdict.HALLUCINATED, "cross-checked: ...", None, "") == [[0, len(c)]]
    kg_v = SimpleNamespace(status="contradicted", expected_value="Q1156")  # a QID is not text
    assert error_spans(c, Verdict.HALLUCINATED, KG_NOTE, kg_v, "") == [[0, len(c)]]


def test_crosscheck_score_stays_in_the_verdict_band():
    assert 0.66 <= _crosscheck_score(Verdict.VERIFIED, 0.9, 0.2) <= 1.0
    assert _crosscheck_score(Verdict.HALLUCINATED, 0.9, 0.1) <= 0.34
    assert 0.35 <= _crosscheck_score(Verdict.UNCERTAIN, None, None) <= 0.65
