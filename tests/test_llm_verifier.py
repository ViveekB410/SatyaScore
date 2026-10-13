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
    # legacy aggregation: this fixture's one passage is not titled after the claim's
    # subject, so under "gated" it could not contradict; these tests need NLI to say No
    p = DetectionPipeline(embedder=embedder, retriever=retriever, scorer=scorer, claim_extractor=extractor,
                          nli_scorer=nli, llm_verifier=llm, aggregation="legacy")
    p._kg_lookup = lambda *a, **k: (kg_conf, None)
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


def test_wrong_span_is_kept_only_when_it_occurs_in_the_claim():
    claim = "Mahatma Gandhi was born in Delhi."
    j = lv.parse_reply('{"verdict": "Hallucinated", "p_true": 0.05, "wrong_span": "Delhi", "reason": "Porbandar"}', claim)
    assert j.wrong_span == "Delhi"
    assert lv.parse_reply('{"verdict": "Hallucinated", "wrong_span": "Mumbai"}', claim).wrong_span == ""
    assert lv.parse_reply('{"verdict": "Verified", "wrong_span": "Delhi"}', claim).wrong_span == ""


def test_provider_selects_endpoint_and_key_variable(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    v = lv.LLMVerifier(provider="gemini", model="gemini-2.5-flash", min_interval_s=0)
    assert "generativelanguage.googleapis.com" in v._url
    with pytest.raises(lv.LLMVerifierError, match="GEMINI_API_KEY"):
        v.verify("c", [])
    assert "max_tokens" in v._body("c", []) and "max_completion_tokens" not in v._body("c", [])
    with pytest.raises(ValueError):
        lv.LLMVerifier(provider="nope")


def test_evidence_sent_to_the_llm_is_trimmed():
    msgs = lv.build_messages("c", ["x" * 5000] * 20, "open")
    assert msgs[1]["content"].count("[") <= lv.MAX_PASSAGES and len(msgs[1]["content"]) < 5000


# --- Version 2: cross-check verdict mode ----------------------------------------------

def _crosscheck(llm, entail, contra):
    p = _pipeline_with(llm, kg_conf=None)
    p.verdict_mode = "crosscheck"
    p.nli_scorer.score_batch.return_value = [MagicMock(entailment_prob=entail, contradiction_prob=contra)]
    return p.run("Paris is the capital of France.", "en")


def test_crosscheck_verified_needs_passages_and_llm():
    llm = MagicMock(model="m")
    llm.verify.return_value = lv.LLMJudgement("Verified", 0.95, "stated", "")
    r = _crosscheck(llm, 0.9, 0.05)
    assert r.scores[0].verdict.value == "Verified" and r.scores[0].note.startswith("cross-checked")
    assert r.evidence[0]["llm_check"]["verdict"] == "Verified" and r.evidence[0]["error_spans"] == []
    llm.verify.return_value = lv.LLMJudgement("Hallucinated", 0.1, "wrong city", "Paris", wrong_span="Paris")
    r = _crosscheck(llm, 0.9, 0.05)
    assert r.scores[0].verdict.value == "Uncertain"  # passages and LLM disagree


def test_crosscheck_contradiction_or_llm_false_without_support_is_hallucinated():
    llm = MagicMock(model="m")
    llm.verify.return_value = lv.LLMJudgement("Uncertain", 0.5, "", "")
    assert _crosscheck(llm, 0.1, 0.8).scores[0].verdict.value == "Hallucinated"  # on-topic contradiction
    llm.verify.return_value = lv.LLMJudgement("Verified", 0.9, "", "")
    assert _crosscheck(llm, 0.1, 0.8).scores[0].verdict.value == "Uncertain"  # symmetric: they disagree
    llm.verify.return_value = lv.LLMJudgement("Hallucinated", 0.05, "", "", wrong_span="Paris")
    r = _crosscheck(llm, 0.5, 0.3)
    assert r.scores[0].verdict.value == "Hallucinated" and r.scores[0].hallu_score <= 0.34
    assert r.evidence[0]["error_spans"] == [[0, 5]]


def test_crosscheck_llm_failure_keeps_the_passage_verdict():
    llm = MagicMock(model="m")
    llm.verify.side_effect = lv.LLMQuotaExhausted("daily limit")
    r = _crosscheck(llm, 0.1, 0.8)
    assert r.scores[0].verdict.value == "Hallucinated" and r.evidence[0]["llm_check"] is None


def test_provider_json_validation_failure_is_read_tolerantly_or_retried(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    session = MagicMock()
    bad = {"error": {"message": "Failed to validate JSON.", "code": "json_validate_failed",
                     "failed_generation": 'Sure: {"verdict": "Hallucinated", "p_true": 0.1,}'}}
    good = {"choices": [{"message": {"content": '{"verdict": "Verified", "p_true": 0.9}'}}], "usage": {}}
    session.post.side_effect = [_resp(400, bad), _resp(200, good)]
    j = lv.LLMVerifier(session=session, min_interval_s=0).verify("c", [])
    assert j.verdict == "Verified"  # unparsable failed_generation -> retried without strict JSON mode
    assert "response_format" not in session.post.call_args.kwargs["json"]
    bad["error"]["failed_generation"] = '{"verdict": "Hallucinated", "p_true": 0.1} trailing text'
    session.post.side_effect = [_resp(400, bad)]
    assert lv.LLMVerifier(session=session, min_interval_s=0).verify("c", []).verdict == "Hallucinated"


def test_second_reading_verifies_a_leaning_true_claim_only_if_the_sources_state_it():
    llm = MagicMock(model="m")
    llm.verify.return_value = lv.LLMJudgement("Verified", 0.95, "known fact", "")
    p = _pipeline_with(llm, kg_conf=None)
    p.verdict_mode = "crosscheck"
    p.nli_scorer.score_batch.return_value = [MagicMock(entailment_prob=0.5, contradiction_prob=0.3)]
    assert p.run("Paris is the capital of France.", "en").scores[0].verdict.value == "Uncertain"  # passages unclear
    reader = MagicMock(model="m")
    reader.verify.return_value = lv.LLMJudgement("Verified", 0.9, "passage 1 states it", "")
    p.second_reader = reader
    s = p.run("Paris is the capital of France.", "en").scores[0]
    assert s.verdict.value == "Verified" and "second reading" in s.note
    reader.verify.return_value = lv.LLMJudgement("Uncertain", 0.5, "", "")
    assert p.run("Paris is the capital of France.", "en").scores[0].verdict.value == "Uncertain"
    llm.verify.return_value = lv.LLMJudgement("Hallucinated", 0.1, "Lyon is the capital", "")  # LLM says false
    reader.verify.reset_mock()
    p.run("Paris is the capital of France.", "en")
    reader.verify.assert_not_called()


def test_v4a_guard_unflags_a_claim_the_sources_state():
    llm = MagicMock(model="m")
    llm.verify.return_value = lv.LLMJudgement("Hallucinated", 0.05, "wrong city", "")
    p = _pipeline_with(llm, kg_conf=None)
    p.verdict_mode, p.flag_needs_llm = "crosscheck", True
    p.nli_scorer.score_batch.return_value = [MagicMock(entailment_prob=0.5, contradiction_prob=0.3)]
    reader = MagicMock(model="m")
    reader.verify.return_value = lv.LLMJudgement("Verified", 0.9, "passage 1 states it", "")
    p.second_reader = reader
    s = p.run("Paris is the capital of France.", "en").scores[0]
    assert s.verdict.value == "Uncertain" and "not flagged" in s.note
    reader.verify.return_value = lv.LLMJudgement("Uncertain", 0.5, "", "")
    assert p.run("Paris is the capital of France.", "en").scores[0].verdict.value == "Hallucinated"


def test_same_claim_and_passages_are_answered_from_the_cache(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    session = MagicMock()
    session.post.return_value = _resp(200, {"choices": [{"message": {"content": '{"verdict": "Verified"}'}}], "usage": {}})
    v = lv.LLMVerifier(session=session, min_interval_s=0)
    assert v.verify("c", ["p"]).verdict == v.verify("c", ["p"]).verdict == "Verified"
    assert session.post.call_count == 1
    v.verify("c", ["other passage"])
    assert session.post.call_count == 2  # different evidence: asked again
    session.post.return_value = _resp(200, {"choices": [{"message": {"content": "no json"}}], "usage": {}})
    v.verify("d", [])
    v.verify("d", [])
    assert session.post.call_count == 4  # unparsable answers are not cached


def test_parallel_crosscheck_gives_the_same_verdicts_in_claim_order():
    import numpy as np
    texts = ["Paris is the capital of France.", "Lyon is the capital of France.", "Nice is in France."]
    answers = {texts[0]: "Verified", texts[1]: "Hallucinated", texts[2]: "Uncertain"}
    llm = MagicMock(model="m")
    llm.verify.side_effect = lambda claim, passages: lv.LLMJudgement(answers[claim], None, "", "")
    runs = []
    for workers in (1, 4):
        p = _pipeline_with(llm, kg_conf=None)
        p.verdict_mode, p.llm_workers = "crosscheck", workers
        claims = []
        for t in texts:
            c = MagicMock()
            c.text = t
            claims.append(c)
        p.claim_extractor.extract.return_value = claims
        p.embedder.embed.return_value = MagicMock(vectors=np.ones((3, 8), np.float32), model_used=["xlm-r"] * 3)
        p.nli_scorer.score_batch.return_value = [MagicMock(entailment_prob=0.9, contradiction_prob=0.05)]
        runs.append([s.verdict.value for s in p.run(" ".join(texts), "en").scores])
    assert runs[0] == runs[1] == ["Verified", "Hallucinated", "Uncertain"]  # one answer per claim, in order


def test_fallback_moves_on_at_a_rate_limit_without_waiting_and_skips_that_provider(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    good = {"choices": [{"message": {"content": '{"verdict": "Verified"}'}}], "usage": {}}
    cloud, local = MagicMock(), MagicMock()
    cloud.post.return_value = _resp(429, headers={"Retry-After": "30"})
    local.post.return_value = _resp(200, good)
    fb = lv.FallbackVerifier([lv.LLMVerifier(session=cloud, min_interval_s=0, model="a"),
                              lv.LLMVerifier(session=local, min_interval_s=0, provider="ollama", model="b")])
    j = fb.verify("c1", [])
    assert j.verdict == "Verified" and j.model == "b" and cloud.post.call_count == 1  # one 429, no retries
    fb.verify("c2", [])
    assert cloud.post.call_count == 1 and local.post.call_count == 2  # cloud skipped while cooling down
    assert fb.verify("c1", []) is j and local.post.call_count == 2  # cached answer reused
    fb.max_passages = 10
    assert all(v.max_passages == 10 for v in fb.verifiers)


def test_second_reading_flags_only_when_switched_on_and_all_readers_are_recorded():
    llm = MagicMock(model="m")
    llm.verify.return_value = lv.LLMJudgement("Verified", 0.9, "known fact", "")
    reader = MagicMock(model="m")
    reader.verify.return_value = lv.LLMJudgement("Hallucinated", 0.1, "passage 2 gives 1889", "", wrong_span="Paris")
    p = _pipeline_with(llm, kg_conf=None)
    p.verdict_mode, p.second_reader = "crosscheck", reader
    p.nli_scorer.score_batch.return_value = [MagicMock(entailment_prob=0.5, contradiction_prob=0.3)]
    r = p.run("Paris is the capital of France.", "en")
    assert r.scores[0].verdict.value == "Uncertain"  # default: the evaluated rule
    lc = r.evidence[0]["llm_check"]
    assert lc["passages"] == "passages unclear" and lc["second_reading"]["verdict"] == "Hallucinated"
    assert lc["second_reading"]["purpose"] == "confirm" and lc["verdict_used"] == "Verified"
    p.second_reading_flags = True
    r = p.run("Paris is the capital of France.", "en")
    assert r.scores[0].verdict.value == "Hallucinated" and "contradict it" in r.scores[0].note
    assert r.evidence[0]["error_spans"] == [[0, 5]]


def test_fallback_moves_on_at_once_on_a_network_error_or_server_error(monkeypatch):
    import requests
    monkeypatch.setenv("GROQ_API_KEY", "x")
    good = {"choices": [{"message": {"content": '{"verdict": "Uncertain"}'}}], "usage": {}}
    monkeypatch.setattr(lv.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("must not wait")))
    for failure in (requests.ConnectionError("down"), _resp(503)):
        cloud, local = MagicMock(), MagicMock()
        if isinstance(failure, Exception):
            cloud.post.side_effect = failure
        else:
            cloud.post.return_value = failure
        local.post.return_value = _resp(200, good)
        fb = lv.FallbackVerifier([lv.LLMVerifier(session=cloud, min_interval_s=0, model="a"),
                                  lv.LLMVerifier(session=local, min_interval_s=0, provider="ollama", model="b")])
        assert fb.verify("c", []).model == "b" and cloud.post.call_count == 1  # no retries, no sleeping
        assert fb.verifiers[0]._timeout <= lv.FallbackVerifier.FAST_TIMEOUT_S and fb.verifiers[1]._timeout == 90


def test_llm_models_pairs_models_with_providers_and_rejects_a_mismatch():
    from member3_backend.api import llm_models
    assert llm_models(["groq", "ollama"], [], crosscheck=True) == ["openai/gpt-oss-20b", "gpt-oss:20b"]
    assert llm_models(["ollama"], [], crosscheck=False) == ["gpt-oss:20b"]  # never a cloud name for Ollama
    assert llm_models(["groq"], [], crosscheck=False) == [lv.DEFAULT_MODEL]
    assert llm_models(["groq", "ollama"], ["x", "y"], crosscheck=True) == ["x", "y"]
    with pytest.raises(ValueError, match="one per provider"):
        llm_models(["groq", "ollama"], ["gpt-oss:20b"], crosscheck=True)
