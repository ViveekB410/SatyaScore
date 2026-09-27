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
