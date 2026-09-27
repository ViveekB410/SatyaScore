import pytest

from member1_model.cmhsa import CMHSAScorer, ClaimSubScores, Verdict


@pytest.fixture
def scorer():
    s = CMHSAScorer()
    s.load_weights("en", alpha=0.4, beta=0.4, gamma=0.2)
    return s


def test_weights_sum_to_one(scorer):
    a, b, g = scorer.get_weights("en")
    assert pytest.approx(a + b + g, abs=1e-4) == 1.0


def test_full_signal_fusion(scorer):
    claim = ClaimSubScores(claim_id="c1", sem_sim=0.9, nli_prob=0.9, kg_conf=0.9)
    result = scorer.score_claim(claim, "en")
    assert result.hallu_score == pytest.approx(0.9, abs=1e-3)
    assert result.verdict == Verdict.VERIFIED
    assert set(result.active_signals) == {"semsim", "nli", "kg"}


def test_ablation_renormalises_weights(scorer):
    # KG signal missing (ablation mode) — remaining alpha/beta should renormalise
    # to sum to 1 rather than silently underweighting the score.
    claim = ClaimSubScores(claim_id="c2", sem_sim=0.8, nli_prob=0.8, kg_conf=None)
    result = scorer.score_claim(claim, "en")
    assert result.hallu_score == pytest.approx(0.8, abs=1e-3)
    assert "kg" not in result.active_signals


def test_verdict_thresholds(scorer):
    low = ClaimSubScores(claim_id="c3", sem_sim=0.1, nli_prob=0.1, kg_conf=0.1)
    mid = ClaimSubScores(claim_id="c4", sem_sim=0.5, nli_prob=0.5, kg_conf=0.5)
    high = ClaimSubScores(claim_id="c5", sem_sim=0.9, nli_prob=0.9, kg_conf=0.9)

    assert scorer.score_claim(low, "en").verdict == Verdict.HALLUCINATED
    assert scorer.score_claim(mid, "en").verdict == Verdict.UNCERTAIN
    assert scorer.score_claim(high, "en").verdict == Verdict.VERIFIED


def test_no_active_signals_raises(scorer):
    claim = ClaimSubScores(claim_id="c6", sem_sim=None, nli_prob=None, kg_conf=None)
    with pytest.raises(ValueError):
        scorer.score_claim(claim, "en")


def test_invalid_weight_sum_rejected(scorer):
    with pytest.raises(ValueError):
        scorer.load_weights("en", alpha=0.5, beta=0.5, gamma=0.5)

# --- the KG decides when it answers (member1_model/cmhsa.KG_DECIDES) -------------

def test_kg_supported_decides_over_a_contradicting_nli(scorer):
    # "Gandhi was born in Porbandar": Wikidata supports it, NLI wrongly contradicts
    s = scorer.score_claim(ClaimSubScores(claim_id="g", sem_sim=0.6, nli_prob=0.1, kg_conf=1.0), "en")
    assert s.verdict is Verdict.VERIFIED and s.hallu_score == 1.0
    assert s.note and "knowledge graph" in s.note


def test_kg_contradiction_decides_over_a_supporting_nli(scorer):
    s = scorer.score_claim(ClaimSubScores(claim_id="b", sem_sim=0.9, nli_prob=0.95, kg_conf=0.0), "hi")
    assert s.verdict is Verdict.HALLUCINATED and s.hallu_score == 0.0


def test_without_a_kg_answer_the_weighted_fusion_is_unchanged(scorer):
    s = scorer.score_claim(ClaimSubScores(claim_id="n", sem_sim=0.2, nli_prob=0.8, kg_conf=None), "en")
    assert s.hallu_score == pytest.approx(0.5 * 0.2 + 0.5 * 0.8) and s.note is None
