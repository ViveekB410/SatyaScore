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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from typing import Literal

from member1_model.cmhsa import (
    HALLUCINATED_THRESHOLD, KG_NOTE, VERIFIED_THRESHOLD, CMHSAScorer, ClaimScore, ClaimSubScores,
    DocumentSummary, Verdict, aggregate_document,
)
from member1_model.embeddings import CrossLingualEmbedder
from member1_model.nli_scorer import NLIScorer
from member2_data import kg_extra, official_stats
from member2_data.dates import DATE_PID, parse_date
from member2_data.entity_linker import CAPITAL_PID, EntityLinker, english_capital_claim
from member2_data.wikidata_connector import WikidataConnector
from member3_backend.claim_extractor import ClaimExtractor, ExtractedClaim
from member3_backend.crosscheck import crosscheck_verdict, llm_verdict_used, second_reading_candidate
from member3_backend.evidence_rules import RULES as AGGREGATION_RULES, SubjectIndex, deciding, passage_source
from member3_backend.factcheck_rules import FC_FALSE_SCORE, FC_NOTE_PREFIX, FC_TRUE_SCORE
from member3_backend.factcheck_rules import decide as decide_fact_check
from member3_backend.factcheck_rules import match as match_fact_checks
from member3_backend.faiss_retriever import FAISSRetriever
from member3_backend.number_guard import NUMBER_NOTE, missing_numbers

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
MAX_PARALLEL_LOOKUPS = 6  # claims whose knowledge-graph / fact-check lookups run at the same time
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


def _same_article_texts(pc: dict, deciding_pid: str) -> list[str]:
    """The retrieved passages from the same Wikipedia article as the deciding passage."""
    title = passage_source(deciding_pid, {})[0]
    return [t for pid, t in zip(pc["passage_ids"], pc["passages"]) if passage_source(pid, {})[0] == title]


CROSSCHECK_NOTE = "cross-checked"
_TIER = {Verdict.VERIFIED: (0.66, 1.0), Verdict.UNCERTAIN: (0.35, 0.65), Verdict.HALLUCINATED: (0.0, 0.34)}


def _crosscheck_score(verdict: Verdict, nli_prob: float | None, p_true: float | None) -> float:
    """A score inside the verdict's band: the mean of the passage score and the LLM's P(true), clamped."""
    vals = [v for v in (nli_prob, p_true) if v is not None]
    lo, hi = _TIER[verdict]
    return min(hi, max(lo, sum(vals) / len(vals) if vals else (lo + hi) / 2))


def find_words(text: str, words: str) -> tuple[int, int] | None:
    """(start, end) of `words` in `text`, ignoring case, preferring a whole-word match ("2" in "had 2 offices",
    not inside "2022"). Searched in the original string, so the offsets stay right even where casefolding
    would change the length (ß, İ)."""
    if not words:
        return None
    w = re.escape(words)
    m = re.search(rf"(?<!\w){w}(?!\w)", text, re.I) or re.search(w, text, re.I)
    return (m.start(), m.end()) if m else None


_SCALE = {"thousand": 1e3, "lakh": 1e5, "million": 1e6, "crore": 1e7, "billion": 1e9, "trillion": 1e12,
          "हज़ार": 1e3, "हजार": 1e3, "लाख": 1e5, "मिलियन": 1e6, "करोड़": 1e7, "अरब": 1e9, "बिलियन": 1e9, "ट्रिलियन": 1e12}
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?(?:\s?(?P<scale>" + "|".join(_SCALE) + r"))?(?:\s?(?:%|percent|per cent|प्रतिशत))?",
                     re.I)
_MONTHS = ("January|February|March|April|May|June|July|August|September|October|November|December|"
           "जनवरी|फ़रवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितंबर|सितम्बर|अक्टूबर|नवंबर|नवम्बर|दिसंबर|दिसम्बर")


def claimed_words(claim: str, kg_v, names: set[str] | frozenset = frozenset()) -> str:
    """The words of a claim that state the value a structured source contradicted, or "". Wikidata and the
    statistics keep that value in their own form, never as written: an item id (Q1353: "Delhi", found through
    `names`, the item's casefolded labels and aliases), a date ("1870-10-2": the date phrase with that year),
    or a number ("1400000000.0": the number in the claim with that value, e.g. "1.4 billion")."""
    value = str(getattr(kg_v, "expected_value", "") or "")
    if re.fullmatch(r"Q\d+", value):
        low = claim.casefold()
        hits = [n for n in names if n and n in low]
        return max(hits, key=len) if hits else ""
    if value and find_words(claim, value):  # already written as in the claim (e.g. a nationality, "Canadian")
        return value
    if d := re.fullmatch(r"(\d{1,4})-\d{1,2}(?:-\d{1,2})?", value):
        y = d[1]
        m = re.search(rf"(?:\d{{1,2}}\s+(?:{_MONTHS})|(?:{_MONTHS})\s+\d{{1,2}},?)\s+{y}(?!\d)|(?:{_MONTHS})\s+{y}(?!\d)"
                      rf"|(?<!\d){y}(?!\d)", claim, re.I)
        return m.group(0) if m else ""
    try:
        target = float(value)
    except ValueError:
        return ""
    best, gap = "", 0.01  # within 1%: the value was read from these very words
    for m in _NUMBER.finditer(claim):
        n = float(re.match(r"\d[\d,]*(?:\.\d+)?", m.group(0))[0].replace(",", ""))
        n *= _SCALE.get((m["scale"] or "").lower(), 1.0)  # lower() leaves the Hindi words unchanged
        g = abs(n - target) / max(abs(target), 1.0)
        if g <= gap:
            best, gap = m.group(0).strip(), g
    return best


def error_spans(claim: str, verdict: Verdict, note: str | None, kg_v, wrong_span: str = "",
                claimed: str = "") -> list[list[int]]:
    """Where the error is, as [start, end] offsets into the claim, for a Hallucinated claim: the claimed
    value a structured source contradicts (`claimed`, from claimed_words), else the words the LLM named as
    wrong, else the whole claim."""
    if verdict != Verdict.HALLUCINATED:
        return []
    candidates = []
    if note == KG_NOTE and kg_v is not None and getattr(kg_v, "status", None) == "contradicted":
        candidates.append(claimed or claimed_words(claim, kg_v))
    candidates.append(wrong_span or "")
    for w in candidates:
        if span := find_words(claim, w):
            return [list(span)]
    return [[0, len(claim)]]


# Notes of verdicts set by something other than the passage score alone (with KG_NOTE): the LLM judge, the
# Version 2 cross-check, a published fact-check. Shared with the API (calibration, sources).
DECIDED_PREFIXES = ("judged by LLM", CROSSCHECK_NOTE, FC_NOTE_PREFIX)


def _decided_elsewhere(note: str | None) -> bool:
    """Was this claim's verdict set by the KG, the LLM judge, the cross-check or a fact-check (not by NLI)?"""
    return bool(note) and (note == KG_NOTE or note.startswith(DECIDED_PREFIXES))


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
        number_guard: bool = False,
        verdict_mode: str = "v1",
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
        # Number guard (member3_backend/number_guard.py); see number_guard_eval.py.
        self.number_guard = number_guard
        # "v1": verdicts as before (an LLM, if set, replaces the NLI result). "crosscheck" (Version 2,
        # member3_backend/crosscheck.py): sources decide first; otherwise the passages and the LLM must agree.
        if verdict_mode not in ("v1", "crosscheck"):
            raise ValueError("verdict_mode must be 'v1' or 'crosscheck'")
        self.verdict_mode = verdict_mode
        self.crosscheck_symmetric = True  # the default rule (member3_backend/crosscheck.py)
        # Second reading (Version 2, last round): an LLM in "grounded" mode over all retrieved passages, asked only
        # for claims the cross-check leaves Uncertain although one side leans true. None = off.
        self.second_reader = None
        # v4a: a passage contradiction alone never flags; and a claim about to be flagged is first read against all
        # retrieved sources (second_reader): if they state it, it is Uncertain instead. Off unless adopted.
        self.flag_needs_llm = False
        # Claims cross-checked at the same time (speed only: each claim's verdict depends on that claim alone).
        self.llm_workers = 1
        # Optional, off by default: a second reading that finds the claim false flags it (see _crosscheck_one).
        self.second_reading_flags = False
        self.keep_article_texts = False  # evidence["article_texts"], for number_guard_eval_v2.py only
        # MedlinePlus as a second evidence source (member3_backend/medline_expander.py);
        # None unless the API switches it on (official_sources_eval.py decides).
        self.medline = None
        # World Bank / WHO statistics; False unless the API switches them on.
        self.official_stats = False

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
        enabled = active_signals or self._default_enabled_signals()

        # Knowledge-graph / statistics lookups are network-bound, independent per claim and
        # independent of the Wikipedia expansion: start them now, in parallel, and collect
        # them after retrieval (each web service is still paced, member2_data/_http.py).
        kg_pool, kg_futures, t_kg = None, None, time.perf_counter()
        if "kg" in enabled and self.entity_linker and self.wikidata:
            kg_pool = ThreadPoolExecutor(max_workers=MAX_PARALLEL_LOOKUPS)
            kg_futures = [kg_pool.submit(self._kg_lookup, c, language) for c in claim_texts]

        try:
            if self.expander is not None:
                t = time.perf_counter()
                self.expander.expand(list(zip(claim_texts, languages)))  # never raises; failures are skipped
                timings["expansion"] = (time.perf_counter() - t) * 1000
            if self.medline is not None:  # MedlinePlus health topics (member3_backend/medline_expander.py)
                t = time.perf_counter()
                self.medline.expand(list(zip(claim_texts, languages)))  # never raises
                timings["expansion"] += (time.perf_counter() - t) * 1000

            t = time.perf_counter()
            embedding_result = self.embedder.embed(
                claim_ids, claim_texts, languages, use_muril=self.retriever_muril is not None)
            timings["embedding"] = (time.perf_counter() - t) * 1000

            kg_results: list[tuple] = [(None, None)] * len(claim_ids)
            if kg_futures is not None:
                kg_results = [f.result() for f in kg_futures]
                timings["kg"] = (time.perf_counter() - t_kg) * 1000  # wall time; overlaps the expansion
        finally:
            if kg_pool is not None:
                kg_pool.shutdown(wait=True)

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

            kg_conf, kg_v = kg_results[i]

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
        crosscheck = self.verdict_mode == "crosscheck" and self.llm_verifier is not None
        if self.llm_verifier is not None and not crosscheck:
            t_llm = time.perf_counter()
            scores = [s if s.note == KG_NOTE else self._llm_judge(s, claim_texts[i], per_claim[i]["passages"])
                      for i, s in enumerate(scores)]
            timings["llm"] = (time.perf_counter() - t_llm) * 1000
        fact_checks: list[dict | None] = [None] * len(scores)
        if self.fact_checker is not None and self.nli_scorer is not None:
            t_fc = time.perf_counter()
            todo = [i for i, s in enumerate(scores) if s.note != KG_NOTE]

            def search(i):  # web searches in parallel; matching (GPU) stays sequential below
                try:
                    return self.fact_checker.search(claim_texts[i], language)
                except Exception:
                    return None
            with ThreadPoolExecutor(max_workers=MAX_PARALLEL_LOOKUPS) as pool:
                found = dict(zip(todo, pool.map(search, todo)))
            for i in todo:
                scores[i], fact_checks[i] = self._fact_check(scores[i], claim_texts[i], language, found[i])
            timings["factcheck"] = (time.perf_counter() - t_fc) * 1000

        # --- Number guard (member3_backend/number_guard.py): Verified by a passage only if
        # the passage contains the claim's numbers; else Uncertain. Off unless adopted.
        for i, s in enumerate(scores):
            dec = per_claim[i]["deciding"]
            if not (self.number_guard and s.verdict == Verdict.VERIFIED and not _decided_elsewhere(s.note)
                    and dec and dec[1] == "supports" and dec[0] in per_claim[i]["passage_ids"]):
                continue
            if missing := missing_numbers(claim_texts[i], _same_article_texts(per_claim[i], dec[0])):
                scores[i] = ClaimScore(claim_id=s.claim_id, hallu_score=0.5, verdict=Verdict.UNCERTAIN,
                                       active_signals=s.active_signals,
                                       note=f"{NUMBER_NOTE} ({', '.join(missing)})")

        # --- Cross-check (Version 2): for every claim no source decided, the LLM's own judgement and the
        # passage score must agree for Verified; a contradiction or (no support + LLM false) is Hallucinated.
        llm_checks: list[dict | None] = [None] * len(scores)
        if crosscheck:
            t_llm = time.perf_counter()
            todo = [i for i, s in enumerate(scores) if not _decided_elsewhere(s.note)]
            with ThreadPoolExecutor(max_workers=max(1, self.llm_workers)) as pool:
                done = list(pool.map(lambda i: self._crosscheck_one(scores[i], claim_texts[i], per_claim[i]), todo))
            for i, (score, check) in zip(todo, done):
                scores[i], llm_checks[i] = score, check
            timings["llm"] = (time.perf_counter() - t_llm) * 1000

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
        def claimed(pc: dict, sc: ClaimScore, ct: str) -> str:
            """The claim's words for the value a structured source contradicted (for the error span)."""
            v = pc.get("kg_v")
            if sc.verdict != Verdict.HALLUCINATED or sc.note != KG_NOTE or getattr(v, "status", None) != "contradicted":
                return ""
            value, names = str(v.expected_value or ""), set()
            if re.fullmatch(r"Q\d+", value) and self.wikidata is not None:
                try:
                    names = self.wikidata.names([value], language).get(value, set())
                except Exception:
                    names = set()
            return claimed_words(ct, v, names)

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_LOOKUPS) as pool:  # name lookups: network-bound
            kg_facts = list(pool.map(lambda ps: self._kg_fact(ps[0]["kg_v"], language) if ps[1].note == KG_NOTE else None,
                                     zip(per_claim, scores)))
            claimed_text = list(pool.map(lambda a: claimed(*a), zip(per_claim, scores, claim_texts)))
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
            evidence=[{"passage_ids": pc["passage_ids"], "passages": pc["passages"], "deciding": pc["deciding"], "fact_check": fc,
                       "excerpt": ex, "kg_fact": kf, "llm_check": lc,
                       "error_spans": error_spans(ct, sc.verdict, sc.note, pc.get("kg_v"), (lc or {}).get("wrong_span", ""),
                                                  cw),
                       "deciding_text": (pc["passages"][pc["passage_ids"].index(pc["deciding"][0])]
                                         if pc["deciding"] and pc["deciding"][0] in pc["passage_ids"] else None),
                       # only for number_guard_eval_v2.py (not read by the API): not built per request
                       "article_texts": (_same_article_texts(pc, pc["deciding"][0])
                                         if self.keep_article_texts and pc["deciding"] else [])}
                      for pc, fc, ex, kf, lc, ct, sc, cw in zip(per_claim, fact_checks, excerpts, kg_facts, llm_checks,
                                                                claim_texts, scores, claimed_text)],
        )

    def _fact_check(self, score: ClaimScore, claim_text: str, language: Language, checks: list | None = None
                    ) -> tuple[ClaimScore, dict | None]:
        """A fact-check of the same claim with a clear rating replaces the score;
        otherwise (none found, none matching, mixed rating, lookup failed) it stays.
        `checks`: the search results if already fetched (run() searches in parallel)."""
        try:
            if checks is None:
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

    def _crosscheck_one(self, s: ClaimScore, claim_text: str, pc: dict) -> tuple[ClaimScore, dict | None]:
        """Version 2 cross-check of one claim no source decided: (new score, llm_check or None)."""
        try:
            j = self.llm_verifier.verify(claim_text, pc["passages"])
        except Exception:
            j = None
        if j is None or j.verdict is None:
            return ClaimScore(claim_id=s.claim_id, hallu_score=s.hallu_score, verdict=s.verdict,
                              active_signals=s.active_signals,
                              note=s.note or "LLM cross-check unavailable (key, quota or network); "
                                             "passage result used"), None
        model = j.model or getattr(self.llm_verifier, "model", "LLM")
        nli = pc["nli_prob"]
        number_missing = (s.note or "").startswith(NUMBER_NOTE)
        used = llm_verdict_used(j.verdict, j.reason)
        tier = "no passage" if nli is None else ("passages support" if nli > 0.65 else
                                                 "passages contradict" if nli < 0.35 else "passages unclear")
        # Every reader's verdict, for the web app ("how it was decided"): passages, first and second LLM reading.
        check = {"model": model, "verdict": j.verdict, "verdict_used": used, "p_true": j.p_true, "reason": j.reason,
                 "wrong_span": j.wrong_span, "passages": tier, "passage_score": nli}
        v = Verdict(crosscheck_verdict(s.verdict.value, False, nli, used, number_missing, self.crosscheck_symmetric,
                                       self.flag_needs_llm))
        note = f"{CROSSCHECK_NOTE}: {tier}; LLM ({model}) says {j.verdict}"
        if j.reason:
            note += f": {j.reason}"

        def second(purpose: str):
            try:
                g = self.second_reader.verify(claim_text, pc["passages"])
            except Exception:
                return None
            if g.verdict is not None:
                check["second_reading"] = {"verdict": g.verdict, "reason": g.reason, "purpose": purpose,
                                           "model": g.model or getattr(self.second_reader, "model", "LLM")}
            return g

        if (v == Verdict.UNCERTAIN and self.second_reader is not None
                and second_reading_candidate(nli, used, number_missing)):
            g = second("confirm")
            if g is not None and g.verdict == "Verified":
                v = Verdict.VERIFIED
                note += f"; second reading: the {len(pc['passages'])} retrieved sources state it"
                if g.reason:
                    note += f" ({g.reason})"
            elif g is not None and g.verdict == "Hallucinated" and self.second_reading_flags:
                # Optional (SATYASCORE_SECOND_READING_FLAGS): the passages-only reading finds the claim false.
                # Exploratory on the 620-item test: caught 47% -> 49%, false alarms 13% -> 15%.
                v = Verdict.HALLUCINATED
                note += f"; second reading: the {len(pc['passages'])} retrieved sources contradict it"
                if g.reason:
                    note += f" ({g.reason})"
                if g.wrong_span:
                    check["wrong_span"] = g.wrong_span
        if v == Verdict.HALLUCINATED and self.flag_needs_llm and self.second_reader is not None \
                and "second_reading" not in check:
            g = second("guard")  # the false-alarm guard: do the retrieved sources state the claim after all?
            if g is not None and g.verdict == "Verified":
                v = Verdict.UNCERTAIN
                note += "; not flagged: a second reading finds the retrieved sources state it"
        return ClaimScore(claim_id=s.claim_id, hallu_score=_crosscheck_score(v, nli, j.p_true),
                          verdict=v, active_signals=[*s.active_signals, "llm"], note=note), check

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
        if self.official_stats:  # World Bank / WHO country statistics (member2_data/official_stats.py)
            stats = official_stats.check(claim_text, language, self.entity_linker, self.wikidata)
            if stats is not None:
                return stats.confidence, (stats if stats.status != "unknown" else None)
        extra = kg_extra.check(claim_text, language, self.entity_linker, self.wikidata)
        if extra is not None:  # authorship / current office / quantity / currency (member2_data/kg_extra.py)
            return extra.confidence, (extra if extra.status != "unknown" else None)
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
            v = self._capital_by_name(v, linked, language)
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
            v = self._capital_by_name(v, linked, "hi")
            if v.status in ("supported", "contradicted"):
                return v.confidence, v
        return None, None

    def _capital_by_name(self, v, linked, language: Language):
        """A contradicted capital claim (P36) is supported when the claimed city's name is a whole word of the
        real capital's name: "भारत की राजधानी दिल्ली है" / "Delhi is the capital of India" (capital: New Delhi,
        नई दिल्ली). Wikidata's location chain from New Delhi no longer reaches Delhi, so the walk alone fails."""
        if v.status != "contradicted" or v.property_pid != CAPITAL_PID or not v.actual_values:
            return v
        try:
            names = self.wikidata.names([linked.subject_qid, *(linked.object_candidates or (linked.object_qid,)),
                                         *v.actual_values], language)
        except Exception:
            return v
        claimed = {n for q in (linked.object_candidates or (linked.object_qid,)) for n in names.get(q, ())}
        claimed -= names.get(linked.subject_qid, set())  # "Mexico is the capital of Mexico" (Mexico City): not support
        actual = {n for q in v.actual_values for n in names.get(q, ())}
        if any(c and re.search(rf"(?<!\w){re.escape(c)}(?!\w)", a) for c in claimed for a in actual):
            return replace(v, status="supported", found=True, confidence=1.0)
        return v

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
        if v.display:  # World Bank / WHO: already named and linked
            return {**v.display, "values": list(v.actual_text), "status": v.status}
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