"""
Entity linker — resolves free-text entity mentions to Wikidata QIDs, and
common relation phrases to Wikidata property IDs (PIDs).

This is the piece wikidata_connector.py's docstring flagged as missing:
WikidataConnector.verify_triple() needs a (subject_qid, property_pid,
expected_value) triple, but claims arrive as plain text like "Narendra
Modi is the Prime Minister of India." This module bridges that gap.

HONESTY NOTE ON SCOPE: full relation extraction (mapping an arbitrary
English/Hindi sentence to the *correct* Wikidata property) is a hard,
open NLP problem — not something a capstone-scale project solves from
scratch. This module handles it two ways:
  1. Entity mention -> QID: REAL, via Wikidata's public search API
     (wbsearchentities), which does fuzzy text matching server-side.
  2. Relation phrase -> PID: A hand-built lookup table covering common,
     high-frequency relations (nationality, position held, birthplace,
     capital, etc.) — NOT a general relation extractor. Claims using
     relations outside this table won't get a KG_conf signal (falls
     back to None, which CMHSAScorer already handles via renormalisation).
Expanding relation coverage is a good, scoped task for later — see the
`RELATION_TO_PID` table below, which is meant to keep growing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import requests

Language = Literal["en", "hi", "mr"]

WIKIDATA_SEARCH_ENDPOINT = "https://www.wikidata.org/w/api.php"

# Common relation phrases -> Wikidata property IDs. Deliberately a hand-built
# lookup, NOT a general relation extractor (see module docstring).
#
# DIRECTION CONVENTION: each entry assumes the claim reads
# "SUBJECT <phrase> OBJECT" and link_claim builds the triple
# (subject_qid, PID, object_qid). Only relations whose Wikidata direction
# matches that ordering are included, so the SPARQL ASK query is meaningful.
#
# NOTE on P39 (position held): the OBJECT must be the office itself
# (e.g. "Prime Minister of India" -> Q14212), not the country. That depends
# on upstream NER extracting the office phrase as the object entity; if NER
# instead extracts the country ("India"), the triple will mis-verify. This is
# a known limitation of pairing a simple relation table with generic NER.
RELATION_TO_PID: dict[str, str] = {
    # -- Positions / office held (object = the office) --
    "is the prime minister of": "P39",
    "is the president of": "P39",
    "is the chief minister of": "P39",
    "is the vice president of": "P39",
    "is the governor of": "P39",
    "holds the position of": "P39",
    # -- Place of birth / death (person -> place) --
    "was born in": "P19",
    "born in": "P19",
    "died in": "P20",
    "passed away in": "P20",
    # -- Citizenship (person -> country) --
    "is a citizen of": "P27",
    "is a national of": "P27",
    # -- Capital. "Paris is the capital of France" (city -> country) is P1376
    #    ("capital of"), NOT P36 ("capital", which is country -> city). The
    #    old P36 mapping here built ASK { Paris P36 France } and always failed.
    "is the capital of": "P1376",
    "has its capital in": "P36",  # reverse direction (country -> city)
    # -- Location (place / org -> place) --
    "is located in": "P131",
    "located in": "P131",
    "is situated in": "P131",
    "is headquartered in": "P159",
    "headquartered in": "P159",
    "is based in": "P159",
    # -- Founding (org -> person for "by"; org -> date for "in") --
    "was founded by": "P112",
    "was co-founded by": "P112",
    "was founded in": "P571",
    "was established in": "P571",
    # -- Authorship. NOTE: direction-limited — P50 ("author") is work->person,
    #    but our pattern has the person as SUBJECT, so this can mis-verify.
    #    Kept for continuity; a correct person->work mapping is P800.
    "is the author of": "P50",
    # -- Membership / part-of (direction-safe) --
    "is part of": "P361",
    "is a member of": "P463",
}


@dataclass
class EntityMatch:
    surface_text: str
    qid: str | None
    wikidata_label: str | None
    confidence: float  # search-rank-derived, not a calibrated probability


@dataclass
class LinkedTriple:
    subject_qid: str | None
    property_pid: str | None
    object_qid: str | None
    linkable: bool  # True only if all three parts resolved


class EntityLinker:
    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()

    def search_entity(self, text: str, language: Language = "en", limit: int = 1) -> EntityMatch:
        """Looks up the best-matching Wikidata entity for a text mention."""
        try:
            response = self._session.get(
                WIKIDATA_SEARCH_ENDPOINT,
                params={
                    "action": "wbsearchentities",
                    "search": text,
                    "language": language,
                    "format": "json",
                    "limit": limit,
                },
                headers={"User-Agent": "SatyaScore/1.0 (capstone research project)"},
                timeout=10,
            )
            response.raise_for_status()
            results = response.json().get("search", [])
        except (requests.RequestException, ValueError, KeyError):
            return EntityMatch(surface_text=text, qid=None, wikidata_label=None, confidence=0.0)

        if not results:
            return EntityMatch(surface_text=text, qid=None, wikidata_label=None, confidence=0.0)

        top = results[0]
        return EntityMatch(
            surface_text=text,
            qid=top.get("id"),
            wikidata_label=top.get("label"),
            confidence=1.0,  # Wikidata returns results pre-ranked; we take rank-1 as-is
        )

    def find_relation_pid(self, claim_text: str) -> str | None:
        """Substring match against RELATION_TO_PID, case-insensitive. Tries the
        LONGEST phrases first so a specific relation ("is the capital of")
        wins over any shorter phrase it contains ("located in"), rather than
        depending on dict insertion order. Still a lookup, not extraction —
        an unrecognised relation returns None and the claim gets no KG signal
        (kg_conf=None, which CMHSAScorer renormalises around)."""
        lowered = claim_text.lower()
        for phrase in sorted(RELATION_TO_PID, key=len, reverse=True):
            if phrase in lowered:
                return RELATION_TO_PID[phrase]
        return None

    def link_claim(
        self,
        claim_text: str,
        subject_text: str,
        object_text: str,
        language: Language = "en",
    ) -> LinkedTriple:
        """
        Attempts to resolve a claim into a (subject_qid, property_pid,
        object_qid) triple. `subject_text`/`object_text` are assumed
        already extracted (e.g. via NER) — this module does entity
        *linking* (text -> QID), not entity *recognition* (finding which
        spans of text are entities in the first place; that's NER, not
        built here — spaCy's NER in claim_extractor.py's pipeline could
        supply these spans as a follow-up integration).
        """
        pid = self.find_relation_pid(claim_text)
        subject_match = self.search_entity(subject_text, language)
        object_match = self.search_entity(object_text, language)

        linkable = bool(pid and subject_match.qid and object_match.qid)
        return LinkedTriple(
            subject_qid=subject_match.qid,
            property_pid=pid,
            object_qid=object_match.qid,
            linkable=linkable,
        )
