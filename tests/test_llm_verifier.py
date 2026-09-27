"""LLM verifier: prompt, reply parsing, key handling and HTTP behaviour (no network)."""
from unittest.mock import MagicMock

import pytest

from member1_model import llm_verifier as lv


def _resp(status, body=None, headers=None):
    r = MagicMock()
    r.status_code = status
    r.headers = headers or {}
    r.json.return_value = body or {}
    r.text = ""
    return r


def test_prompt_carries_claim_evidence_mode_and_is_bilingual():
    msgs = lv.build_messages("पेरिस फ्रांस की राजधानी है।", ["Paris is the capital of France."], "grounded")
    system, user = msgs[0]["content"], msgs[1]["content"]
    assert "ONLY the evidence" in system and "Hindi or English" in system
    assert "पेरिस" in user and "[1] Paris is the capital" in user
    assert "own reliable knowledge" in lv.build_messages("c", [], "open")[0]["content"]
    assert "(no passage retrieved)" in lv.build_messages("c", [], "open")[1]["content"]


def test_reply_parsing_is_strict_about_verdicts_and_tolerant_about_format():
    j = lv.parse_reply('<think>hmm</think> {"verdict": "hallucinated", "p_true": 0.1, "reason": "wrong city"}')
    assert (j.verdict, j.p_true, j.reason) == ("Hallucinated", 0.1, "wrong city")
    assert lv.parse_reply('{"verdict": "Verified"}').p_true == 1.0  # falls back to the verdict
    assert lv.parse_reply('{"verdict": "Verified", "p_true": 7}').p_true == 1.0  # clamped
    bad = lv.parse_reply("I think it is true.")
    assert bad.verdict is None and bad.p_true is None
    assert lv.parse_reply('{"verdict": "True", "p_true": 0.9}').verdict is None


def test_missing_key_fails_clearly_without_calling_the_api(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    session = MagicMock()
    with pytest.raises(lv.LLMVerifierError, match="GROQ_API_KEY"):
        lv.LLMVerifier(session=session, min_interval_s=0).verify("c", [])
    session.post.assert_not_called()


def test_request_is_deterministic_json_and_key_is_only_in_the_header(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_secret")
    session = MagicMock()
    session.post.return_value = _resp(200, {"choices": [{"message": {"content": '{"verdict": "Verified", "p_true": 0.9}'}}],
                                            "usage": {"total_tokens": 321}})
    v = lv.LLMVerifier(session=session, min_interval_s=0)
    j = v.verify("Paris is the capital of France.", ["Paris is the capital of France."])
    assert j.verdict == "Verified" and v.tokens_used == 321
    kwargs = session.post.call_args.kwargs
    assert kwargs["json"]["temperature"] == 0 and kwargs["json"]["response_format"] == {"type": "json_object"}
    assert kwargs["headers"]["Authorization"] == "Bearer gsk_test_secret"
    assert "gsk_test_secret" not in str(kwargs["json"])


def test_bad_key_stops_and_a_long_rate_limit_is_reported_not_slept(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    session = MagicMock()
    session.post.return_value = _resp(401, {"error": {"message": "Invalid API Key"}})
    with pytest.raises(lv.LLMVerifierError, match="401"):
        lv.LLMVerifier(session=session, min_interval_s=0).verify("c", [])
    session.post.return_value = _resp(429, headers={"Retry-After": "3600"})
    with pytest.raises(lv.LLMQuotaExhausted):
        lv.LLMVerifier(session=session, min_interval_s=0).verify("c", [])


# --- the live pipeline switch (off by default) ---------------------------------------

def _pipeline_with(llm, kg_conf):
    import numpy as np
    from member1_model.cmhsa import CMHSAScorer
    from member3_backend.faiss_retriever import RetrievalResult, RetrievedPassage
    from member3_backend.pipeline import DetectionPipeline
    embedder = MagicMock()
    embedder.embed.return_value = MagicMock(vectors=np.ones((1, 8), np.float32), model_used=["xlm-r"])
    retriever = MagicMock()
    retriever.retrieve.return_value = RetrievalResult("c", [RetrievedPassage("p", "Paris is the capital of France.", 0.9)], 1.0, True)
    nli = MagicMock()
    nli.score_batch.return_value = [MagicMock(entailment_prob=0.1, contradiction_prob=0.8)]
    scorer = CMHSAScorer()
    scorer.load_weights("en", alpha=0.0, beta=0.5, gamma=0.5)
    extractor = MagicMock()
    claim = MagicMock()
    claim.text = "Paris is the capital of France."
    extractor.extract.return_value = [claim]
    p = DetectionPipeline(embedder=embedder, retriever=retriever, scorer=scorer, claim_extractor=extractor,
                          nli_scorer=nli, llm_verifier=llm)
    p._try_kg_verification = lambda *a, **k: kg_conf
    p.entity_linker, p.wikidata = MagicMock(), MagicMock()
    return p


def test_llm_judges_claims_the_kg_did_not_decide():
    llm = MagicMock(model="openai/gpt-oss-120b")
    llm.verify.return_value = lv.LLMJudgement("Verified", 0.95, "stated in passage 1", "")
    s = _pipeline_with(llm, kg_conf=None).run("Paris is the capital of France.", "en").scores[0]
    assert (s.verdict.value, s.hallu_score) == ("Verified", 0.95)  # NLI alone would have said Hallucinated
    assert "llm" in s.active_signals and "judged by LLM" in s.note
    assert llm.verify.call_args.args == ("Paris is the capital of France.", ["Paris is the capital of France."])


def test_kg_decided_claims_are_not_sent_to_the_llm():
    llm = MagicMock(model="m")
    s = _pipeline_with(llm, kg_conf=1.0).run("Paris is the capital of France.", "en").scores[0]
    llm.verify.assert_not_called()
    assert s.verdict.value == "Verified" and "knowledge graph" in s.note


def test_llm_failure_keeps_the_nli_result_with_a_note():
    llm = MagicMock(model="m")
    llm.verify.side_effect = lv.LLMQuotaExhausted("daily limit")
    s = _pipeline_with(llm, kg_conf=None).run("Paris is the capital of France.", "en").scores[0]
    assert s.verdict.value == "Hallucinated" and "unavailable" in s.note
