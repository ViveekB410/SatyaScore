"""
Multilingual FAISS knowledge retriever.

PRD refs: Section 7.1 Stage 3, FR-03:
    - Maintain a FAISS IVF index of multilingual Wikipedia passages
    - Retrieve top-10 candidate passages per claim within 100ms
    - Support index updates without a full rebuild (incremental indexing)

This wraps FAISS's IndexIVFFlat. Note IVF indexes need to be *trained*
on a representative sample of vectors before you can add to them —
that's why `build_index` takes an initial batch, and `add_passages`
is separate for incremental additions afterward.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import faiss
import numpy as np

EMBEDDING_DIM = 768  # matches XLM-R-large / MuRIL output (member1_model/embeddings.py)
DEFAULT_TOP_K = 10
TARGET_LATENCY_MS = 100  # FR-03 target


@dataclass
class RetrievedPassage:
    passage_id: str
    text: str
    score: float  # similarity score (higher = closer match)


@dataclass
class RetrievalResult:
    claim_id: str
    passages: list[RetrievedPassage]
    latency_ms: float
    met_latency_target: bool


class FAISSRetriever:
    """
    Usage:
        retriever = FAISSRetriever()
        retriever.build_index(passage_ids=[...], texts=[...], vectors=initial_vectors)
        retriever.add_passages(passage_ids=[...], texts=[...], vectors=more_vectors)  # incremental
        result = retriever.retrieve(claim_id="c1", query_vector=embedding, top_k=10)
    """

    def __init__(self, dim: int = EMBEDDING_DIM, n_clusters: int = 100):
        self.dim = dim
        self.n_clusters = n_clusters
        self._index: faiss.IndexIVFFlat | None = None
        self._passage_ids: list[str] = []
        self._passage_texts: dict[str, str] = {}
        self._is_trained = False

    def build_index(
        self, passage_ids: list[str], texts: list[str], vectors: np.ndarray
    ) -> None:
        """
        Trains the IVF index on the given vectors and adds them. Needs a
        reasonably sized initial batch — IVF clustering quality suffers if
        trained on too few vectors relative to n_clusters (FAISS recommends
        at least ~40x n_clusters training points as a rule of thumb).
        """
        if vectors.shape[0] < self.n_clusters:
            # Fall back to a flat (brute-force) index for small corpora —
            # avoids FAISS's "not enough training points" failure during
            # early development / unit tests, and IVF's speed advantage
            # only matters at real scale (millions of passages) anyway.
            self.n_clusters = max(1, vectors.shape[0] // 2) or 1

        quantizer = faiss.IndexFlatIP(self.dim)  # inner product = cosine sim on unit vectors
        self._index = faiss.IndexIVFFlat(quantizer, self.dim, self.n_clusters, faiss.METRIC_INNER_PRODUCT)

        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        self._index.train(vectors)
        self._index.add(vectors)
        self._is_trained = True

        self._passage_ids.extend(passage_ids)
        for pid, text in zip(passage_ids, texts):
            self._passage_texts[pid] = text

    def add_passages(self, passage_ids: list[str], texts: list[str], vectors: np.ndarray) -> None:
        """Incremental indexing — add new passages without rebuilding (FR-03)."""
        if not self._is_trained:
            raise RuntimeError("Index must be built with build_index() before adding incrementally")
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        self._index.add(vectors)
        self._passage_ids.extend(passage_ids)
        for pid, text in zip(passage_ids, texts):
            self._passage_texts[pid] = text

    def retrieve(
        self, claim_id: str, query_vector: np.ndarray, top_k: int = DEFAULT_TOP_K
    ) -> RetrievalResult:
        if not self._is_trained:
            raise RuntimeError("Index has not been built yet")

        start = time.perf_counter()

        query = np.ascontiguousarray(query_vector.reshape(1, -1), dtype=np.float32)
        # nprobe controls how many IVF clusters are searched — higher = more
        # accurate but slower. Search all clusters for small indexes (cheap),
        # scale down the fraction for large ones to stay near the 100ms target.
        self._index.nprobe = min(self.n_clusters, max(1, self.n_clusters // 4) or 1)

        scores, indices = self._index.search(query, min(top_k, len(self._passage_ids)))
        latency_ms = (time.perf_counter() - start) * 1000

        passages = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # FAISS pads with -1 when fewer than top_k results exist
                continue
            pid = self._passage_ids[idx]
            passages.append(
                RetrievedPassage(passage_id=pid, text=self._passage_texts[pid], score=float(score))
            )

        return RetrievalResult(
            claim_id=claim_id,
            passages=passages,
            latency_ms=latency_ms,
            met_latency_target=latency_ms < TARGET_LATENCY_MS,
        )

    def __len__(self) -> int:
        return len(self._passage_ids)
