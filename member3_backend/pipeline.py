"""
End-to-end orchestration: text -> claims -> embeddings -> evidence -> HalluScore.

PRD ref: Section 7.1, the full 5-stage pipeline.

STATUS — what's real vs. still-limited, per signal:
  - Claim extraction (Stage 1): REAL for English (member3_backend
    .claim_extractor, dependency-parse-based, spaCy). Falls back to a
    naive sentence splitter for languages the real extractor doesn't
    support yet (Hindi/Marathi — see claim_extractor.py).
  - Embedding (Stage 2): REAL — member1_model.embeddings (XLM-R/MuRIL).
  - SemSim: REAL — derived from the FAISS top-1 retrieval score.
  - NLI_prob: REAL, using a pretrained multilingual NLI model as a
    stand-in for the project's own DeBERTa+IndicXNLI fine-tune (see
    member1_model/nli_scorer.py docstring for why). Scored against up to
    NLI_EVIDENCE_TOP_K relevant passages (not just the single best SemSim
    match), taking the best entailment found -- added after diagnosing
    that nli_prob showed almost no separation between Hallucinated and
    Verified claims in initial training (correlation ~0.03), traced to
    the top-1-only passage often being topically right but not containing
    the specific fact a claim needed.
  - KG_conf: REAL, but SHALLOW — only resolves when the claim contains
    >=2 named entities AND its relation phrase matches the small lookup
    table in member2_data/entity_linker.py. Most claims outside that
    table will get kg_conf=None, which CMHSAScorer correctly handles by
    re-normalising over whichever signals ARE available (SemSim + NLI).
    This is an honest reflection of entity/relation linking being a hard,
    only-partially-solved problem here — not a bug.

All three optional components (nli_scorer, entity_linker, wikidata) can be
omitted (left as None) to run a lighter-weight pipeline, e.g. for fast
local testing without loading the NLI model.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Literal

from member1_model.cmhsa import CMHSAScorer, ClaimScore, ClaimSubScores, Verdict
from member1_model.embeddings import CrossLingualEmbedder
from member1_model.nli_scorer import NLIScorer
from member2_data.entity_linker import EntityLinker
from member2_data.wikidata_connector import WikidataConnector
from member3_backend.claim_extractor import ClaimExtractor
from member3_backend.faiss_retriever import FAISSRetriever

Language = Literal["en", "hi", "mr"]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+")  # includes Hindi danda (।)

# Below this FAISS top-1 similarity score, the retrieved passage is treated
# as "no relevant evidence found" rather than as a real (if weak) signal.
# Without this, the pipeline always uses its nearest neighbour even when
# nothing in the corpus is actually about the claim's topic (this was the
# exact mechanism behind the original "Modi is PM of india" bug: SemSim
# confidently compared against the Nehru article purely because it was the
# closest thing available, not because it was relevant).
#
# NOTE: 0.3 is a reasonable starting point for cosine similarity between
# genuinely unrelated multilingual-embedding text, but embedding spaces are
# not perfectly calibrated (unrelated pairs don't reliably sit near 0) --
# this should be tuned empirically once real query traffic or a labeled
# relevance set is available, not treated as a validated constant.
MIN_RELEVANCE_THRESHOLD = 0.3

# How many top passages to check NLI against, instead of just the single
# best SemSim match. Rationale: the top-ranked passage by SemSim can be
# topically correct but still not contain the SPECIFIC fact a claim needs
# (a date, a name, a number) -- checking a few candidates gives NLI more
# chances to actually find supporting/contradicting evidence, rather than
# scoring against whichever passage happened to rank #1 on a different
# metric (semantic similarity, not evidential sufficiency).
# NOTE: this makes NLI scoring ~Nx slower per claim (one model forward
# pass per passage checked) -- fine for research/eval, worth revisiting
# if this pipeline needs to be snappy for a live demo.
NLI_EVIDENCE_TOP_K = 3


def _naive_split_into_claims(text: str) -> list[str]:
    """Fallback for languages the real ClaimExtractor doesn't support yet."""
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


@dataclass
class PipelineResult:
    claims: list[str]
    scores: list[ClaimScore]
    sub_scores: list[ClaimSubScores]  # raw per-signal values, e.g. for dataset export
    overall_score: float
    processing_time_ms: float


class DetectionPipeline:
    def __init__(
        self,
        embedder: CrossLingualEmbedder,
        retriever: FAISSRetriever,
        scorer: CMHSAScorer,
        claim_extractor: ClaimExtractor | None = None,
        nli_scorer: NLIScorer | None = None,
        entity_linker: EntityLinker | None = None,
        wikidata: WikidataConnector | None = None,
        nli_top_k: int = NLI_EVIDENCE_TOP_K,
    ):
        self.embedder = embedder
        self.retriever = retriever
        self.scorer = scorer
        self.claim_extractor = claim_extractor
        self.nli_scorer = nli_scorer
        self.entity_linker = entity_linker
        self.wikidata = wikidata
        # How many passages to check per claim. Default 3 (best accuracy, used
        # by the research/eval path); the live API sets 1 to cut latency ~3x.
        self.nli_top_k = nli_top_k

    def run(
        self,
        text: str,
        language: Language,
        active_signals: set[str] | None = None,
    ) -> PipelineResult:
        """
        active_signals: for ablation mode (FR-04). e.g. {"semsim"} to run
        SemSim-only, {"semsim", "nli"} to test without KG, etc. Defaults to
        every signal this pipeline instance is actually configured with.
        """
        start = time.perf_counter()

        claim_texts = self._extract_claims(text, language)
        if not claim_texts:
            raise ValueError("No claims could be extracted from the input text")

        claim_ids = [f"claim_{i}" for i in range(len(claim_texts))]
        languages = [language] * len(claim_texts)

        embedding_result = self.embedder.embed(claim_ids, claim_texts, languages)

        enabled = active_signals or self._default_enabled_signals()

        sub_scores_list = []
        for i, claim_id in enumerate(claim_ids):
            claim_text = claim_texts[i]
            query_vector = embedding_result.vectors[i]
            retrieval = self.retriever.retrieve(claim_id, query_vector, top_k=self.nli_top_k)

            relevant_passages = [p for p in retrieval.passages if p.score >= MIN_RELEVANCE_THRESHOLD]
            relevant_evidence_found = bool(relevant_passages)

            sem_sim = None
            if "semsim" in enabled and relevant_evidence_found:
                # SemSim still uses only the single best match -- it's
                # measuring "how close is the nearest relevant evidence",
                # which is inherently a top-1 question, unlike NLI below.
                sem_sim = max(0.0, min(1.0, relevant_passages[0].score))

            nli_prob = None
            if "nli" in enabled and self.nli_scorer and relevant_passages:
                nli_results = self.nli_scorer.score_batch(
                    claim_ids=[claim_id] * len(relevant_passages),
                    premises=[p.text for p in relevant_passages],
                    hypotheses=[claim_text] * len(relevant_passages),
                )
                # CRITICAL: nli_prob must reflect BOTH directions of
                # evidence, not just entailment. A confidently-contradicted
                # claim (e.g. entailment=0.11, contradiction=0.83 -- exactly
                # the real "IPL has 8 teams" hallucination in this project)
                # and a claim the evidence simply doesn't address (neutral)
                # both produce LOW raw entailment_prob -- but only one of
                # them is an actual lie. Discarding contradiction_prob
                # entirely (the previous version of this code) meant CMHSA
                # never got to see the model's strongest, most decisive
                # signal. Net score below: 1.0 = strongly entailed,
                # 0.0 = strongly contradicted, 0.5 = neutral/unaddressed.
                #
                # We also pick whichever passage gives the MOST DECISIVE
                # net score (furthest from neutral 0.5), not whichever
                # passage happens to maximize raw entailment -- naive
                # max(entailment) is vulnerable to a false claim getting
                # spuriously high entailment from just one of several
                # loosely-matching passages, inflating false positives
                # specifically on the Hallucinated class (confirmed via
                # diagnose_nli_signal.py showing Hallucinated claims had
                # HIGHER mean nli_prob than Verified under the old scheme).
                net_scores = [0.5 + 0.5 * (r.entailment_prob - r.contradiction_prob) for r in nli_results]
                nli_prob = max(net_scores, key=lambda s: abs(s - 0.5))

            kg_conf = None
            if "kg" in enabled and self.entity_linker and self.wikidata:
                kg_conf = self._try_kg_verification(claim_id, claim_text, language)

            sub_scores_list.append(
                ClaimSubScores(claim_id=claim_id, sem_sim=sem_sim, nli_prob=nli_prob, kg_conf=kg_conf)
            )

        scores = []
        for sub_scores in sub_scores_list:
            try:
                scores.append(self.scorer.score_claim(sub_scores, language))
            except ValueError:
                # All signals ended up unavailable for this claim -- most
                # likely because no sufficiently relevant evidence existed
                # in the corpus (see MIN_RELEVANCE_THRESHOLD) and KG linking
                # also didn't resolve. This is a per-claim, expected-in-
                # production condition, not the programmer-error case
                # CMHSAScorer.score_claim's raise is meant to catch (e.g.
                # ablation mode misconfigured with zero signals enabled) --
                # so we surface it honestly here rather than let one
                # under-covered claim crash an entire /detect request, and
                # rather than silently score against irrelevant evidence.
                scores.append(ClaimScore(
                    claim_id=sub_scores.claim_id,
                    hallu_score=0.5,
                    verdict=Verdict.UNCERTAIN,
                    active_signals=[],
                    note="insufficient evidence: no sufficiently relevant passage found in the corpus",
                ))
        overall_score = sum(s.hallu_score for s in scores) / len(scores)
        processing_time_ms = (time.perf_counter() - start) * 1000

        return PipelineResult(
            claims=claim_texts,
            scores=scores,
            sub_scores=sub_scores_list,
            overall_score=overall_score,
            processing_time_ms=processing_time_ms,
        )

    def _extract_claims(self, text: str, language: Language) -> list[str]:
        if self.claim_extractor is not None:
            try:
                return [c.text for c in self.claim_extractor.extract(text, language)]
            except NotImplementedError:
                pass  # real extractor doesn't support this language yet — fall back
        return _naive_split_into_claims(text)

    def _default_enabled_signals(self) -> set[str]:
        enabled = {"semsim"}
        if self.nli_scorer:
            enabled.add("nli")
        if self.entity_linker and self.wikidata:
            enabled.add("kg")
        return enabled

    def _try_kg_verification(self, claim_id: str, claim_text: str, language: Language) -> float | None:
        """Returns kg_conf if the claim's entities+relation could be
        resolved to a Wikidata triple, else None (handled gracefully by
        the scorer's renormalisation — see module docstring)."""
        if self.claim_extractor is None:
            return None
        entities = self.claim_extractor.extract_entities(claim_text, language)
        if len(entities) < 2:
            return None

        linked = self.entity_linker.link_claim(
            claim_text=claim_text, subject_text=entities[0], object_text=entities[1], language=language
        )
        if not linked.linkable:
            return None

        verification = self.wikidata.verify_triple(
            subject_qid=linked.subject_qid,
            property_pid=linked.property_pid,
            expected_value=linked.object_qid,
            language=language,
        )
        return verification.confidence