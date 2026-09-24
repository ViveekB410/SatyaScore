"""
Cross-lingual claim embedder.

PRD refs: Section 7.1 Stage 2, FR-02
- XLM-R-large as primary model (768-dim vectors)
- MuRIL as fallback for Hindi, particularly transliterated (Latin-script) text
- Batch embedding up to 128 claims per forward pass
- Unit-normalise embeddings before similarity computation
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

Language = Literal["en", "hi", "mr"]

XLMR_MODEL_NAME = "sentence-transformers/paraphrase-xlm-r-multilingual-v1"
MURIL_MODEL_NAME = "google/muril-base-cased"

MAX_BATCH_SIZE = 128

# Default for embed(use_muril=None). A MuRIL query vector is only comparable to
# MuRIL corpus vectors, so callers enable MuRIL routing (FR-02) exactly when
# they can search a MuRIL-embedded corpus (DetectionPipeline does this when a
# MuRIL index is loaded). Without one, everything goes through XLM-R.
USE_MURIL_FALLBACK = False

# Rough heuristic: if a Hindi-tagged claim is mostly ASCII letters, it's
# likely transliterated (Latin-script) Hindi rather than Devanagari.
_DEVANAGARI_RANGE = re.compile(r"[\u0900-\u097F]")


def _looks_transliterated(text: str) -> bool:
    """Return True if text is tagged as Hindi but contains little/no Devanagari."""
    devanagari_chars = len(_DEVANAGARI_RANGE.findall(text))
    return devanagari_chars < max(1, len(text) // 10)


@dataclass
class EmbeddingResult:
    claim_ids: list[str]
    vectors: np.ndarray  # shape (n, dim), L2-normalised
    model_used: list[str]  # which model produced each row, for debugging/audit


class CrossLingualEmbedder:
    """
    Wraps XLM-R (primary, all languages) and MuRIL (fallback, Hindi
    transliterated text) behind a single embed() call.

    Usage:
        embedder = CrossLingualEmbedder()
        result = embedder.embed(claim_ids=["c1", "c2"],
                                 texts=["The Ganga originates in Gangotri.", ...],
                                 languages=["en", "hi"])
    """

    def __init__(self, device: str | None = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._xlmr: SentenceTransformer | None = None
        self._muril: SentenceTransformer | None = None

    # Lazy loading — don't pull both models into memory until actually needed.
    @property
    def xlmr(self) -> SentenceTransformer:
        if self._xlmr is None:
            self._xlmr = SentenceTransformer(XLMR_MODEL_NAME, device=self.device)
        return self._xlmr

    @property
    def muril(self) -> SentenceTransformer:
        if self._muril is None:
            self._muril = SentenceTransformer(MURIL_MODEL_NAME, device=self.device)
        return self._muril

    def embed(
        self,
        claim_ids: list[str],
        texts: list[str],
        languages: list[Language],
        use_muril: bool | None = None,
    ) -> EmbeddingResult:
        if not (len(claim_ids) == len(texts) == len(languages)):
            raise ValueError("claim_ids, texts, and languages must be the same length")
        if use_muril is None:
            use_muril = USE_MURIL_FALLBACK

        # Route each claim to XLM-R or MuRIL.
        xlmr_idx, muril_idx = [], []
        for i, (text, lang) in enumerate(zip(texts, languages)):
            if use_muril and lang == "hi" and _looks_transliterated(text):
                muril_idx.append(i)
            else:
                xlmr_idx.append(i)

        dim = 768
        vectors = np.zeros((len(texts), dim), dtype=np.float32)
        model_used = [""] * len(texts)

        if xlmr_idx:
            xlmr_texts = [texts[i] for i in xlmr_idx]
            xlmr_vecs = self._batched_encode(self.xlmr, xlmr_texts)
            for pos, i in enumerate(xlmr_idx):
                vectors[i] = xlmr_vecs[pos]
                model_used[i] = "xlm-r"

        if muril_idx:
            muril_texts = [texts[i] for i in muril_idx]
            muril_vecs = self._batched_encode(self.muril, muril_texts)
            for pos, i in enumerate(muril_idx):
                vectors[i] = muril_vecs[pos]
                model_used[i] = "muril"

        vectors = self._normalise(vectors)
        return EmbeddingResult(claim_ids=claim_ids, vectors=vectors, model_used=model_used)

    @staticmethod
    def _batched_encode(model: SentenceTransformer, texts: list[str]) -> np.ndarray:
        chunks = []
        for start in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[start : start + MAX_BATCH_SIZE]
            chunks.append(model.encode(batch, convert_to_numpy=True, show_progress_bar=False))
        return np.vstack(chunks)

    @staticmethod
    def _normalise(vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms
