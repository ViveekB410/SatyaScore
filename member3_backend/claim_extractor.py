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

   SAFETY NET (IMPROVEMENT_PLAN.md task 1.1): when any piece of a sentence
   comes out as an unjudgeable fragment (no finite verb in the source, a
   lost "%", or a "Label:" glued to its content), the whole sentence becomes
   ONE sentence_level claim instead, preferring the content after a "Label:".
   Sentences with no subject at all (headings, bare list items like
   "Registering political parties.") yield no claim. Measured on all 50
   English source answers: broken claims 14.3% -> 0% (results/
   extraction_quality.md). Known loss: spaCy's small model sometimes tags a
   verb as a noun ("the points system awards..."), and such a sentence is
   skipped; a larger spaCy model would fix it.

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
_NON_REFERENT_LABELS = {"CARDINAL", "ORDINAL", "QUANTITY", "PERCENT", "MONEY", "DATE", "TIME"}
# How pronouns are resolved: "nearest" (the nearest preceding compatible entity, the
# original rule) or "salience" (the sentence subject / topic first; see
# ClaimExtractor._referents_by_salience). "salience" met coref_eval.py's fixed rule on 400
# held-out Wikipedia introductions: right referents 93 -> 277, wrong 206 -> 128
# (results/coref_eval.md).
COREF_RULE = "salience"
_FINITE_TAGS = {"VBD", "VBZ", "VBP", "MD"}  # past, 3sg-present, non-3sg-present, modal
# Objects / complements. Deliberately excludes "pobj": "The rules for a
# run-out are:" has one but still says nothing on its own.
_COMPLEMENT_DEPS = {"dobj", "attr", "acomp", "oprd", "ccomp", "xcomp", "dative"}

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


# Bracketed asides: life dates, abbreviations, pronunciations, translations.
# Parsed as part of the sentence they produced nonsense claims from TRUE text:
# "Bhimrao Ramji Ambedkar (14 April 1891 – 6 December 1956) was ..." gave
# "Bhimrao Ramji Ambedkar is 14." and "Peripheral artery disease (PAD) is ..." gave
# "Peripheral artery disease is PAD." (results/diagnosis_true_claims.md).
_BRACKETED = re.compile(r"\([^()\n]{0,200}\)|\[[^\[\]\n]{0,200}\]")


def _blank_bracketed(text: str) -> str:
    """Blank bracketed asides with spaces of the same width (LENGTH-PRESERVING,
    like _blank_markdown_artifacts, so claim offsets still point into the
    original text). The aside's content is not checked as a claim."""
    return _BRACKETED.sub(lambda m: " " * len(m.group(0)), text)

_nlp_cache: dict[str, SpacyLanguage] = {}


def _get_english_pipeline() -> SpacyLanguage:
    if "en" not in _nlp_cache:
        nlp = spacy.load("en_core_web_sm")
        nlp.add_pipe("paragraph_breaks", before="parser")
        nlp.add_pipe("no_mid_sentence_breaks", before="parser")
        _nlp_cache["en"] = nlp
    return _nlp_cache["en"]


def _possessive(referent: str, pronoun: Token) -> str:
    """A possessive pronoun ("his", "her", "its", "their") is replaced by the
    referent's possessive form: "the tomb of his wife" -> "... of Shah Jahan's wife",
    not "... of Shah Jahan wife"."""
    # a referent with a leading "The" inside the claim reads "the": "commissioned the Taj
    # Mahal", but "The Taj Mahal was completed" (subject: the claim starts there)
    starts_claim = pronoun.dep_ in _SUBJECT_DEPS or (pronoun.dep_ == "poss" and pronoun.head.dep_ in _SUBJECT_DEPS)
    if referent.startswith("The ") and not starts_claim:
        referent = "the " + referent[4:]
    if pronoun.tag_ != "PRP$":
        return referent
    return referent + ("'" if referent.endswith("s") else "'s")


@SpacyLanguage.component("paragraph_breaks")
def _paragraph_breaks(doc: Doc) -> Doc:
    """A blank line always ends a sentence. Without this a heading with no full stop
    ("🩸 Dengue warning signs 🚨") was glued onto the next sentence as one claim.
    Single line breaks are left to the parser: PDF text breaks lines mid-sentence."""
    for tok in doc[:-1]:
        if tok.is_space and tok.text.count("\n") >= 2:
            doc[tok.i + 1].is_sent_start = True
    return doc


_SENT_END = (".", "!", "?", ":", ";", "…", "।")
_CLOSERS = ('"', "'", ")", "]", "”", "’")


@SpacyLanguage.component("no_mid_sentence_breaks")
def _no_mid_sentence_breaks(doc: Doc) -> Doc:
    """A sentence can only start after sentence-ending punctuation (or a closing quote
    or bracket right after it) or at a line break. The parser sometimes split mid-
    sentence after a capitalised word: "The Taj Mahal has been a UNESCO | World Heritage
    Site since 1983." gave the claim "The Taj Mahal has been a UNESCO." Line breaks are
    still left to the parser (headings, list items, PDF text)."""
    for tok in doc[1:]:
        prev = doc[tok.i - 1]
        if tok.is_space or prev.is_space or "\n" in prev.whitespace_ or tok.is_sent_start:
            continue
        if prev.text.endswith(_SENT_END):
            continue
        if prev.text in _CLOSERS and tok.i >= 2 and doc[tok.i - 2].text.endswith(_SENT_END):
            continue
        tok.is_sent_start = False
    return doc


# --- Claim quality: the ONE definition of a "broken" claim --------------------
# Used by the extractor (to fall back to the whole sentence instead of emitting
# a broken fragment) and by flag_quality.py (to audit gold_final.csv), so both
# always agree on what "broken" means. Conservative: flags only claims that are
# genuinely unjudgeable, not merely awkward.
_STRIPPED_SYMBOL = re.compile(r"(\w+\.?\s+)?\d+\s+of\s+the\b")  # e.g. "65 of the warming" (% lost)
# "<Article> 370 of the ..." is a reference number, not a percentage whose %
# was stripped; without this exemption real claims about Article 370 were
# flagged broken.
_REFERENCE_WORDS = {"article", "articles", "section", "sections", "clause", "chapter",
                    "schedule", "rule", "part", "amendment", "act", "no", "no.", "number"}
# Subjects that make a clause judgeable. "expl" is existential "there"
# ("There are 11 players on a cricket team." has no nsubj but is a claim).
_SUBJECT_DEPS = ("nsubj", "nsubjpass", "expl", "csubj", "csubjpass")


def _has_stripped_symbol(text: str) -> bool:
    for m in _STRIPPED_SYMBOL.finditer(text):
        prev = (m.group(1) or "").strip().lower()
        if prev not in _REFERENCE_WORDS:
            return True
    return False


def _has_finite_clause_en(text: str) -> bool:
    doc = _get_english_pipeline()(text)
    return any(t.dep_ in _SUBJECT_DEPS and t.head.pos_ in ("VERB", "AUX") for t in doc)


def claim_quality(text: str, language: Language) -> tuple[str, str]:
    """Return ("ok", "") or ("broken", reason) for one claim text."""
    t = str(text).strip()
    words = t.split()
    if language != "en":
        return ("broken", "too_short") if len(words) < 3 else ("ok", "")
    if len(words) < 4:
        return "broken", "too_short"
    if _has_stripped_symbol(t):
        return "broken", "stripped_symbol"
    if not _has_finite_clause_en(t):
        return "broken", "no_finite_clause"
    return "ok", ""


def is_well_formed_claim(text: str, language: Language) -> bool:
    return claim_quality(text, language)[0] == "ok"


# -- Is a sentence a factual claim at all? -------------------------------------
# Chatbot answers mix facts with pleasantries ("I hope this helps!"), advice ("You
# should visit it in winter"), opinions ("I think it is the most beautiful ...") and
# questions. None of these can be verified, so each came out Uncertain and pulled the
# whole-text verdict toward Uncertain. They are skipped (not highlighted, not scored).
_PLEASANTRY = re.compile(
    r"^\W*(?:i hope|hope this|let me\b|let us\b|let's|feel free|great question|good question|happy to help|"
    r"glad to help|is there anything|if you have any|thanks|thank you|sure\b|certainly\b|of course\b)", re.I)
# (not "In summary," / "In conclusion,": what follows them is usually a fact)
_SPEAKER_OR_READER = {"i", "we", "you", "me", "us"}
_HI_SPEAKER_OR_READER = re.compile(r"^\W*(?:मैं|मुझे|मेरा|मेरी|हम|हमें|हमारा|आप|आपको|आपका|आपकी|कृपया)\s")


def _not_a_claim_en(sent: Span) -> bool:
    text = sent.text.strip()
    if not text or text.endswith("?") or _PLEASANTRY.match(text):
        return True
    root = sent.root
    subjects = [c for c in root.children if c.dep_ in _SUBJECT_DEPS]
    if any(s.text.lower() in _SPEAKER_OR_READER for s in subjects):
        return True  # about the speaker or the reader: "I think ...", "You should ..."
    if root.lemma_.lower() == "let" and any(c.text.lower() in ("me", "us") for c in root.children):
        return True  # "Let me explain ...", "Let us look at ..."
    # a command ("Visit it in winter."), unless any clause in it has a subject: "Note that
    # X is Y", or a list heading run into a fact ("Provide instructions ... DNA contains ...")
    if (not subjects and root.tag_ == "VB" and root.i == sent.start
            and not any(t.dep_ in _SUBJECT_DEPS for t in sent)):
        return True
    return False


def not_a_claim(text: str, language: Language) -> bool:
    """True for questions, pleasantries, advice, opinions and other sentences about
    the speaker or reader: nothing there to verify."""
    t = text.strip()
    if language == "en":
        doc = _get_english_pipeline()(t)
        sents = list(doc.sents)
        return bool(sents) and _not_a_claim_en(sents[0])
    return not t or t.endswith("?") or bool(_HI_SPEAKER_OR_READER.match(t))


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

        text = _blank_bracketed(_blank_markdown_artifacts(text))

        if language == "en":
            return self._extract_english(text)
        return self._extract_indic_sentence_level(text, language)

    # -- English: dependency-based decomposition + coreference --------------

    # A lead-in line ending in ":" followed by short list lines. Each verb-less item
    # ("Severe abdominal pain") says nothing on its own and used to be dropped, while
    # the lead-in alone became a meaningless claim ("Seek urgent medical care if
    # there is."). Joined, each item is a checkable claim of its own.
    _LIST_ITEM_MAX = 160
    _ITEM_MARKER = re.compile(r"^[\s\-*•·–—]*(?:\d+[.)]\s*)?")

    def _extract_list_items(self, text: str) -> tuple[list[ExtractedClaim], str]:
        """Claims "<lead-in> <item>." for verb-less list items, each spanning its own
        item line; returns them with the text to parse normally, in which the used
        lead-in and items are blanked (LENGTH-PRESERVING, offsets stay valid)."""
        lines, pos = [], 0
        for raw in text.splitlines(keepends=True):
            lines.append((pos, raw.rstrip("\r\n")))
            pos += len(raw)
        made: list[ExtractedClaim] = []
        blank: list[tuple[int, int]] = []
        i = 0
        while i < len(lines):
            start, raw = lines[i]
            lead = raw.strip()
            if not (lead.endswith(":") and len(lead) > 3):
                i += 1
                continue
            j = i + 1
            while j < len(lines) and not lines[j][1].strip():
                j += 1  # blank lines between the lead-in and its first item
            items = []
            while j < len(lines):
                r = lines[j][1].strip()
                if not r or r.endswith(":") or len(r) > self._LIST_ITEM_MAX:
                    break
                items.append(lines[j])
                j += 1
            intro = lead[:-1].strip()
            used = []
            for item_start, item_raw in items if len(items) >= 2 else []:
                marker = self._ITEM_MARKER.match(item_raw).end()
                item = item_raw[marker:].strip().rstrip(".;,")
                if not item or is_well_formed_claim(item + ".", "en"):
                    continue  # empty, or a full sentence: normal extraction handles it
                first = item.split()[0]
                if first[:1].isupper() and first[1:].islower():
                    item = item[0].lower() + item[1:]  # "Severe pain" -> "... severe pain"; keeps "WHO"
                claim = f"{intro} {item}."
                if not is_well_formed_claim(claim, "en") or not_a_claim(claim, "en"):
                    continue
                s = item_start + marker + (len(item_raw[marker:]) - len(item_raw[marker:].lstrip()))
                e = item_start + len(item_raw.rstrip())
                used.append((claim, s, e))
                blank.append((item_start, item_start + len(item_raw)))
            if used:
                blank.append((start, start + len(raw)))  # the lead-in lives on in each item's claim
                made += [ExtractedClaim(claim_id="", text=c, start_char=s, end_char=e,
                                        extraction_method="list_item") for c, s, e in used]
            i = max(j, i + 1)
        chars = list(text)
        for s, e in blank:
            chars[s:e] = [" "] * (e - s)
        return made, "".join(chars)

    def _extract_english(self, text: str) -> list[ExtractedClaim]:
        list_claims, text = self._extract_list_items(text)
        claims = self._extract_english_sentences(text)
        for c in claims:
            # a whole-sentence span may run over blanked (list) text; trim to its own words
            # so it cannot overlap the list items' spans (the page skips overlapping marks)
            while c.start_char < c.end_char and text[c.start_char].isspace():
                c.start_char += 1
            while c.end_char > c.start_char and text[c.end_char - 1].isspace():
                c.end_char -= 1
        claims = sorted(claims + list_claims, key=lambda c: c.start_char)
        for k, c in enumerate(claims):
            c.claim_id = f"claim_{k}"
        return claims

    def _extract_english_sentences(self, text: str) -> list[ExtractedClaim]:
        doc = _get_english_pipeline()(text)
        referents = self._build_pronoun_referents(doc)

        claims: list[ExtractedClaim] = []
        for sent in doc.sents:
            if _not_a_claim_en(sent):
                continue  # question, pleasantry, advice, opinion: nothing to verify
            pieces = []
            for method, token_ids, precise_span in self._decompose_sentence(sent):
                claim_text, had_unresolved = self._render_tokens(doc, token_ids, referents)
                if not claim_text or len(claim_text.split()) < 2:
                    continue  # skip fragments too short to be a meaningful claim
                span = precise_span or (sent.start_char, sent.end_char)
                pieces.append((claim_text, span, method, had_unresolved, token_ids))

            # Rule-based decomposition sometimes yields an ungrammatical,
            # unjudgeable fragment (17% of English gold claims were). When ANY
            # piece of a sentence is broken, keep the whole sentence as ONE claim
            # instead -- same as the Hindi path. Pronouns are still resolved.
            if not pieces or any(self._piece_is_broken(sent, p) for p in pieces):
                fallback = self._sentence_fallback(sent, referents)
                if fallback is None:
                    continue  # a heading / list label / subjectless fragment
                pieces = [fallback]

            for claim_text, span, method, had_unresolved, _ in pieces:
                claims.append(
                    ExtractedClaim(
                        claim_id=f"claim_{len(claims)}",
                        text=claim_text,
                        start_char=span[0],
                        end_char=span[1],
                        extraction_method=method,
                        had_unresolved_pronoun=had_unresolved,
                    )
                )
        return claims

    def _sentence_fallback(self, sent: Span, referents: dict[int, str | None]):
        """One whole-sentence claim for a sentence whose decomposition broke,
        or None if the sentence is not a judgeable claim.

        Keeps the sentence's own punctuation and spacing (dropping the commas
        makes spaCy mis-parse e.g. "In Formula 1, the points system awards...").
        For "Label: content" lines, prefers the content after the colon when it
        is a claim on its own ("Blood sugar regulation: Insulin lowers...").
        """
        tokens = [t for t in sent if not t.is_space]
        colon = next((i for i, t in enumerate(tokens) if t.text == ":"), None)
        # (tokens, needs_complement). Order: the content after a "Label:",
        # then the clause before a colon, then the whole sentence (only when
        # there is no colon -- otherwise the label would be glued on).
        candidates: list[tuple[list[Token], bool]] = []
        if colon is None:
            candidates.append((tokens, False))
        else:
            candidates.append((tokens[colon + 1:], False))
            # "Mass and weight ... have distinct meanings:" is a claim that
            # introduces a list; "Its significance includes:" is only an intro.
            candidates.append((tokens[:colon], True))
            # "Common symptoms of dengue fever include: High fever, Severe
            # headache, ..." -- the list IS the object of the intro verb, so
            # the whole line is one checkable claim. Needs real list content.
            content = [t for t in tokens[colon + 1:] if not t.is_punct]
            if len(content) >= 3:
                candidates.append((tokens, False))
        for toks, needs_complement in candidates:
            while toks and toks[-1].is_punct:
                toks = toks[:-1]  # trailing full stop / colon; "." is re-added on render
            if not toks:
                continue
            text, had_unresolved = self._render_surface(toks, referents)
            if not is_well_formed_claim(text, "en"):
                continue
            if needs_complement and not self._has_complement(toks):
                continue  # a bare list intro, not a claim
            span = (toks[0].idx, toks[-1].idx + len(toks[-1].text))
            return text, span, "sentence_level", had_unresolved, [t.i for t in toks]
        return None

    @staticmethod
    def _has_complement(tokens: list[Token]) -> bool:
        """Does the clause say something (an object / complement), rather than
        just announce a list ("The rules are:", "Its significance includes:")?"""
        return any(t.dep_ in _COMPLEMENT_DEPS for t in tokens)

    @staticmethod
    def _piece_is_broken(sent: Span, piece) -> bool:
        """Is one decomposed piece an unjudgeable fragment?

        Judged on the ORIGINAL sentence's parse (the piece's source tokens),
        not by re-parsing the short rendered text: re-parsing "The Ganga
        originates in Gangotri." alone mis-tags "Ganga", and the audit's 4-word
        minimum rejects valid short claims like "Modi visited Delhi.".
        """
        claim_text, _, method, _, token_ids = piece
        doc = sent.doc
        toks = [doc[i] for i in token_ids if i >= 0]  # -1 = the "is" inserted for appositives
        if _has_stripped_symbol(claim_text):
            return True
        # Needs a finite verb from the source text -- except appositive pieces,
        # whose "X is Y" verb is inserted by design (they need a real noun).
        if method == "decomposed_appos":
            if not any(t.pos_ in ("NOUN", "PROPN", "NUM") for t in toks):
                return True
        elif not any(t.tag_ in _FINITE_TAGS for t in toks):
            return True
        # "Label: content" glued into one claim.
        colon = next((t.i for t in sent if t.text == ":"), None)
        if colon is not None and any(t.i < colon for t in toks) and any(t.i > colon for t in toks):
            return True
        # A sentence ending in ":" introduces a list. A piece of it that has no
        # object/complement ("Its significance includes", "The rules for a
        # run-out are") says nothing on its own.
        last = next((t for t in reversed(sent) if not t.is_space), None)
        if last is not None and last.text == ":" and not any(t.dep_ in _COMPLEMENT_DEPS for t in toks):
            return True
        return False

    @staticmethod
    def _render_surface(tokens: list[Token], referents: dict[int, str | None]) -> tuple[str, bool]:
        """Render tokens with their original spacing and punctuation, swapping
        resolved pronouns for their referent."""
        had_unresolved = False
        parts = []
        for t in tokens:
            if t.text.lower() in ALL_PRONOUNS:
                ref = referents.get(t.i)
                if ref:
                    parts.append(_possessive(ref, t) + t.whitespace_)
                    continue
                had_unresolved = True
            parts.append(t.text_with_ws)
        text = _MULTI_SPACE.sub(" ", "".join(parts)).strip()
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        if text and text[-1] not in ".!?":
            text += "."
        return text, had_unresolved

    def _build_pronoun_referents(self, doc: Doc) -> dict[int, str | None]:
        if COREF_RULE == "salience":
            return self._referents_by_salience(doc)
        return self._referents_nearest(doc)

    def _referents_by_salience(self, doc: Doc) -> dict[int, str | None]:
        """Pronouns follow the TOPIC, not the last name mentioned. A pronoun refers to
        (1) the subject of its own sentence if that subject is a compatible entity
        before it ("Shah Jahan built it for his wife"), else (2) the most recent
        compatible entity that was a sentence SUBJECT (directly, or as a resolved
        pronoun subject), else (3) the nearest compatible entity (the old rule).
        Before: "The Taj Mahal is located in Agra, Uttar Pradesh. It was completed in
        1653." -> "Uttar Pradesh was completed in 1653" (a false claim from true text)."""
        nearest = self._referents_nearest(doc)
        ents = [e for e in doc.ents if e.label_ not in _NON_REFERENT_LABELS]

        def entity_of(tok: Token):
            return next((e for e in ents if e.start <= tok.i < e.end), None)

        chunks = list(doc.noun_chunks)

        def subject_referent(tok: Token) -> tuple[str, str] | None:
            """(kind, text) a subject offers as a referent: a named entity, or for
            things a plain noun phrase the NER does not tag ("Diarrhea", "The triangle",
            "Spironolactone") -- else "it" fell back to a name in an aside ("English",
            "trigon", the brand name "Aldactone")."""
            if (e := entity_of(tok)) is not None:
                k = kind(e.label_)
                return (k, e.text) if k else None
            if tok.pos_ in ("NOUN", "PROPN") and tok.tag_ in ("NN", "NNP"):  # singular: "it", not "Signs"
                chunk = next((c for c in chunks if c.start <= tok.i < c.end), None)
                # "Its dome", "This building": a part of / pointer back to the topic, not a new one
                if chunk is not None and any(t.tag_ == "PRP$" or t.lower_ in ("this", "that", "these", "those")
                                             for t in chunk):
                    return None
                return ("thing", chunk.text if chunk is not None else tok.text)
            return None

        def kind(label_or_pronoun: str) -> str | None:
            low = label_or_pronoun.lower()
            if low in PRONOUN_PERSON or label_or_pronoun == "PERSON":
                return "person"
            if low in PRONOUN_NONPERSON or (label_or_pronoun.isupper() and label_or_pronoun not in ("PERSON", "NORP")):
                return "thing"
            return None

        salient: dict[str, str] = {}
        referents: dict[int, str | None] = {}
        for sent in doc.sents:
            subjects = [t for t in sent if t.dep_ in ("nsubj", "nsubjpass") and t.head == sent.root]
            for token in sent:
                low = token.text.lower()
                if low not in ALL_PRONOUNS:
                    continue
                k = kind(low)
                if k is None:  # plural pronouns: unchanged
                    referents[token.i] = nearest.get(token.i)
                    continue
                own = None
                for s in subjects:
                    sr = subject_referent(s)
                    if s.i < token.i and sr is not None and sr[0] == k:
                        own = sr[1]
                referents[token.i] = own or salient.get(k) or nearest.get(token.i)
            for s in subjects:  # the sentence subject becomes the topic for what follows
                if s.text.lower() in ALL_PRONOUNS:
                    k = kind(s.text)
                    if k and referents.get(s.i):
                        salient[k] = referents[s.i]
                elif (sr := subject_referent(s)) is not None:
                    salient[sr[0]] = sr[1]
        return referents

    def _referents_nearest(self, doc: Doc) -> dict[int, str | None]:
        """Maps token.i -> resolved referent text for every pronoun token,
        based on the nearest preceding entity of a compatible type. See
        module docstring item 1 for known limitations."""
        # A pronoun never refers to a number, date or amount; without this
        # filter "their finishing position" became "1 finishing position" and
        # "It serves as..." became "first serves as...".
        entities_in_order = sorted(
            (e for e in doc.ents if e.label_ not in _NON_REFERENT_LABELS),
            key=lambda e: e.start_char,
        )
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

        # The subject's FULL noun phrase, minus any relative clause / appositive
        # hanging off it. Using only the head token (subj.i) produced truncated
        # claims like "Programme is UIP." for "The Universal Immunization
        # Programme (UIP) ...".
        subj_ids: list[int] = []
        if subj is not None:
            carved = {t.i for c in subj.children if c.dep_ in ("relcl", "appos") for t in c.subtree}
            subj_ids = sorted(t.i for t in subj.subtree if t.i not in carved and t.pos_ != "PUNCT")

        if subj is not None:
            for child in subj.children:
                if child.dep_ == "relcl":
                    subtree = sorted(child.subtree, key=lambda t: t.i)
                    non_pronoun = [t for t in subtree if not (t.dep_ == "nsubj" and t.pos_ == "PRON")]
                    token_ids = subj_ids + [t.i for t in non_pronoun]
                    span = (subtree[0].idx, subtree[-1].idx + len(subtree[-1].text))
                    results.append(("decomposed_relcl", token_ids, span))
                    excluded_ids |= {t.i for t in subtree}
                    excluded_ids |= self._adjacent_comma_ids(sent, subtree)

            for child in subj.children:
                if child.dep_ == "appos":
                    subtree = sorted(child.subtree, key=lambda t: t.i)
                    span = (subtree[0].idx, subtree[-1].idx + len(subtree[-1].text))
                    appos_ids = [t.i for t in subtree if t.pos_ != "PUNCT"]  # drop the "(" ")"
                    results.append(("decomposed_appos", subj_ids + [-1] + appos_ids, span))
                    excluded_ids |= {t.i for t in subtree}
                    excluded_ids |= self._adjacent_comma_ids(sent, subtree)

        has_conj = False
        for child in root.children:
            if child.dep_ == "conj" and child.pos_ in ("VERB", "AUX"):
                has_conj = True
                subtree = sorted(child.subtree, key=lambda t: t.i)
                has_own_subject = any(t.dep_ in ("nsubj", "nsubjpass") for t in subtree)
                has_own_aux = any(t.dep_ in ("aux", "auxpass") for t in subtree)
                token_ids = [t.i for t in subtree if t.text != ":"]  # a list-intro colon is not content

                # English elides a shared auxiliary across coordinated verbs
                # ("Water is absorbed ... and transported ...") -- the
                # second conjunct's own subtree has no "is" token because
                # none exists at that position in the source text. Without
                # this, the extracted claim reads as an ungrammatical
                # fragment ("Water transported to the leaves."). Borrow the
                # root's auxiliary so the standalone claim stays complete.
                # Only when the conjunct also shares the subject: "..., but they
                # have distinct meanings" has its own subject and finite verb,
                # and borrowing "are" produced "Are they have distinct meanings".
                if not has_own_aux and not has_own_subject:
                    root_aux = next((t for t in root.children if t.dep_ in ("aux", "auxpass")), None)
                    if root_aux is not None:
                        token_ids = [root_aux.i] + token_ids

                if not has_own_subject and subj is not None:
                    token_ids = subj_ids + token_ids
                span = (subtree[0].idx, subtree[-1].idx + len(subtree[-1].text))
                results.append(("decomposed_conj", token_ids, span))
                excluded_ids |= {t.i for t in subtree}
        if has_conj:
            excluded_ids |= {t.i for t in sent if t.dep_ == "cc" and t.head.i == root.i}

        # Drop real punctuation only. spaCy marks "%" as is_punct (pos NOUN), so
        # filtering on is_punct turned "65% of the warming" into "65 of the
        # warming" -- a different claim. Filter on the PUNCT part-of-speech.
        # Word-internal hyphens (tag HYPH: "run-out", "non-violently") are
        # part of the word, not punctuation to drop.
        base_ids = [t.i for t in sent
                    if t.i not in excluded_ids and (t.pos_ != "PUNCT" or t.tag_ == "HYPH")]
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
                    words.append(_possessive(referent, doc[tid]))
                else:
                    had_unresolved = True
                    words.append(token.text)
            else:
                words.append(token.text)

        # Join with the SOURCE spacing where two tokens were adjacent in the
        # original text ("65%", "non-violently", "14-18", "body's"); a single
        # space where tokens were carved apart.
        text = ""
        for pos, (tid, word) in enumerate(zip(token_ids, words)):
            nxt = token_ids[pos + 1] if pos + 1 < len(token_ids) else None
            sep = doc[tid].whitespace_ if tid >= 0 and nxt == tid + 1 else " "
            text += word + sep
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
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            start = text.find(sentence, cursor)
            if start == -1:
                start = cursor
            end = start + len(sentence)
            cursor = end
            if not_a_claim(sentence, language):
                continue  # question, pleasantry, advice: nothing to verify
            claims.append(
                ExtractedClaim(
                    claim_id=f"claim_{len(claims)}",
                    # blanked asides leave runs of spaces: collapse them in the claim
                    # text only (the offsets above still index the original input)
                    text=" ".join(sentence.split()),
                    start_char=start,
                    end_char=end,
                    extraction_method="sentence_level",
                )
            )
        return claims
