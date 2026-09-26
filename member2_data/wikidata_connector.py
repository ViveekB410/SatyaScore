"""
Wikidata knowledge-graph connector — produces the KG_conf(c, G) signal
that feeds into Member 1's CMHSA scorer.

PRD refs: Section 7.2 (KG_conf definition), FR-03:
    - Query the Wikidata SPARQL API for entity-linked triple verification
    - Explicit fallback to English-labelled entities when a Hindi label
      is unavailable (Wikidata's Hindi coverage is narrower than English)
    - Cache SPARQL query results with a 24-hour TTL to reduce API calls

This module does NOT do entity linking (turning "Narendra Modi" into
Q1058) — that's assumed to happen upstream (Claim Extractor / NER step,
Member 3's territory). This module takes an already-identified entity
(QID) + relation (PID) + expected value, and checks Wikidata for
confirmation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Literal

import requests

from member2_data._http import polite_get

Language = Literal["en", "hi", "mr"]

WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours, per FR-03

# Single-valued properties: a DIFFERENT existing value is a real contradiction.
# (capital of, has capital, place of birth, place of death)
FUNCTIONAL_PIDS = {"P1376", "P36", "P19", "P20"}
# Place-valued properties: the claimed object may be any enclosing region, so
# the support query walks the located-in / country chain.
HIERARCHICAL_PIDS = {"P19", "P20", "P131", "P159"}
WIKIDATA_ENTITY_API = "https://www.wikidata.org/w/api.php"
MAX_HIERARCHY_DEPTH = 6
MAX_HIERARCHY_NODES = 60

# Wikidata language codes differ slightly from ours for Hindi/Marathi in
# some contexts, but these are the standard ones.
_LANG_CODE = {"en": "en", "hi": "hi", "mr": "mr"}


@dataclass
class TripleVerification:
    subject_qid: str
    property_pid: str
    expected_value: str
    found: bool
    confidence: float | None  # 1.0 supported, 0.0 contradicted, None unknown (no KG signal)
    used_fallback_label: bool  # True if we had to fall back to English label
    source: Literal["cache", "live"]
    status: Literal["supported", "contradicted", "unknown"] = "unknown"


class _TTLCache:
    """Minimal in-memory cache with a fixed time-to-live per entry."""

    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str):
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value) -> None:
        self._store[key] = (time.time() + self._ttl, value)

    def __len__(self) -> int:
        return len(self._store)


class WikidataConnector:
    """
    Usage:
        wd = WikidataConnector()
        result = wd.verify_triple(
            subject_qid="Q1058",       # Narendra Modi
            property_pid="P39",        # position held
            expected_value="Q14212",   # Prime Minister of India
            language="hi",
        )
        # result.confidence -> KG_conf for the CMHSA formula
    """

    def __init__(self, session: requests.Session | None = None, cache: _TTLCache | None = None):
        self._session = session or requests.Session()
        self._cache = cache or _TTLCache()

    def verify_triple(
        self,
        subject_qid: str,
        property_pid: str,
        expected_value: str,
        language: Language = "en",
        alternatives: tuple[str, ...] = (),
    ) -> TripleVerification:
        # `alternatives`: other items with the same name as expected_value (place
        # relations, see EntityLinker.link_claim). Supported if ANY matches;
        # contradicted only if none does.
        targets = {expected_value, *alternatives}
        cache_key = f"{subject_qid}|{property_pid}|{'+'.join(sorted(targets))}|{language}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            # Return a copy with source="cache" — mutating `cached` directly
            # would also silently corrupt the object handed back on the
            # original (live) call, since both are the same object in memory.
            return replace(cached, source="cache")

        # Three outcomes, not two. "Not found" is NOT evidence of falsity: the
        # triple may be mis-built, Wikidata may be incomplete, or the lookup may
        # have failed. Scoring those as 0.0 turned true claims into
        # Hallucinated ("Modi is the Prime Minister of India" -> 0.0).
        used_fallback = False
        if expected_value.startswith("Q"):
            found, has_value = self._entity_check(subject_qid, property_pid, targets)
        else:  # literal value (rare): SPARQL ASK, with the Hindi-label fallback
            query = self._build_ask_query(subject_qid, property_pid, expected_value)
            found, used_fallback = self._run_ask_with_fallback(
                query, subject_qid, property_pid, expected_value, language)
            has_value = None

        if found is True:
            status = "supported"
        elif found is None:
            status = "unknown"  # lookup failed (network / HTTP error)
        elif property_pid in FUNCTIONAL_PIDS and has_value:
            # Single-valued property that Wikidata DOES fill, with a different
            # value: a genuine contradiction ("Paris is the capital of Germany").
            status = "contradicted"
        else:
            status = "unknown"  # multi-valued property, or no value on record

        if status == "supported":
            # Slightly discount confidence when we only matched via the
            # English-label fallback rather than a native-language label —
            # this is a known, documented limitation (Section 7.2 / 16).
            confidence = 0.85 if used_fallback else 1.0
        elif status == "contradicted":
            confidence = 0.0
        else:
            confidence = None  # no KG signal; the scorer renormalises around it

        result = TripleVerification(
            subject_qid=subject_qid,
            property_pid=property_pid,
            expected_value=expected_value,
            found=status == "supported",
            confidence=confidence,
            used_fallback_label=used_fallback,
            source="live",
            status=status,
        )
        if found is not None:  # never cache a network failure for 24h
            self._cache.set(cache_key, result)
        return result

    # -- entity-API checks (fast, reliable; the SPARQL endpoint times out on paths)

    def _claim_values(self, qid: str, pid: str) -> set[str] | None:
        """Truthy entity values of `qid`'s property `pid` via wbgetclaims
        (preferred rank if any, else normal; deprecated skipped). None if the
        lookup failed."""
        key = f"vals|{qid}|{pid}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        try:
            response = polite_get(self._session, WIKIDATA_ENTITY_API, params={"action": "wbgetclaims", "entity": qid, "property": pid, "format": "json"}, timeout=10)
            statements = response.json()["claims"].get(pid, [])
        except Exception:
            return None
        live = [s for s in statements if s.get("rank") != "deprecated"]
        preferred = [s for s in live if s.get("rank") == "preferred"]
        values = set()
        for s in preferred or live:
            v = s.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(v, dict) and "id" in v:
                values.add(v["id"])
        self._cache.set(key, values)
        return values

    def _reaches(self, start: set[str], targets: set[str]) -> bool | None:
        """Is any of `targets` an enclosing region of any of `start`, via country (P17,
        checked first: usually one hop) and located-in (P131)? Breadth-first,
        bounded, stops as soon as the target is found. None if a lookup failed."""
        seen, frontier = set(start), list(start)
        for _ in range(MAX_HIERARCHY_DEPTH):
            nxt = []
            for q in frontier:
                for pid in ("P17", "P131"):
                    vals = self._claim_values(q, pid)
                    if vals is None:
                        return None
                    if targets & vals:
                        return True
                    nxt += [v for v in vals if v not in seen]
                    seen |= vals
            if not nxt or len(seen) > MAX_HIERARCHY_NODES:
                return False
            frontier = nxt
        return False

    def _entity_check(self, subject_qid: str, pid: str, object_qids: set[str]) -> tuple[bool | None, bool | None]:
        """(found, has_value). found is None when a lookup failed."""
        values = self._claim_values(subject_qid, pid)
        if values is None:
            return None, None
        if object_qids & values:
            return True, True
        if pid in HIERARCHICAL_PIDS and values:
            reached = self._reaches(values, object_qids)
            if reached is None:
                return None, True
            if reached:
                return True, True
        return False, bool(values)

    def get_label(self, qid: str, language: Language = "en") -> tuple[str | None, bool]:
        """
        Returns (label, used_fallback). Tries the requested language first;
        if Wikidata has no label in that language, falls back to English
        and flags it — this is the fallback behaviour FR-03 requires us to
        test and document explicitly for Hindi (and, worse, Marathi).
        """
        cache_key = f"label|{qid}|{language}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        label = self._fetch_label(qid, language)
        used_fallback = False
        if label is None and language != "en":
            label = self._fetch_label(qid, "en")
            used_fallback = True

        result = (label, used_fallback)
        self._cache.set(cache_key, result)
        return result

    # -- internal helpers ------------------------------------------------

    def _run_ask_with_fallback(
        self, query: str, subject_qid: str, property_pid: str, expected_value: str, language: Language
    ) -> tuple[bool | None, bool]:
        """(found, used_fallback); found is None when the lookup itself failed."""
        found = self._execute_ask(query)
        if found is None:
            return None, False
        if found:
            return True, False

        # If the direct triple check failed, it might be a label-coverage
        # issue rather than a factual mismatch (e.g. expected_value was
        # passed as a Hindi label string and Wikidata has no Hindi label
        # for that entity). Only relevant when expected_value isn't a QID.
        if language != "en" and not expected_value.startswith("Q"):
            label, _ = self.get_label_qid_by_string(expected_value, language)
            if label is not None:
                fallback_query = self._build_ask_query(subject_qid, property_pid, label)
                found = self._execute_ask(fallback_query)
                return found, True

        return False, False

    def get_label_qid_by_string(self, label_text: str, language: Language) -> tuple[str | None, bool]:
        """Placeholder entity-resolution hook — real implementation would
        query Wikidata's search API. Kept separate so it's easy to swap in
        a real implementation without touching the verification logic."""
        return None, False

    def _fetch_label(self, qid: str, language: Language) -> str | None:
        query = f"""
        SELECT ?label WHERE {{
          wd:{qid} rdfs:label ?label .
          FILTER(LANG(?label) = "{_LANG_CODE[language]}")
        }} LIMIT 1
        """
        try:
            response = polite_get(self._session, WIKIDATA_SPARQL_ENDPOINT, params={"query": query, "format": "json"}, timeout=10)
            bindings = response.json()["results"]["bindings"]
            return bindings[0]["label"]["value"] if bindings else None
        except (requests.RequestException, KeyError, IndexError, ValueError):
            return None

    def _execute_ask(self, query: str) -> bool | None:
        """True/False from Wikidata, or None if the lookup failed -- a failed
        request must never be read as "the fact is false"."""
        try:
            response = polite_get(self._session, WIKIDATA_SPARQL_ENDPOINT, params={"query": query, "format": "json"}, timeout=10)
            body = response.json()
            if "boolean" not in body:
                return None
            return bool(body["boolean"])
        except (requests.RequestException, KeyError, ValueError, Exception):
            return None

    @staticmethod
    def _build_ask_query(subject_qid: str, property_pid: str, expected_value: str) -> str:
        # expected_value as a QID (entity-to-entity relation)
        # (QID objects are checked via the entity API in _entity_check; a
        # property-path ASK for place hierarchies timed out on the endpoint.)
        if expected_value.startswith("Q"):
            return f"ASK {{ wd:{subject_qid} wdt:{property_pid} wd:{expected_value} . }}"
        # expected_value as a literal (e.g. a date or plain string)
        return f'ASK {{ wd:{subject_qid} wdt:{property_pid} "{expected_value}" . }}'
