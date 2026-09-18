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

Language = Literal["en", "hi", "mr"]

WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours, per FR-03

# Wikidata language codes differ slightly from ours for Hindi/Marathi in
# some contexts, but these are the standard ones.
_LANG_CODE = {"en": "en", "hi": "hi", "mr": "mr"}


@dataclass
class TripleVerification:
    subject_qid: str
    property_pid: str
    expected_value: str
    found: bool
    confidence: float  # 0.0-1.0
    used_fallback_label: bool  # True if we had to fall back to English label
    source: Literal["cache", "live"]


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
    ) -> TripleVerification:
        cache_key = f"{subject_qid}|{property_pid}|{expected_value}|{language}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            # Return a copy with source="cache" — mutating `cached` directly
            # would also silently corrupt the object handed back on the
            # original (live) call, since both are the same object in memory.
            return replace(cached, source="cache")

        query = self._build_ask_query(subject_qid, property_pid, expected_value)
        found, used_fallback = self._run_ask_with_fallback(query, subject_qid, property_pid, expected_value, language)

        confidence = 1.0 if found else 0.0
        if found and used_fallback:
            # Slightly discount confidence when we only matched via the
            # English-label fallback rather than a native-language label —
            # this is a known, documented limitation (Section 7.2 / 16).
            confidence = 0.85

        result = TripleVerification(
            subject_qid=subject_qid,
            property_pid=property_pid,
            expected_value=expected_value,
            found=found,
            confidence=confidence,
            used_fallback_label=used_fallback,
            source="live",
        )
        self._cache.set(cache_key, result)
        return result

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
    ) -> tuple[bool, bool]:
        found = self._execute_ask(query)
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
            response = self._session.get(
                WIKIDATA_SPARQL_ENDPOINT,
                params={"query": query, "format": "json"},
                headers={"User-Agent": "SatyaScore/1.0 (capstone research project)"},
                timeout=10,
            )
            response.raise_for_status()
            bindings = response.json()["results"]["bindings"]
            return bindings[0]["label"]["value"] if bindings else None
        except (requests.RequestException, KeyError, IndexError, ValueError):
            return None

    def _execute_ask(self, query: str) -> bool:
        try:
            response = self._session.get(
                WIKIDATA_SPARQL_ENDPOINT,
                params={"query": query, "format": "json"},
                headers={"User-Agent": "SatyaScore/1.0 (capstone research project)"},
                timeout=10,
            )
            response.raise_for_status()
            return bool(response.json().get("boolean", False))
        except (requests.RequestException, KeyError, ValueError):
            return False

    @staticmethod
    def _build_ask_query(subject_qid: str, property_pid: str, expected_value: str) -> str:
        # expected_value as a QID (entity-to-entity relation)
        if expected_value.startswith("Q"):
            return f"ASK {{ wd:{subject_qid} wdt:{property_pid} wd:{expected_value} . }}"
        # expected_value as a literal (e.g. a date or plain string)
        return f'ASK {{ wd:{subject_qid} wdt:{property_pid} "{expected_value}" . }}'
