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
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from member1_model.cmhsa import (
    CMHSAScorer, ClaimScore, ClaimSubScores, DocumentSummary, Verdict, aggregate_document,
)
from member1_model.embeddings import CrossLingualEmbedder
from member1_model.nli_scorer import NLIScorer
from member2_data.entity_linker import EntityLinker
from member2_data.wikidata_connector import WikidataConnector
from member3_backend.claim_extractor import ClaimExtractor, ExtractedClaim
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
# MEASURED (IMPROVEMENT_PLAN.md Phase 2.2, results/retrieval_comparison.md and
# results/retrieval_bottleneck.md): with XLM-R, 0.3 keeps ~100% of both
# relevant and irrelevant best passages -- in practice it filters nothing.
# The train-fitted cut-off (0.66) would drop ~half the relevant evidence and
# 45% of claims, and NLI is no better on the claims it keeps (AUC 0.567 vs
# 0.496, overlapping CIs). So 0.3 is kept deliberately, as "effectively no
# filter"; revisit only if the encoder or NLI model changes.
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

# --- C2-lite: sentence-level NLI premises -----------------------------------
# The retrieval diagnostic found the claim's source article reaches NLI's top-3
# for ~73% of claims, yet ~67% of claim-passage NLI pairs land in "neutral":
# the evidence is arriving, but a whole multi-sentence passage is too long for
# NLI to use -- the one relevant sentence gets diluted by the surrounding text.
# So we split each retrieved passage into sentences and send each sentence as
# its own premise, then keep the most decisive one (the SAME selection rule as
# before). Cap sentences per passage so a long passage cannot blow up the batch.
# Gated behind SATYASCORE_SENTENCE_PREMISES (default OFF) so the live API keeps
# its old behaviour until the A/B comparison justifies turning this on.
MAX_SENTENCES_PER_PASSAGE = 8


def _sentence_premises_enabled() -> bool:
    """Switch (default OFF). The live API keeps the original whole-passage NLI
    behaviour until the c2_lite_compare.py A/B run (on GPU) shows sentence-level
    premises actually improve NLI AUC. Set SATYASCORE_SENTENCE_PREMISES=true to
    turn C2-lite on -- that is exactly what the comparison does -- without
    editing code."""
    import os
    return os.environ.get("SATYASCORE_SENTENCE_PREMISES", "false").strip().lower() \
        in ("1", "true", "yes", "on")


def passage_to_premises(passage_text: str, sentence_level: bool | None = None) -> list[str]:
    """Turn one retrieved passage into the NLI premise unit(s) for it.

    sentence_level ON (C2-lite): split into sentences -- reusing the same
    _SENTENCE_SPLIT already used for Hindi claim extraction, so English and Hindi
    are handled identically and no new dependency is added -- and cap at
    MAX_SENTENCES_PER_PASSAGE. sentence_level OFF (the current default): the whole
    passage as a single premise (the pre-C2-lite behaviour).

    This is the SHARED definition used by both the live pipeline and the
    c2_lite_compare.py A/B diagnostic, so the diagnostic measures exactly what
    the pipeline does.
    """
    if sentence_level is None:
        sentence_level = _sentence_premises_enabled()
    if not sentence_level:
        return [passage_text]
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(passage_text) if s.strip()]
    if not sentences:  # nothing splittable -- fall back to the whole passage
        return [passage_text]
    return sentences[:MAX_SENTENCES_PER_PASSAGE]


def _naive_split_into_claims(text: str) -> list[ExtractedClaim]:
    """Fallback for languages the real ClaimExtractor doesn't support yet.
    Produces ExtractedClaim objects with real character offsets into `text`
    so the frontend can highlight each claim in place."""
    claims: list[ExtractedClaim] = []
    cursor = 0
    counter = 0
    for part in _SENTENCE_SPLIT.split(text):
        s = part.strip()
        if not s:
            continue
        start = text.find(s, cursor)
        if start == -1:
            start = cursor
        end = start + len(s)
        cursor = end
        claims.append(ExtractedClaim(
            claim_id=f"claim_{counter}", text=s, start_char=start, end_char=end,
            extraction_method="sentence_level",
        ))
        counter += 1
    return claims


@dataclass
class PipelineResult:
    claims: list[ExtractedClaim]  # carry spans (start_char/end_char) through to the API
    scores: list[ClaimScore]
    sub_scores: list[ClaimSubScores]  # raw per-signal values, e.g. for dataset export
    overall_score: float
    processing_time_ms: float
    # Per-stage timings (ms): claim_extraction, embedding, retrieval, nli, kg, fusion, total.
    timings_ms: dict[str, float] = field(default_factory=dict)
    document: DocumentSummary | None = None  # whole-text verdict (worst-claim rule)


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
        retriever_muril: FAISSRetriever | None = None,
    ):
        self.embedder = embedder
        self.retriever = retriever
        # FR-02: MuRIL fallback for transliterated Hindi. Only enabled when a
        # MuRIL-embedded copy of the corpus is supplied, so a MuRIL query is
        # always searched against MuRIL vectors (never across vector spaces).
        self.retriever_muril = retriever_muril
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
        timings = {k: 0.0 for k in
                   ("claim_extraction", "embedding", "retrieval", "nli", "kg", "fusion", "total")}
        t_start = time.perf_counter()

        t = time.perf_counter()
        extracted = self._extract_claims(text, language)
        timings["claim_extraction"] = (time.perf_counter() - t) * 1000
        if not extracted:
            raise ValueError("No claims could be extracted from the input text")

        claim_texts = [c.text for c in extracted]
        claim_ids = [f"claim_{i}" for i in range(len(claim_texts))]
        languages = [language] * len(claim_texts)

        t = time.perf_counter()
        embedding_result = self.embedder.embed(
            claim_ids, claim_texts, languages, use_muril=self.retriever_muril is not None)
        timings["embedding"] = (time.perf_counter() - t) * 1000

        enabled = active_signals or self._default_enabled_signals()

        # --- Phase A: retrieval + relevance + SemSim + KG (per claim); collect NLI pairs ---
        # NLI is deliberately NOT called in this loop. We gather every
        # (claim, passage) pair across ALL claims first, then run ONE batched NLI
        # pass over the whole document in Phase B. This turns a 10-claim request
        # from 10 forward passes into 1 -- the dominant latency win -- without
        # changing any score (each pair is still scored independently).
        per_claim: list[dict] = []
        nli_pairs: list[tuple[int, str, str, str]] = []  # (claim_idx, claim_id, premise, hypothesis)
        for i, claim_id in enumerate(claim_ids):
            claim_text = claim_texts[i]
            t = time.perf_counter()
            retriever = (self.retriever_muril if embedding_result.model_used[i] == "muril"
                         else self.retriever)
            retrieval = retriever.retrieve(claim_id, embedding_result.vectors[i], top_k=self.nli_top_k)
            timings["retrieval"] += (time.perf_counter() - t) * 1000

            relevant_passages = [p for p in retrieval.passages if p.score >= MIN_RELEVANCE_THRESHOLD]

            sem_sim = None
            if "semsim" in enabled and relevant_passages:
                # SemSim still uses only the single best match -- it's
                # measuring "how close is the nearest relevant evidence",
                # which is inherently a top-1 question, unlike NLI below.
                sem_sim = max(0.0, min(1.0, relevant_passages[0].score))

            kg_conf = None
            if "kg" in enabled and self.entity_linker and self.wikidata:
                t = time.perf_counter()
                kg_conf = self._try_kg_verification(claim_id, claim_text, language)
                timings["kg"] += (time.perf_counter() - t) * 1000

            per_claim.append({"sem_sim": sem_sim, "nli_prob": None, "kg_conf": kg_conf})
            if "nli" in enabled and self.nli_scorer and relevant_passages:
                # C2-lite: each passage becomes one-or-more premise units
                # (sentences when the switch is on; otherwise the whole passage,
                # which is the default). They stay in the single flattened
                # batch below; Phase B still keeps the most decisive unit per
                # claim, so a claim with many sentence-premises is unchanged in
                # how its final nli_prob is chosen.
                for p in relevant_passages:
                    for premise in passage_to_premises(p.text):
                        nli_pairs.append((i, claim_id, premise, claim_text))

        # --- Phase B: a SINGLE batched NLI call over every claim's pairs, then regroup ---
        if nli_pairs:
            t = time.perf_counter()
            nli_results = self.nli_scorer.score_batch(
                claim_ids=[cid for (_, cid, _, _) in nli_pairs],
                premises=[prem for (_, _, prem, _) in nli_pairs],
                hypotheses=[hyp for (_, _, _, hyp) in nli_pairs],
            )
            timings["nli"] = (time.perf_counter() - t) * 1000

            grouped: dict[int, list] = defaultdict(list)
            for (idx, _, _, _), res in zip(nli_pairs, nli_results):
                grouped[idx].append(res)
            for idx, results in grouped.items():
                # CRITICAL (unchanged): nli_prob reflects BOTH directions of
                # evidence. Net score: 1.0 = strongly entailed, 0.0 = strongly
                # contradicted, 0.5 = neutral/unaddressed. We pick the MOST
                # DECISIVE passage (furthest from 0.5), not max entailment --
                # this and the formula are identical to the pre-batching code.
                net_scores = [0.5 + 0.5 * (r.entailment_prob - r.contradiction_prob) for r in results]
                per_claim[idx]["nli_prob"] = max(net_scores, key=lambda s: abs(s - 0.5))

        # --- Phase C: assemble sub-scores (original claim order) + fuse ---
        sub_scores_list = [
            ClaimSubScores(claim_id=claim_ids[i], sem_sim=per_claim[i]["sem_sim"],
                           nli_prob=per_claim[i]["nli_prob"], kg_conf=per_claim[i]["kg_conf"])
            for i in range(len(claim_ids))
        ]

        t = time.perf_counter()
        scores = []
        for sub_scores in sub_scores_list:
            try:
                scores.append(self.scorer.score_claim(sub_scores, language))
            except ValueError:
                # All signals unavailable for this claim -- usually no sufficiently
                # relevant evidence (MIN_RELEVANCE_THRESHOLD) and KG didn't resolve.
                # Surface as Uncertain rather than crash the whole /detect request.
                scores.append(ClaimScore(
                    claim_id=sub_scores.claim_id,
                    hallu_score=0.5,
                    verdict=Verdict.UNCERTAIN,
                    active_signals=[],
                    note="insufficient evidence: no sufficiently relevant passage found in the corpus",
                ))
        # overall_score (mean) is kept for backward compatibility; `document`
        # is the whole-text verdict and should be what a reader looks at.
        overall_score = sum(s.hallu_score for s in scores) / len(scores)
        document = aggregate_document([s.verdict for s in scores])
        timings["fusion"] = (time.perf_counter() - t) * 1000
        timings["total"] = (time.perf_counter() - t_start) * 1000

        return PipelineResult(
            claims=extracted,
            scores=scores,
            sub_scores=sub_scores_list,
            overall_score=overall_score,
            processing_time_ms=timings["total"],
            timings_ms=timings,
            document=document,
        )

    def _extract_claims(self, text: str, language: Language) -> list[ExtractedClaim]:
        if self.claim_extractor is not None:
            try:
                return list(self.claim_extractor.extract(text, language))
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
        # No known relation phrase -> the claim can never link. Return before
        # any network call (this was ~1 s of Wikidata lookups per claim).
        if not self.entity_linker.find_relation_pid(claim_text):
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