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
