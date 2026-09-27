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

import re
from dataclasses import dataclass
from typing import Literal

import requests

from member2_data._http import polite_get

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
# (e.g. "Prime Minister of India"), not the country NER extracts. link_claim
# rebuilds it as "<role> of <place>" via OFFICE_ROLES below.
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

# P39 phrases whose object is a jurisdiction: the office is "<role> of <place>".
OFFICE_ROLES: dict[str, str] = {
    "is the prime minister of": "Prime Minister",
    "is the president of": "President",
    "is the chief minister of": "Chief Minister",
    "is the vice president of": "Vice President",
    "is the governor of": "Governor",
}


# Place-valued relations. Their object is linked as the SET of Wikidata items
# whose name is exactly the claimed place, not the top search hit: round 3 found
# the top hit was often not a place ("Erode" -> a given name, "Naigaon" -> a
# monorail station, "Niphad" -> an insect genus), so true birthplaces were
# "contradicted" and false ones were contradicted only by luck.
PLACE_PIDS = {"P19", "P20", "P131", "P159"}
PLACE_SEARCH_LIMIT = 50  # the right "Naigaon" was hit 27 of 28
# Exact-name hits whose description says they are not a place.
_NOT_A_PLACE = ("given name", "family name", "surname", "genus", "species",
                "disambiguation", "encyclopedic article", "scholarly article",
                "film", "album", "song", "novel", "opera")


# Hindi relation templates. No Hindi NER model is wired in, so the patterns find
# the subject and object spans themselves. Each yields (subject, object, PID)
# candidates; ambiguous word boundaries give several, and only a split where BOTH
# sides match a Wikidata item by exact Hindi name is used.
_HI_PUNCT = re.compile(r"[\s।.!?]+$")
_HI_LIFE = re.compile(r"^(.+?) (का जन्म|का निधन|की मृत्यु) (.+?) में (?:हुआ|हुई)")
_HI_CAPITAL_OF = re.compile(r"^(.+?) की राजधानी (.+?) है$")      # "X की राजधानी Y है": country P36 city
_HI_IS_CAPITAL = re.compile(r"^(.+) की राजधानी है$")               # "Y (,) X की राजधानी है": city P1376 country
_HI_LOCATED = re.compile(r"^(.+) में स्थित (?:है|था|थी)$")          # "X Y में स्थित है": P131
MAX_HI_CANDIDATES = 4


def _splits(span: str, pid: str) -> list[tuple[str, str, str]]:
    if "," in span:
        s, o = span.split(",", 1)
        return [(s.strip(), o.strip(), pid)]
    toks = span.split()
    return [(" ".join(toks[:k]), " ".join(toks[k:]), pid) for k in range(1, len(toks))]


def hindi_relation_candidates(claim_text: str) -> list[tuple[str, str, str]]:
    """(subject, object, PID) readings of a Hindi claim; empty if no template fits."""
    t = _HI_PUNCT.sub("", " ".join(claim_text.split()))
    out: list[tuple[str, str, str]] = []
    if m := _HI_LIFE.match(t):
        pid = "P19" if m.group(2) == "का जन्म" else "P20"
        before = m.group(3).replace(",", " ").split()
        # the place is the last word(s) before "में": "... 1869 को पोरबंदर में हुआ"
        out += [(m.group(1), " ".join(before[-k:]), pid) for k in (1, 2) if len(before) >= k]
    elif m := _HI_CAPITAL_OF.match(t):
        out.append((m.group(1), m.group(2), "P36"))
    elif m := _HI_IS_CAPITAL.match(t):
        out += _splits(m.group(1), "P1376")
    elif m := _HI_LOCATED.match(t):
        out += _splits(m.group(1), "P131")
    return [c for c in out if c[0] and c[1]][:MAX_HI_CANDIDATES]


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
    # Place relations only: every place with exactly the claimed name
    # (object_qid is the first of them). Empty for other relations.
    object_candidates: tuple[str, ...] = ()


class EntityLinker:
    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()

    def search_entity(self, text: str, language: Language = "en", limit: int = 1) -> EntityMatch:
        """Looks up the best-matching Wikidata entity for a text mention."""
        try:
            response = polite_get(self._session, WIKIDATA_SEARCH_ENDPOINT, params={
                    "action": "wbsearchentities",
                    "search": text,
                    "language": language,
                    "format": "json",
                    "limit": limit,
                }, timeout=10)
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

    def search_places(self, text: str, language: Language = "en") -> tuple[str, ...] | None:
        """All items named exactly `text` (label or alias, any language, case-
        insensitive) that are not obviously non-places (the same filter also
        suits people and countries). () if there are none, None if the lookup
        failed."""
        try:
            response = polite_get(self._session, WIKIDATA_SEARCH_ENDPOINT, params={
                    "action": "wbsearchentities",
                    "search": text,
                    "language": language,
                    "format": "json",
                    "limit": PLACE_SEARCH_LIMIT,
                }, timeout=10)
            results = response.json().get("search", [])
        except (requests.RequestException, ValueError, KeyError):
            return None
        name = text.strip().casefold()
        return tuple(
            r["id"] for r in results
            if r.get("match", {}).get("text", "").strip().casefold() == name
            and not any(w in (r.get("description") or "").lower() for w in _NOT_A_PLACE))

    def link_hindi_claim(self, claim_text: str) -> list[LinkedTriple]:
        """Hindi path: the first template reading whose subject and object both
        match Wikidata items by exact Hindi name. Returns one triple per
        same-named subject (at most 3), so the caller can skip a namesake that
        has no value for the property. Empty if nothing links."""
        for subj, obj, pid in hindi_relation_candidates(claim_text):
            subjects = self.search_places(subj, "hi")
            if not subjects:
                continue
            objects = self.search_places(obj, "hi")
            if not objects:
                continue
            place = pid in PLACE_PIDS
            return [LinkedTriple(subject_qid=s, property_pid=pid, object_qid=objects[0], linkable=True,
                                 object_candidates=objects if place else ())
                    for s in subjects[:3]]
        return []

    def find_relation_pid(self, claim_text: str) -> str | None:
        """Substring match against RELATION_TO_PID, case-insensitive. Tries the
        LONGEST phrases first so a specific relation ("is the capital of")
        wins over any shorter phrase it contains ("located in"), rather than
        depending on dict insertion order. Still a lookup, not extraction —
        an unrecognised relation returns None and the claim gets no KG signal
        (kg_conf=None, which CMHSAScorer renormalises around)."""
        phrase = self.find_relation_phrase(claim_text)
        return RELATION_TO_PID[phrase] if phrase else None

    @staticmethod
    def find_relation_phrase(claim_text: str) -> str | None:
        lowered = claim_text.lower()
        for phrase in sorted(RELATION_TO_PID, key=len, reverse=True):
            if phrase in lowered:
                return phrase
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
        phrase = self.find_relation_phrase(claim_text)
        pid = RELATION_TO_PID[phrase] if phrase else None
        # P39 ("position held") takes the OFFICE as its value, not the country:
        # "Modi is the Prime Minister of India" -> (Modi, P39, "Prime Minister of
        # India"). Linking the country ("India") built a triple Wikidata can
        # never contain, which used to score a true claim as false.
        if phrase in OFFICE_ROLES:
            object_text = f"{OFFICE_ROLES[phrase]} of {object_text}"
        subject_match = self.search_entity(subject_text, language)
        candidates: tuple[str, ...] = ()
        if pid in PLACE_PIDS:
            # No exactly-named place (or a failed lookup) -> unlinked, i.e. no
            # KG signal, rather than a wrong entity that can "contradict".
            candidates = self.search_places(object_text, language) or ()
            object_qid = candidates[0] if candidates else None
        else:
            object_qid = self.search_entity(object_text, language).qid

        linkable = bool(pid and subject_match.qid and object_qid)
        return LinkedTriple(
            subject_qid=subject_match.qid,
            property_pid=pid,
            object_qid=object_qid,
            linkable=linkable,
            object_candidates=candidates,
        )
