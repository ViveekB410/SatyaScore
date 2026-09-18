from unittest.mock import MagicMock

import numpy as np
import pytest

from member1_model.cmhsa import CMHSAScorer
from member3_backend.faiss_retriever import RetrievalResult, RetrievedPassage
from member3_backend.pipeline import DetectionPipeline


def _mock_embedder(n_claims):
    embedder = MagicMock()
    result = MagicMock()
    result.vectors = np.random.default_rng(0).normal(size=(n_claims, 768)).astype(np.float32)
    embedder.embed.return_value = result
    return embedder


def _mock_retriever(score=0.8, has_passage=True):
    retriever = MagicMock()
    if has_passage:
        retriever.retrieve.return_value = RetrievalResult(
            claim_id="claim_0",
            passages=[RetrievedPassage(passage_id="p0", text="Evidence text.", score=score)],
            latency_ms=1.0,
            met_latency_target=True,
        )
    else:
        retriever.retrieve.return_value = RetrievalResult(
            claim_id="claim_0", passages=[], latency_ms=1.0, met_latency_target=True
        )
    return retriever


def _real_scorer():
    scorer = CMHSAScorer()
    scorer.load_weights("en", alpha=0.5, beta=0.3, gamma=0.2)
    return scorer


def test_semsim_only_pipeline_runs_end_to_end():
    pipeline = DetectionPipeline(
        embedder=_mock_embedder(1), retriever=_mock_retriever(score=0.9), scorer=_real_scorer()
    )
    result = pipeline.run("The sky is blue.", language="en")

    assert len(result.claims) == 1
    assert len(result.scores) == 1
    assert result.scores[0].active_signals == ["semsim"]
    assert 0.0 <= result.overall_score <= 1.0


def test_pipeline_with_nli_scorer_uses_both_signals():
    nli_scorer = MagicMock()
    nli_result = MagicMock()
    nli_result.entailment_prob = 0.85
    nli_result.contradiction_prob = 0.05
    nli_scorer.score_batch.return_value = [nli_result]

    pipeline = DetectionPipeline(
        embedder=_mock_embedder(1),
        retriever=_mock_retriever(score=0.9),
        scorer=_real_scorer(),
        nli_scorer=nli_scorer,
    )
    result = pipeline.run("The sky is blue.", language="en")

    assert set(result.scores[0].active_signals) == {"semsim", "nli"}
    nli_scorer.score_batch.assert_called_once()


def test_pipeline_with_full_kg_chain_resolved():
    nli_scorer = MagicMock()
    nli_result = MagicMock()
    nli_result.entailment_prob = 0.8
    nli_result.contradiction_prob = 0.1
    nli_scorer.score_batch.return_value = [nli_result]

    claim_extractor = MagicMock()
    extracted = MagicMock()
    extracted.text = "Narendra Modi is the Prime Minister of India."
    claim_extractor.extract.return_value = [extracted]
    claim_extractor.extract_entities.return_value = ["Narendra Modi", "India"]

    entity_linker = MagicMock()
    linked = MagicMock()
    linked.linkable = True
    linked.subject_qid = "Q1058"
    linked.property_pid = "P39"
    linked.object_qid = "Q668"
    entity_linker.link_claim.return_value = linked

    wikidata = MagicMock()
    verification = MagicMock()
    verification.confidence = 0.95
    wikidata.verify_triple.return_value = verification

    pipeline = DetectionPipeline(
        embedder=_mock_embedder(1),
        retriever=_mock_retriever(score=0.9),
        scorer=_real_scorer(),
        claim_extractor=claim_extractor,
        nli_scorer=nli_scorer,
        entity_linker=entity_linker,
        wikidata=wikidata,
    )
    result = pipeline.run("Narendra Modi is the Prime Minister of India.", language="en")

    assert set(result.scores[0].active_signals) == {"semsim", "nli", "kg"}
    wikidata.verify_triple.assert_called_once()


def test_pipeline_kg_signal_absent_when_entities_insufficient():
    claim_extractor = MagicMock()
    extracted = MagicMock()
    extracted.text = "It is sunny today."
    claim_extractor.extract.return_value = [extracted]
    claim_extractor.extract_entities.return_value = []  # no entities found

    entity_linker = MagicMock()
    wikidata = MagicMock()

    pipeline = DetectionPipeline(
        embedder=_mock_embedder(1),
        retriever=_mock_retriever(score=0.9),
        scorer=_real_scorer(),
        claim_extractor=claim_extractor,
        entity_linker=entity_linker,
        wikidata=wikidata,
    )
    result = pipeline.run("It is sunny today.", language="en")

    assert "kg" not in result.scores[0].active_signals
    wikidata.verify_triple.assert_not_called()


def test_ablation_mode_restricts_to_requested_signals():
    nli_scorer = MagicMock()
    nli_result = MagicMock()
    nli_result.entailment_prob = 0.7
    nli_result.contradiction_prob = 0.2
    nli_scorer.score_batch.return_value = [nli_result]

    pipeline = DetectionPipeline(
        embedder=_mock_embedder(1),
        retriever=_mock_retriever(score=0.9),
        scorer=_real_scorer(),
        nli_scorer=nli_scorer,
    )
    result = pipeline.run("The sky is blue.", language="en", active_signals={"semsim"})

    assert result.scores[0].active_signals == ["semsim"]
    nli_scorer.score_batch.assert_not_called()


def test_empty_extraction_raises_value_error():
    embedder = _mock_embedder(1)
    retriever = _mock_retriever()

    pipeline = DetectionPipeline(embedder=embedder, retriever=retriever, scorer=_real_scorer())
    with pytest.raises(ValueError):
        pipeline.run("", language="en")


def test_cross_claim_nli_is_a_single_batched_call():
    # Task 1: NLI must run ONCE per request over all claims' pairs, not once per claim.
    nli_scorer = MagicMock()
    r = MagicMock()
    r.entailment_prob = 0.8
    r.contradiction_prob = 0.1
    nli_scorer.score_batch.return_value = [r, r]  # 2 claims x 1 passage = 2 pairs

    claim_extractor = MagicMock()
    c0, c1 = MagicMock(), MagicMock()
    c0.text, c1.text = "The sky is blue.", "Grass is green."
    claim_extractor.extract.return_value = [c0, c1]

    pipeline = DetectionPipeline(
        embedder=_mock_embedder(2),
        retriever=_mock_retriever(score=0.9),
        scorer=_real_scorer(),
        claim_extractor=claim_extractor,
        nli_scorer=nli_scorer,
    )
    result = pipeline.run("The sky is blue. Grass is green.", language="en")

    assert len(result.scores) == 2
    nli_scorer.score_batch.assert_called_once()  # exactly ONE batched NLI call for the document
    _, kwargs = nli_scorer.score_batch.call_args
    assert len(kwargs["premises"]) == 2  # the single call carried pairs from BOTH claims
    assert "total" in result.timings_ms and result.timings_ms["total"] >= 0  # Task 2 timings present


def test_naive_split_produces_exact_spans():
    # Task 0: fallback claim splitter must yield exact char spans for highlighting.
    from member3_backend.pipeline import _naive_split_into_claims
    text = "The sky is blue. Grass is green."
    claims = _naive_split_into_claims(text)
    assert len(claims) == 2
    for c in claims:
        assert text[c.start_char:c.end_char] == c.text
        assert c.extraction_method == "sentence_level"
