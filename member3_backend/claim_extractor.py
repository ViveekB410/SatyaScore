"""
Claim Extractor — decomposes LLM-generated text into atomic factual claims.

PRD ref: FR-01.
    - Accept plain text input in English or Hindi (up to 2,000 words)
    - Use dependency parsing to extract atomic factual claims
    - Resolve coreferences before extraction (pronouns -> entity names)
    - Output claims with character-level span offsets in the original text
    - Handle a minimum of 50 claims per document without degradation

============================================================================
HONESTY NOTE — scope and known limitations (read before relying on this):
============================================================================
1. COREFERENCE RESOLUTION IS ENGLISH-ONLY AND RULE-BASED, NOT NEURAL. It
   tracks the most recent PERSON entity and most recent non-PERSON entity
   seen so far in the document, and resolves pronouns to whichever fits
   (he/she/they -> nearest PERSON, it -> nearest non-PERSON). This does
   NOT do gender disambiguation, does NOT handle plural antecedents
   properly, and can pick the wrong referent when the "nearest entity by
   text position" isn't the grammatical antecedent — e.g. in "The Ganga
   originates in Gangotri and it flows through Varanasi", spaCy's small
   model mis-parses "Ganga" as a compound modifier rather than the
   subject, so "it" falls back to nearest-entity-by-proximity and
   incorrectly resolves to "Gangotri" instead of "Ganga". This is a real,
   known failure mode of rule-based coref, not silently hidden — a
   production system would use a real coreference model (e.g. fastcoref),
   which also doesn't have strong off-the-shelf Hindi support yet.

2. CLAIM DECOMPOSITION (splitting one sentence into multiple atomic
   claims) IS ENGLISH-ONLY. It handles three common patterns via spaCy's
   dependency parse: coordinated verb phrases ("X did A and did B"),
   relative clauses ("X, who is Y, did Z"), and appositives ("X, the Y,
   did Z"). It will NOT catch every way a sentence can bundle multiple
   facts — this is a rule-based system, not a learned one.

3. HINDI/MARATHI: sentence segmentation only (via IndicNLP, with a plain
   punctuation-splitter fallback if IndicNLP's resources aren't
   available), no decomposition, no coreference resolution. Each
   Hindi/Marathi sentence becomes exactly one claim.

4. CHARACTER SPANS: for claims split out of a sentence via decomposition
   (appositive/relative-clause/coordinated-clause claims), the span is
   the precise char range of that clause in the original text. For the
   "base" remaining claim after decomposition, the span covers the whole
   source sentence rather than an exact sub-string, since after removing
   the decomposed piece and substituting resolved pronouns, the claim
   text is a reconstruction, not a literal substring.
============================================================================
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import spacy
from spacy.language import Language as SpacyLanguage
from spacy.tokens import Doc, Span, Token

Language = Literal["en", "hi", "mr"]

MAX_WORDS = 2000
MIN_CLAIMS_SUPPORTED = 50  # FR-01: must handle at least this many without degrading

PRONOUN_PERSON = {"he", "him", "his", "himself", "she", "her", "hers", "herself"}
PRONOUN_NONPERSON = {"it", "its", "itself"}
PRONOUN_PLURAL = {"they", "them", "their", "theirs", "themselves"}
ALL_PRONOUNS = PRONOUN_PERSON | PRONOUN_NONPERSON | PRONOUN_PLURAL

_WS_BEFORE_PUNCT = re.compile(r"\s+([.,!?])")
_MULTI_SPACE = re.compile(r"\s{2,}")
# spaCy tokenizes contractions/possessives ('s, n't, 're, 've, 'll, 'd, 'm)
# as separate tokens, so naively space-joining tokens back together produces
# "the body 's cells" instead of "the body's cells". Cosmetic only (never
# changes claim meaning), but worth collapsing for annotator readability.
_WS_BEFORE_CONTRACTION = re.compile(r"\s+('(?:s|t|re|ve|ll|d|m)\b)", re.IGNORECASE)

# Matches markdown list/heading markers this extractor was never designed to
# see: numbered list markers ("1. ", "12. "), bullet markers ("- ", "* ",
# "• ") at the start of a line, and bold/italic asterisks anywhere.
_NUMBERED_MARKER = re.compile(r"(?m)^\s*\d{1,2}\.\s")
_BULLET_MARKER = re.compile(r"(?m)^\s*[-*•]\s")


def _blank_markdown_artifacts(text: str) -> str:
    """Neutralizes markdown list/heading syntax from raw LLM output BEFORE
    it reaches spaCy's sentence segmenter and dependency parser, which are
    trained on prose and mis-parse markdown structure (numbers/asterisks
    get treated as ordinary tokens, confusing both sentence-boundary
    detection and subject/root identification -- this was the direct
    cause of garbled claims like "6 Government Banker Managing the..."
    from a source line "6. **Government's Banker**: Managing the...").

    Deliberately LENGTH-PRESERVING (markers are replaced with spaces of
    the same width, never deleted) so every character offset computed
    downstream still points into the ORIGINAL input text unchanged --
    this keeps the span-offset guarantee described in the module
    docstring (item 4) intact with no separate offset-remapping needed.
    """
    text = _NUMBERED_MARKER.sub(lambda m: " " * len(m.group(0)), text)
    text = _BULLET_MARKER.sub(lambda m: " " * len(m.group(0)), text)
    text = text.replace("**", "  ").replace("*", " ")
    return text

_nlp_cache: dict[str, SpacyLanguage] = {}


def _get_english_pipeline() -> SpacyLanguage:
    if "en" not in _nlp_cache:
        _nlp_cache["en"] = spacy.load("en_core_web_sm")
    return _nlp_cache["en"]


@dataclass
class ExtractedClaim:
    claim_id: str
    text: str
    start_char: int  # offset into the ORIGINAL input text
    end_char: int
    extraction_method: Literal[
        "decomposed_base", "decomposed_relcl", "decomposed_appos", "decomposed_conj", "sentence_level"
    ] = "sentence_level"
    had_unresolved_pronoun: bool = False


class ClaimExtractor:
    def __init__(self):
        pass  # spaCy pipeline is lazily loaded + cached in _get_english_pipeline

    def extract_entities(self, text: str, language: Language = "en") -> list[str]:
        """Returns named entity surface strings found in `text` (via spaCy's
        NER for English; empty for Hindi/Marathi since no NER model is
        wired in for those yet), for downstream entity linking
        (member2_data/entity_linker.py)."""
        if language == "en":
            doc = _get_english_pipeline()(text)
            return [ent.text for ent in doc.ents]
        # No Hindi/Marathi NER model wired in — return empty rather than
        # guessing, so downstream KG linking correctly skips (kg_conf=None)
        # instead of acting on made-up entity spans.
        return []

    def extract(self, text: str, language: Language = "en") -> list[ExtractedClaim]:
        word_count = len(text.split())
        if word_count > MAX_WORDS:
            raise ValueError(f"Input has {word_count} words, exceeds FR-01's {MAX_WORDS}-word limit")

        text = _blank_markdown_artifacts(text)

        if language == "en":
            return self._extract_english(text)
        return self._extract_indic_sentence_level(text, language)

    # -- English: dependency-based decomposition + coreference --------------

    def _extract_english(self, text: str) -> list[ExtractedClaim]:
        doc = _get_english_pipeline()(text)
        referents = self._build_pronoun_referents(doc)

        claims: list[ExtractedClaim] = []
        counter = 0
        for sent in doc.sents:
            for method, token_ids, precise_span in self._decompose_sentence(sent):
                claim_text, had_unresolved = self._render_tokens(doc, token_ids, referents)
                if not claim_text or len(claim_text.split()) < 2:
                    continue  # skip fragments too short to be a meaningful claim
                span = precise_span or (sent.start_char, sent.end_char)
                claims.append(
                    ExtractedClaim(
                        claim_id=f"claim_{counter}",
                        text=claim_text,
                        start_char=span[0],
                        end_char=span[1],
                        extraction_method=method,
                        had_unresolved_pronoun=had_unresolved,
                    )
                )
                counter += 1
        return claims

    def _build_pronoun_referents(self, doc: Doc) -> dict[int, str | None]:
        """Maps token.i -> resolved referent text for every pronoun token,
        based on the nearest preceding entity of a compatible type. See
        module docstring item 1 for known limitations."""
        entities_in_order = sorted(doc.ents, key=lambda e: e.start_char)
        referents: dict[int, str | None] = {}

        for token in doc:
            lowered = token.text.lower()
            if lowered not in ALL_PRONOUNS:
                continue
            preceding = [e for e in entities_in_order if e.start_char < token.idx]
            if not preceding:
                referents[token.i] = None
                continue
            if lowered in PRONOUN_PERSON:
                match = next((e for e in reversed(preceding) if e.label_ == "PERSON"), None)
            elif lowered in PRONOUN_NONPERSON:
                match = next((e for e in reversed(preceding) if e.label_ != "PERSON"), None)
            else:
                match = preceding[-1]
            referents[token.i] = match.text if match else None

        return referents

    def _decompose_sentence(
        self, sent: Span
    ) -> list[tuple[str, list[int], tuple[int, int] | None]]:
        """Returns list of (extraction_method, token_ids_in_order, precise_span_or_None)."""
        root = sent.root
        subj = next((t for t in root.children if t.dep_ in ("nsubj", "nsubjpass")), None)

        excluded_ids: set[int] = set()
        results: list[tuple[str, list[int], tuple[int, int] | None]] = []

        if subj is not None:
            for child in subj.children:
                if child.dep_ == "relcl":
                    subtree = sorted(child.subtree, key=lambda t: t.i)
                    non_pronoun = [t for t in subtree if not (t.dep_ == "nsubj" and t.pos_ == "PRON")]
                    token_ids = [subj.i] + [t.i for t in non_pronoun]
                    span = (subtree[0].idx, subtree[-1].idx + len(subtree[-1].text))
                    results.append(("decomposed_relcl", token_ids, span))
                    excluded_ids |= {t.i for t in subtree}
                    excluded_ids |= self._adjacent_comma_ids(sent, subtree)

            for child in subj.children:
                if child.dep_ == "appos":
                    subtree = sorted(child.subtree, key=lambda t: t.i)
                    span = (subtree[0].idx, subtree[-1].idx + len(subtree[-1].text))
                    results.append(("decomposed_appos", [subj.i, -1] + [t.i for t in subtree], span))
                    excluded_ids |= {t.i for t in subtree}
                    excluded_ids |= self._adjacent_comma_ids(sent, subtree)

        has_conj = False
        for child in root.children:
            if child.dep_ == "conj" and child.pos_ in ("VERB", "AUX"):
                has_conj = True
                subtree = sorted(child.subtree, key=lambda t: t.i)
                has_own_subject = any(t.dep_ in ("nsubj", "nsubjpass") for t in subtree)
                has_own_aux = any(t.dep_ in ("aux", "auxpass") for t in subtree)
                token_ids = [t.i for t in subtree]

                # English elides a shared auxiliary across coordinated verbs
                # ("Water is absorbed ... and transported ...") -- the
                # second conjunct's own subtree has no "is" token because
                # none exists at that position in the source text. Without
                # this, the extracted claim reads as an ungrammatical
                # fragment ("Water transported to the leaves."). Borrow the
                # root's auxiliary so the standalone claim stays complete.
                if not has_own_aux:
                    root_aux = next((t for t in root.children if t.dep_ in ("aux", "auxpass")), None)
                    if root_aux is not None:
                        token_ids = [root_aux.i] + token_ids

                if not has_own_subject and subj is not None:
                    token_ids = [subj.i] + token_ids
                span = (subtree[0].idx, subtree[-1].idx + len(subtree[-1].text))
                results.append(("decomposed_conj", token_ids, span))
                excluded_ids |= {t.i for t in subtree}
        if has_conj:
            excluded_ids |= {t.i for t in sent if t.dep_ == "cc" and t.head.i == root.i}

        base_ids = [t.i for t in sent if t.i not in excluded_ids and not t.is_punct]
        if base_ids:
            results.append(("decomposed_base", base_ids, None))

        return results

    @staticmethod
    def _adjacent_comma_ids(sent: Span, subtree: list[Token]) -> set[int]:
        ids = set()
        start_i, end_i = subtree[0].i, subtree[-1].i
        for t in sent:
            if t.is_punct and t.text == "," and (t.i == start_i - 1 or t.i == end_i + 1):
                ids.add(t.i)
        return ids

    def _render_tokens(
        self, doc: Doc, token_ids: list[int], referents: dict[int, str | None]
    ) -> tuple[str, bool]:
        had_unresolved = False
        words = []
        for tid in token_ids:
            if tid == -1:
                words.append("is")
                continue
            token = doc[tid]
            lowered = token.text.lower()
            if lowered in ALL_PRONOUNS:
                referent = referents.get(tid)
                if referent:
                    words.append(referent)
                else:
                    had_unresolved = True
                    words.append(token.text)
            else:
                words.append(token.text)

        text = " ".join(words)
        text = _WS_BEFORE_CONTRACTION.sub(r"\1", text)
        text = _WS_BEFORE_PUNCT.sub(r"\1", text)
        text = _MULTI_SPACE.sub(" ", text).strip()
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        if text and text[-1] not in ".!?":
            text += "."
        return text, had_unresolved

    # -- Hindi / Marathi: sentence-level fallback ----------------------------

    def _extract_indic_sentence_level(self, text: str, language: Language) -> list[ExtractedClaim]:
        try:
            from indicnlp.tokenize import sentence_tokenize
            sentences = sentence_tokenize.sentence_split(text, lang=language)
        except Exception:
            sentences = [s.strip() for s in re.split(r"(?<=[।.!?])\s+", text) if s.strip()]

        claims = []
        cursor = 0
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
            start = text.find(sentence, cursor)
            if start == -1:
                start = cursor
            end = start + len(sentence)
            cursor = end
            claims.append(
                ExtractedClaim(
                    claim_id=f"claim_{i}",
                    text=sentence,
                    start_char=start,
                    end_char=end,
                    extraction_method="sentence_level",
                )
            )
        return claims
