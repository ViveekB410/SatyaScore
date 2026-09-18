import numpy as np
import pytest

from member3_backend.faiss_retriever import FAISSRetriever


def _random_unit_vectors(n: int, dim: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vecs = rng.normal(size=(n, dim)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs


def test_build_and_retrieve():
    retriever = FAISSRetriever(dim=16, n_clusters=4)
    vectors = _random_unit_vectors(20, 16)
    ids = [f"p{i}" for i in range(20)]
    texts = [f"passage text {i}" for i in range(20)]

    retriever.build_index(ids, texts, vectors)
    assert len(retriever) == 20

    query = vectors[0]  # search for something identical to passage 0
    result = retriever.retrieve("claim_1", query, top_k=5)

    assert result.claim_id == "claim_1"
    assert len(result.passages) == 5
    # The nearest match to vectors[0] should be passage p0 itself.
    assert result.passages[0].passage_id == "p0"
    assert result.latency_ms >= 0


def test_incremental_add():
    retriever = FAISSRetriever(dim=16, n_clusters=4)
    vectors = _random_unit_vectors(20, 16)
    retriever.build_index([f"p{i}" for i in range(20)], [f"t{i}" for i in range(20)], vectors)

    new_vectors = _random_unit_vectors(5, 16, seed=99)
    retriever.add_passages(["p20", "p21", "p22", "p23", "p24"], [f"t{i}" for i in range(5)], new_vectors)

    assert len(retriever) == 25


def test_retrieve_before_build_raises():
    retriever = FAISSRetriever(dim=16, n_clusters=4)
    with pytest.raises(RuntimeError):
        retriever.retrieve("c1", np.zeros(16, dtype=np.float32))


def test_add_before_build_raises():
    retriever = FAISSRetriever(dim=16, n_clusters=4)
    with pytest.raises(RuntimeError):
        retriever.add_passages(["p1"], ["t1"], _random_unit_vectors(1, 16))


def test_small_corpus_does_not_crash_ivf_training():
    # Regression check: FAISS IVF training fails if n_clusters > n_vectors.
    # build_index should auto-adjust n_clusters down rather than raising.
    retriever = FAISSRetriever(dim=8, n_clusters=100)
    vectors = _random_unit_vectors(3, 8)
    retriever.build_index(["p0", "p1", "p2"], ["a", "b", "c"], vectors)
    assert len(retriever) == 3
