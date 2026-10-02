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
    HALLUCINATED_THRESHOLD, KG_NOTE, VERIFIED_THRESHOLD, CMHSAScorer, ClaimScore, ClaimSubScores,
    DocumentSummary, Verdict, aggregate_document,
)
from member1_model.embeddings import CrossLingualEmbedder
from member1_model.nli_scorer import NLIScorer
from member2_data.dates import DATE_PID, parse_date
from member2_data.entity_linker import EntityLinker, english_capital_claim
from member2_data.wikidata_connector import WikidataConnector
from member3_backend.claim_extractor import ClaimExtractor, ExtractedClaim
from member3_backend.evidence_rules import RULES as AGGREGATION_RULES, SubjectIndex, deciding, passage_source
from member3_backend.factcheck_rules import FC_FALSE_SCORE, FC_NOTE_PREFIX, FC_TRUE_SCORE
from member3_backend.factcheck_rules import decide as decide_fact_check
from member3_backend.factcheck_rules import match as match_fact_checks
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
MAX_DATE_SUBJECTS = 5  # namesakes checked for a date claim (one Wikidata request each)
MAX_EXCERPT_SENTENCES = 20  # sentences of the deciding passage scanned for the evidence excerpt
# A sentence is quoted only if the NLI gives it at least this much for the deciding
# direction AND it shares a content word with the claim beyond the article's name
# (otherwise the quote would not visibly address the claim, e.g. a sentence about
# Beijing's ring roads for "The capital of Japan is Beijing").
MIN_EXCERPT_PROB = 0.3
_EXCERPT_STOP = set(
    "the and was were is are with that this from for has have had which its his her their also into "
    "been being there other than then they them these those such about after before during most more "
    "many some only who whom whose what when where while known called usually often first".split()
) | set("का की के में है हैं था थी थे और से को ने पर एक यह वह भी हो जाता जाती गया गई किया हुआ हुई लिए तक".split())
_WORD_SPLIT = re.compile(r"[\s,.;:!?।()\[\]\"'“”‘’\-–—/]+")


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD_SPLIT.split(text.casefold()) if len(w) > 2 and w not in _EXCERPT_STOP}


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


def _decided_elsewhere(note: str | None) -> bool:
    """Was this claim's verdict set by the KG, the LLM judge or a fact-check (not by NLI)?"""
    return bool(note) and (note == KG_NOTE or note.startswith(("judged by LLM", FC_NOTE_PREFIX)))


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
    document: DocumentSummary | None = None  # whole-text verdict (hallucinated-share rule)
    # Per claim: the passages checked (rank order) and the one that decided the NLI
    # score, (passage_id, "supports" | "contradicts") or None. Shown as sources.
    evidence: list[dict] = field(default_factory=list)


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
        expander=None,
        llm_verifier=None,
        aggregation: str = "gated",
        subjects: SubjectIndex | None = None,
        fact_checker=None,
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
        # Optional on-demand Wikipedia expansion (member3_backend/wiki_expander.py):
        # adds the articles found by searching each claim to the index before
        # retrieval. The API switches it on by default (results/unseen_eval.md); a
        # pipeline built without an expander does not expand.
        self.expander = expander
        # Optional LLM judge (member1_model/llm_verifier.py): for every claim the KG
        # did not decide, the LLM's verdict and P(true) on the same passages replace
        # the NLI-based result. Off by default; adopted only if llm_verifier_eval.py
        # meets its fixed rule. On any LLM failure the claim keeps its NLI result.
        self.llm_verifier = llm_verifier
        # How per-passage NLI becomes one claim score (member3_backend/evidence_rules.py):
        # "legacy" = the most decisive passage wins; "gated" = support first, and only
        # an on-topic passage (its article title appears in the claim) may contradict.
        if aggregation not in AGGREGATION_RULES:
            raise ValueError(f"aggregation must be one of {list(AGGREGATION_RULES)}")
        self.aggregation = aggregation
        self.subjects = subjects or SubjectIndex(strict=True)
        # Optional professional fact-checks (member2_data/factcheck.py): a fact-check
        # of THE SAME claim with a clear rating decides it (member3_backend/
        # factcheck_rules.py), for every claim the KG did not decide. None here; the
        # API switches it on (it met its fixed rule, results/factcheck_eval.md).
        self.fact_checker = fact_checker

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
                   ("claim_extraction", "expansion", "embedding", "retrieval", "nli", "kg", "llm",
                    "factcheck", "explain", "fusion", "total")}
        t_start = time.perf_counter()

        t = time.perf_counter()
        extracted = self._extract_claims(text, language)
        timings["claim_extraction"] = (time.perf_counter() - t) * 1000
        if not extracted:
            raise ValueError("No claims could be extracted from the input text")

        claim_texts = [c.text for c in extracted]
        claim_ids = [f"claim_{i}" for i in range(len(claim_texts))]
        languages = [language] * len(claim_texts)

        if self.expander is not None:
            t = time.perf_counter()
            self.expander.expand(list(zip(claim_texts, languages)))  # never raises; failures are skipped
            timings["expansion"] = (time.perf_counter() - t) * 1000

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
        on_topic: list[bool] = []  # per NLI pair: is its passage about the claim's subject?
        pair_pid: list[str] = []   # per NLI pair: the passage it came from
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

            kg_conf, kg_v = None, None
            if "kg" in enabled and self.entity_linker and self.wikidata:
                t = time.perf_counter()
                kg_conf, kg_v = self._kg_lookup(claim_text, language)
                timings["kg"] += (time.perf_counter() - t) * 1000

            per_claim.append({"sem_sim": sem_sim, "nli_prob": None, "kg_conf": kg_conf, "kg_v": kg_v,
                              "passages": [p.text for p in relevant_passages],
                              "passage_ids": [p.passage_id for p in relevant_passages], "deciding": None})
            if "nli" in enabled and self.nli_scorer and relevant_passages:
                # C2-lite: each passage becomes one-or-more premise units
                # (sentences when the switch is on; otherwise the whole passage,
                # which is the default). They stay in the single flattened
                # batch below; Phase B still keeps the most decisive unit per
                # claim, so a claim with many sentence-premises is unchanged in
                # how its final nli_prob is chosen.
                for p in relevant_passages:
                    topical = self.subjects.on_topic(claim_text, p.passage_id)
                    for premise in passage_to_premises(p.text):
                        nli_pairs.append((i, claim_id, premise, claim_text))
                        on_topic.append(topical)
                        pair_pid.append(p.passage_id)

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
            for (idx, _, _, _), res, topical, pid in zip(nli_pairs, nli_results, on_topic, pair_pid):
                grouped[idx].append((res.entailment_prob, res.contradiction_prob, topical, pid))
            rule = AGGREGATION_RULES[self.aggregation]
            for idx, rows in grouped.items():
                # nli_prob reflects both directions of evidence: 1.0 = entailed,
                # 0.0 = contradicted, 0.5 = neutral / not addressed. How the
                # passages combine is the aggregation rule (evidence_rules.py).
                per_claim[idx]["nli_prob"] = rule([r[:3] for r in rows])
                per_claim[idx]["deciding"] = deciding(rows, self.aggregation)

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
        if self.llm_verifier is not None:
            t_llm = time.perf_counter()
            scores = [s if s.note == KG_NOTE else self._llm_judge(s, claim_texts[i], per_claim[i]["passages"])
                      for i, s in enumerate(scores)]
            timings["llm"] = (time.perf_counter() - t_llm) * 1000
        fact_checks: list[dict | None] = [None] * len(scores)
        if self.fact_checker is not None and self.nli_scorer is not None:
            t_fc = time.perf_counter()
            for i, s in enumerate(scores):
                if s.note == KG_NOTE:
                    continue
                scores[i], fact_checks[i] = self._fact_check(s, claim_texts[i], language)
            timings["factcheck"] = (time.perf_counter() - t_fc) * 1000

        # --- Explanation only (no verdict changes): the evidence sentence of the
        # passage that decided each NLI-decided claim, and the fact Wikidata holds
        # for each KG-decided claim (e.g. the correct birthplace).
        t_ex = time.perf_counter()
        nli_decided = [not _decided_elsewhere(s.note) for s in scores]
        excerpts: list[str | None] = [None] * len(scores)
        if self.nli_scorer is not None and any(nli_decided):
            excerpts = self._excerpts(claim_texts, [pc if ok else {**pc, "deciding": None}
                                                    for pc, ok in zip(per_claim, nli_decided)])
        for i, fc in enumerate(fact_checks):  # fact-checked: the claim the fact-checker checked
            if fc:
                excerpts[i] = fc["claim_text"] or None
        kg_facts = [self._kg_fact(pc["kg_v"], language) if s.note == KG_NOTE else None
                    for pc, s in zip(per_claim, scores)]
        timings["explain"] = (time.perf_counter() - t_ex) * 1000

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
            evidence=[{"passage_ids": pc["passage_ids"], "deciding": pc["deciding"], "fact_check": fc,
                       "excerpt": ex, "kg_fact": kf}
                      for pc, fc, ex, kf in zip(per_claim, fact_checks, excerpts, kg_facts)],
        )

    def _fact_check(self, score: ClaimScore, claim_text: str, language: Language
                    ) -> tuple[ClaimScore, dict | None]:
        """A fact-check of the same claim with a clear rating replaces the score;
        otherwise (none found, none matching, mixed rating, lookup failed) it stays."""
        try:
            checks = self.fact_checker.search(claim_text, language)
            m = decide_fact_check(match_fact_checks(claim_text, language, checks, self.embedder, self.nli_scorer))
        except Exception:
            return score, None
        if m is None:
            return score, None
        fc = m.check
        false = fc.verdict == "false"
        info = {"publisher": fc.publisher, "rating": fc.rating, "url": fc.url, "claim_text": fc.claim_text,
                "verdict": fc.verdict}
        return ClaimScore(
            claim_id=score.claim_id, hallu_score=FC_FALSE_SCORE if false else FC_TRUE_SCORE,
            verdict=Verdict.HALLUCINATED if false else Verdict.VERIFIED,
            active_signals=[*score.active_signals, "factcheck"],
            note=f"{FC_NOTE_PREFIX} {fc.publisher or 'a fact-checker'}: rated \"{fc.rating}\"",
        ), info

    def _llm_judge(self, score: ClaimScore, claim_text: str, passages: list[str]) -> ClaimScore:
        """The LLM's verdict for one claim (the KG did not decide it). Falls back to
        the NLI-based score, with a note, if the LLM is unavailable or unparsable."""
        model = getattr(self.llm_verifier, "model", "LLM")
        try:
            j = self.llm_verifier.verify(claim_text, passages)
        except Exception:
            return ClaimScore(claim_id=score.claim_id, hallu_score=score.hallu_score, verdict=score.verdict,
                              active_signals=score.active_signals,
                              note="LLM judge unavailable (key, quota or network); NLI result used")
        if j.p_true is None:
            return score
        verdict = Verdict(j.verdict) if j.verdict else (
            Verdict.HALLUCINATED if j.p_true < HALLUCINATED_THRESHOLD else
            Verdict.VERIFIED if j.p_true > VERIFIED_THRESHOLD else Verdict.UNCERTAIN)
        note = f"judged by LLM ({model}) from the retrieved passages"
        if j.reason:
            note += f": {j.reason}"
        return ClaimScore(claim_id=score.claim_id, hallu_score=float(j.p_true), verdict=verdict,
                          active_signals=[*score.active_signals, "llm"], note=note)

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
        return self._kg_lookup(claim_text, language)[0]

    def _kg_lookup(self, claim_text: str, language: Language):
        """(kg_conf, TripleVerification | None): the verification is kept so the
        API can show the fact Wikidata holds (e.g. the correct birthplace)."""
        if language == "hi":
            return self._kg_lookup_hi(claim_text)
        cap = english_capital_claim(claim_text)
        if cap:  # capital claims: checked from the country's side (entity_linker.CAPITAL_PID)
            linked = self.entity_linker.link_capital(*cap, language)
            if not linked.linkable:
                return None, None
            v = self.wikidata.verify_triple(subject_qid=linked.subject_qid, property_pid=linked.property_pid,
                                            expected_value=linked.object_qid, language=language,
                                            alternatives=linked.object_candidates)
            return v.confidence, v
        if self.claim_extractor is None:
            return None, None
        # No known relation phrase -> the claim can never link. Return before
        # any network call (this was ~1 s of Wikidata lookups per claim).
        if not self.entity_linker.find_relation_pid(claim_text):
            return None, None
        entities = self.claim_extractor.extract_entities(claim_text, language)
        if len(entities) < 2:
            return None, None
        pid = self.entity_linker.find_relation_pid(claim_text)
        if pid in DATE_PID and (when := parse_date(entities[1])) is not None:
            # "born in 1869" / "died on 27 May 1964" / "founded in 1885": a date, not a place
            return self._date_lookup(re.sub(r"^the\s+", "", entities[0], flags=re.I), DATE_PID[pid], when, language)

        linked = self.entity_linker.link_claim(
            claim_text=claim_text, subject_text=entities[0], object_text=entities[1], language=language
        )
        if not linked.linkable:
            return None, None

        verification = self.wikidata.verify_triple(
            subject_qid=linked.subject_qid,
            property_pid=linked.property_pid,
            expected_value=linked.object_qid,
            language=language,
            alternatives=linked.object_candidates,
        )
        return verification.confidence, verification

    def _try_kg_verification_hi(self, claim_text: str) -> float | None:
        return self._kg_lookup_hi(claim_text)[0]

    def _kg_lookup_hi(self, claim_text: str):
        """Hindi: template-based relation + exact Hindi-name linking
        (EntityLinker.link_hindi_claim). The first same-named subject with a
        definite answer is used; a namesake with no value gives no signal."""
        from member2_data.entity_linker import hindi_date_claim, hindi_relation_candidates
        if (dated := hindi_date_claim(claim_text)) is not None:  # "X का जन्म 1869 में हुआ": a date
            subject_text, when, date_pid = dated
            return self._date_lookup(subject_text, date_pid, when, "hi")
        if not hindi_relation_candidates(claim_text):  # no template fits: no network call
            return None, None
        for linked in self.entity_linker.link_hindi_claim(claim_text):
            v = self.wikidata.verify_triple(
                subject_qid=linked.subject_qid, property_pid=linked.property_pid,
                expected_value=linked.object_qid, language="hi",
                alternatives=linked.object_candidates)
            if v.status in ("supported", "contradicted"):
                return v.confidence, v
        return None, None

    def _date_lookup(self, subject_text: str, date_pid: str, when: tuple, language: Language):
        """A claimed date against every item named exactly `subject_text` (at most
        MAX_DATE_SUBJECTS): supported if any namesake's date agrees, contradicted only
        if every namesake with a date on record disagrees, else no signal. A top search
        hit is not trusted here: for "The Indian National Congress" it was a book."""
        subjects = (self.entity_linker.search_places(subject_text, language) or ())[:MAX_DATE_SUBJECTS]
        results = [self.wikidata.verify_date(s, date_pid, when, language) for s in subjects]
        if supported := [v for v in results if v.status == "supported"]:
            return supported[0].confidence, supported[0]
        dated = [v for v in results if v.actual_text]  # namesakes with a date on record
        if dated and all(v.status == "contradicted" for v in dated):
            return dated[0].confidence, dated[0]
        return None, None

    def _kg_fact(self, v, language: Language) -> dict | None:
        """The fact Wikidata holds, named in the claim's language (English fallback):
        {subject, property, values, status, url}. None if it cannot be named."""
        if v is None or v.status not in ("supported", "contradicted") or not (v.actual_values or v.actual_text):
            return None
        try:
            names = self.wikidata.labels([v.subject_qid, v.property_pid, *v.actual_values], language)
        except Exception:
            return None
        values = list(v.actual_text) or [names[q] for q in v.actual_values if q in names]
        if v.subject_qid not in names or v.property_pid not in names or not values:
            return None
        return {"subject": names[v.subject_qid], "property": names[v.property_pid], "values": values,
                "status": v.status, "url": f"https://www.wikidata.org/wiki/{v.subject_qid}"}

    def _excerpts(self, claim_texts: list[str], per_claim: list[dict]) -> list[str | None]:
        """For each claim decided by a passage: the one sentence of that passage that
        most supports (or contradicts) the claim, by NLI, to show as the evidence.
        Explanation only: the verdict was already decided on the whole passage."""
        out: list[str | None] = [None] * len(per_claim)
        pairs: list[tuple[int, str, str]] = []  # (claim index, sentence, role)
        for i, pc in enumerate(per_claim):
            dec = pc.get("deciding")
            if not dec or dec[0] not in pc["passage_ids"]:
                continue
            text = pc["passages"][pc["passage_ids"].index(dec[0])]
            hi_titles = getattr(getattr(self, "subjects", None), "hi_titles", None) or {}
            title_words = (_content_words(passage_source(dec[0], {})[0])
                           | _content_words(passage_source(dec[0], hi_titles)[0]))
            claim_words = _content_words(claim_texts[i]) - title_words
            sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if len(s.strip()) > 15][:MAX_EXCERPT_SENTENCES]
            pairs += [(i, s, dec[1]) for s in sentences if claim_words & _content_words(s)]
        if not pairs:
            return out
        try:
            res = self.nli_scorer.score_batch(claim_ids=[f"ex{k}" for k in range(len(pairs))],
                                              premises=[s for _, s, _ in pairs],
                                              hypotheses=[claim_texts[i] for i, _, _ in pairs])
        except Exception:
            return out
        best: dict[int, tuple[float, str]] = {}
        for (i, s, role), r in zip(pairs, res):
            p = r.entailment_prob if role == "supports" else r.contradiction_prob
            if p >= MIN_EXCERPT_PROB and (i not in best or p > best[i][0]):
                best[i] = (p, s)
        for i, (_, s) in best.items():
            out[i] = s
        return out