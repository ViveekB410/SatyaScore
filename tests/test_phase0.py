"""Phase 0 (IMPROVEMENT_PLAN.md): whole-text verdict + single embedding space."""
import numpy as np
import pytest

from member1_model import embeddings as emb
from member1_model.cmhsa import Verdict, aggregate_document


# --- 0.2 whole-text verdict (worst-claim rule) -------------------------------

def test_any_hallucinated_claim_makes_the_document_hallucinated():
    d = aggregate_document([Verdict.VERIFIED] * 9 + [Verdict.HALLUCINATED])
    # a mean would call this ~90% fine; the document verdict must not hide it
    assert d.document_verdict is Verdict.HALLUCINATED
    assert (d.n_claims, d.n_verified, d.n_hallucinated) == (10, 9, 1)
    assert d.supported_fraction == pytest.approx(0.9)


def test_uncertain_without_hallucination_makes_the_document_uncertain():
    d = aggregate_document(["Verified", "Uncertain", "Verified"])  # accepts strings (API path)
    assert d.document_verdict is Verdict.UNCERTAIN
    assert d.n_uncertain == 1


def test_all_verified_document_is_verified():
    d = aggregate_document([Verdict.VERIFIED, Verdict.VERIFIED])
    assert d.document_verdict is Verdict.VERIFIED
    assert d.supported_fraction == 1.0


def test_empty_document_is_rejected():
    with pytest.raises(ValueError):
        aggregate_document([])


# --- 0.3 one embedding space for query and corpus ----------------------------

def test_transliterated_hindi_uses_the_same_model_as_the_corpus(monkeypatch):
    e = emb.CrossLingualEmbedder(device="cpu")
    e._xlmr, e._muril = object(), object()  # stand-ins; no model download
    monkeypatch.setattr(emb.CrossLingualEmbedder, "_batched_encode",
                        staticmethod(lambda model, texts: np.ones((len(texts), 768), np.float32)))
    r = e.embed(["a", "b", "c"],
                ["The capital of France is Paris.",
                 "पेरिस फ्रांस की राजधानी है।",
                 "Paris France ki rajdhani hai."],  # transliterated Hindi
                ["en", "hi", "hi"])
    # the corpus is XLM-R only, so every query must be XLM-R too
    assert r.model_used == ["xlm-r", "xlm-r", "xlm-r"]
    assert emb.USE_MURIL_FALLBACK is False


# --- PRD FR-02: MuRIL fallback searches a MuRIL index; FR-04: calibrated CI ---

def test_muril_query_searches_the_muril_index_only():
    from unittest.mock import MagicMock
    from member1_model.cmhsa import CMHSAScorer
    from member3_backend.faiss_retriever import RetrievalResult, RetrievedPassage
    from member3_backend.pipeline import DetectionPipeline

    embedder = MagicMock()
    res = MagicMock()
    res.vectors = np.ones((2, 768), np.float32)
    res.model_used = ["xlm-r", "muril"]
    embedder.embed.return_value = res

    def retriever():
        r = MagicMock()
        r.retrieve.return_value = RetrievalResult(
            "c", [RetrievedPassage("p", "Evidence.", 0.9)], 1.0, True)
        return r
    xlmr_r, muril_r = retriever(), retriever()
    scorer = CMHSAScorer()
    scorer.load_weights("hi", alpha=0.5, beta=0.3, gamma=0.2)
    extractor = MagicMock()
    c0, c1 = MagicMock(), MagicMock()
    c0.text, c1.text = "पेरिस फ्रांस की राजधानी है।", "Paris France ki rajdhani hai."
    extractor.extract.return_value = [c0, c1]

    p = DetectionPipeline(embedder=embedder, retriever=xlmr_r, scorer=scorer,
                          claim_extractor=extractor, retriever_muril=muril_r)
    p.run("x", "hi")
    assert embedder.embed.call_args.kwargs["use_muril"] is True
    assert xlmr_r.retrieve.call_count == 1 and muril_r.retrieve.call_count == 1


def test_without_a_muril_index_muril_is_not_used():
    from unittest.mock import MagicMock
    from member3_backend.pipeline import DetectionPipeline
    embedder = MagicMock()
    p = DetectionPipeline(embedder=embedder, retriever=MagicMock(), scorer=MagicMock())
    assert p.retriever_muril is None  # -> embed(use_muril=False) in run()


def test_calibration_bins_and_wilson_interval():
    from member1_model.calibration import fit_bins, lookup, wilson
    lo, hi = wilson(9, 10)
    assert 0.55 < lo < 0.9 < hi <= 1.0
    scores = np.linspace(0, 1, 100)
    verified = scores > 0.5
    t = fit_bins(scores, verified, n_bins=4)
    low, high = lookup(0.05, t), lookup(0.95, t)
    assert low.p_verified == 0.0 and high.p_verified == 1.0
    assert high.ci95[0] > low.ci95[1]  # separated bins -> non-overlapping CIs
    assert low.n == 25



def test_cors_origins_are_configurable_for_a_hosted_frontend():
    from member3_backend.api import _CORS_ORIGINS, parse_cors_origins
    assert parse_cors_origins(None) == ["http://localhost:5173"]
    assert parse_cors_origins("") == ["http://localhost:5173"]
    assert parse_cors_origins("http://localhost:5173, https://demo.lovable.app") == [
        "http://localhost:5173", "https://demo.lovable.app"]
    assert _CORS_ORIGINS  # the middleware is built from this list
