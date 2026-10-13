"""Fixes from the code review of the Version 2 branch (error spans, provider fallback, API settings)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from member1_model import llm_verifier as lv
from member1_model.cmhsa import KG_NOTE, ClaimScore, Verdict
from member3_backend.pipeline import claimed_words, error_spans, find_words


def _resp(status, body=None, headers=None, text=""):
    r = MagicMock()
    r.status_code, r.headers, r.text = status, headers or {}, text
    if isinstance(body, Exception):
        r.json.side_effect = body
    else:
        r.json.return_value = body if body is not None else {}
    return r


# --- 1. a structured source's contradiction marks the claimed words, not the whole claim ----------------

def test_claimed_words_from_an_item_id_a_date_or_a_number():
    kg = lambda value: SimpleNamespace(status="contradicted", expected_value=value)  # noqa: E731
    assert claimed_words("Mahatma Gandhi was born in Delhi.", kg("Q1353"), {"delhi", "new delhi"}) == "delhi"
    assert claimed_words("भारत की राजधानी मुंबई है।", kg("Q1156"), {"मुंबई", "bombay"}) == "मुंबई"
    assert claimed_words("Gandhi was born on 2 October 1870.", kg("1870-10-2")) == "2 October 1870"
    assert claimed_words("India's population is 1.4 billion.", kg("1400000000.0")) == "1.4 billion"
    assert claimed_words("The literacy rate of Kerala is 74%.", kg("74.0")) == "74%"
    assert claimed_words("Gandhi was born in Delhi.", kg("Q1353")) == ""  # no names known: nothing to mark
    c = "Mahatma Gandhi was born in Delhi."
    assert error_spans(c, Verdict.HALLUCINATED, KG_NOTE, kg("Q1353"), "", "delhi") == [[27, 32]]


# --- 8. whole words first, and offsets that survive casefolding ------------------------------------------

def test_find_words_prefers_whole_words_and_keeps_offsets():
    assert find_words("In 2022 the company had 2 offices", "2") == (24, 25)  # not the "2" inside "2022"
    assert find_words("Straße ist 5 km lang", "5 km") == (11, 15)  # "ß" casefolds to "ss" (longer)
    assert find_words("abc", "") is None and find_words("abc", "x") is None


def test_input_spans_offsets_survive_casefolding():
    from member3_backend.api import input_spans
    text = "Die Straße hat 2 Spuren."
    claim = SimpleNamespace(text="Die Straße hat 2 Spuren.", start_char=0, end_char=len(text))
    assert input_spans(text, claim, [[15, 16]]) == [[15, 16]]


# --- 3. the second reader shares the first reader's pacing and paused providers --------------------------

def test_second_reader_shares_pacing_and_paused_providers():
    first = lv.FallbackVerifier([lv.LLMVerifier(provider="groq", model="a", min_interval_s=0),
                                 lv.LLMVerifier(provider="ollama", model="b", min_interval_s=0)])
    second = lv.FallbackVerifier([lv.LLMVerifier(provider="groq", model="a", min_interval_s=0, mode="grounded",
                                                 pacer=first.verifiers[0].pacer),
                                  lv.LLMVerifier(provider="ollama", model="b", min_interval_s=0, mode="grounded",
                                                 pacer=first.verifiers[1].pacer)], share_with=first)
    assert second._down is first._down and second._lock is first._lock
    assert second.verifiers[0].pacer is first.verifiers[0].pacer


# --- 4. error replies of any shape, odd Retry-After values, replies without a message ---------------------

def test_error_replies_of_any_shape_are_read():
    assert lv._error_of(_resp(400, {"error": {"message": "bad", "code": "x"}}))["message"] == "bad"
    assert lv._error_of(_resp(400, [{"error": {"message": "gemini says no"}}]))["message"] == "gemini says no"
    assert lv._error_of(_resp(404, {"error": "model not found"}))["message"] == "model not found"
    assert lv._error_of(_resp(500, ValueError("not json"), text="<html>oops</html>"))["message"] == "<html>oops</html>"
    assert lv._seconds("Wed, 21 Oct 2026 07:28:00 GMT", 4) == 4 and lv._seconds("3", 4) == 3.0


def test_a_strange_reply_moves_the_fallback_on(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    good = {"choices": [{"message": {"content": '{"verdict": "Verified"}'}}], "usage": {}}
    for bad in (_resp(200, {"no": "choices"}), _resp(422, [{"error": {"message": "extra inputs"}}]),
                _resp(429, headers={"Retry-After": "soon"})):
        cloud, local = MagicMock(), MagicMock()
        cloud.post.return_value, local.post.return_value = bad, _resp(200, good)
        fb = lv.FallbackVerifier([lv.LLMVerifier(session=cloud, min_interval_s=0, model="a"),
                                  lv.LLMVerifier(session=local, min_interval_s=0, provider="ollama", model="b")])
        assert fb.verify("c", []).model == "b"


# --- 5. a model each provider serves; Mistral's max_tokens --------------------------------------------------

def test_every_provider_gets_a_model_it_serves_and_mistral_gets_max_tokens():
    from member3_backend.api import llm_models
    got = dict(zip(["gemini", "mistral", "cerebras", "openrouter"],
                   llm_models(["gemini", "mistral", "cerebras", "openrouter"], [], crosscheck=True)))
    assert "openai/gpt-oss-120b" not in (got["gemini"], got["mistral"], got["cerebras"])
    body = lv.LLMVerifier(provider="mistral", model=got["mistral"], min_interval_s=0)._body("c", [])
    assert "max_tokens" in body and "max_completion_tokens" not in body


# --- 2. claims decided by the cross-check get no passage excerpt ------------------------------------------

def test_cross_checked_claims_are_decided_elsewhere():
    from member3_backend.pipeline import _decided_elsewhere
    assert _decided_elsewhere("cross-checked: passages support; LLM (m) says Verified")
    assert not _decided_elsewhere(None) and not _decided_elsewhere("")


# --- 7. a threshold override that flags a claim still marks it ---------------------------------------------

def test_threshold_override_marks_the_whole_claim(monkeypatch):
    from fastapi.testclient import TestClient
    from member3_backend import api
    text = "Paris is in Germany."
    claim = SimpleNamespace(text=text, start_char=0, end_char=len(text), extraction_method="decomposed_base")
    score = ClaimScore(claim_id="claim_0", hallu_score=0.6, verdict=Verdict.UNCERTAIN, active_signals=["nli"],
                       note=None)
    result = SimpleNamespace(claims=[claim], scores=[score], overall_score=0.6, processing_time_ms=1.0, timings_ms={},
                             evidence=[{"passage_ids": [], "deciding": None, "error_spans": []}])
    class Retriever:  # an index is "loaded"
        _index = object()

        def __len__(self):
            return 1

    monkeypatch.setattr(api, "_retriever", Retriever())
    monkeypatch.setattr(api._pipeline, "run", lambda *a, **k: result)
    api._request_log.clear()
    r = TestClient(api.app).post("/detect", json={"text": text, "language": "en", "threshold": 0.8},
                                 headers={"X-API-Key": "dev-key-satyascore-2026"})
    assert r.status_code == 200, r.text
    c = r.json()["claims"][0]
    assert c["verdict"] == "Hallucinated" and c["error_spans"] == [[0, len(text)]]
