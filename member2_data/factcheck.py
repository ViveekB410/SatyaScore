"""
Professional fact-checks via the Google Fact Check Tools API (ClaimReview data
from fact-checkers such as PIB Fact Check, Alt News, BOOM, Factly, AFP, Reuters).

This module only SEARCHES and NORMALISES: for a claim it returns the fact-checked
claims Google finds, each with the publisher, its rating and a link, and maps the
rating to "false" / "true" / "mixed" / None. Deciding whether a returned fact-check
is about the SAME claim (and not, say, its negation) is done by the pipeline with
the embedder and the NLI model (member3_backend/pipeline.py).

The key is read from GOOGLE_FACTCHECK_KEY at call time and is never printed, logged
or stored. With no key the checker is simply unavailable (no signal, no error).
Results are cached on disk, so a claim is looked up once.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
CACHE_DAYS = 7
MAX_QUERY_CHARS = 250

# Ratings are free text in many languages. Mixed/qualified ratings are checked
# FIRST ("partly false" must not count as "false"); false before true ("not true").
_MIXED = ("mislead", "partly", "partially", "half", "mixture", "mixed", "missing context", "out of context",
          "exaggerat", "unproven", "unverified", "satire", "needs context", "disputed", "mostly true",
          "भ्रामक", "आंशिक", "अधूरा", "संदर्भ")
_FALSE = ("false", "fake", "hoax", "incorrect", "wrong", "not true", "fabricated", "baseless", "untrue",
          "pants on fire", "scam", "no evidence", "debunked", "myth", "not correct", "not accurate",
          "गलत", "ग़लत", "फर्जी", "फ़र्ज़ी", "झूठ", "असत्य", "फेक", "सही नहीं", "सच नहीं")
_TRUE = ("true", "correct", "accurate", "genuine", "सही", "सच", "सत्य")


def normalise_rating(text: str) -> str | None:
    t = (text or "").casefold()
    if not t:
        return None
    if any(w in t for w in _MIXED):
        return "mixed"
    if any(w in t for w in _FALSE):
        return "false"
    if any(re.search(rf"\b{re.escape(w)}\b", t) if w.isascii() else w in t for w in _TRUE):
        return "true"
    return None


@dataclass
class FactCheck:
    claim_text: str      # the claim the fact-checker checked
    rating: str          # the publisher's own wording, e.g. "False", "Misleading", "गलत"
    verdict: str | None  # normalised: "false" | "true" | "mixed" | None
    publisher: str
    url: str
    review_date: str
    language: str


class FactChecker:
    def __init__(self, cache_dir: Path | str | None = None, session: requests.Session | None = None,
                 timeout_s: float = 10):
        self._session = session or requests.Session()
        self._cache_dir = Path(cache_dir) if cache_dir else None
        self._timeout = timeout_s

    @staticmethod
    def available() -> bool:
        return bool(os.environ.get("GOOGLE_FACTCHECK_KEY"))

    def _cache_path(self, query: str, lang: str) -> Path | None:
        if not self._cache_dir:
            return None
        h = hashlib.sha1(f"{lang}|{query}".encode("utf-8")).hexdigest()[:20]
        return self._cache_dir / f"{h}.json"

    def search(self, claim: str, language: str) -> list[FactCheck]:
        """Fact-checks Google finds for this claim (possibly about other claims: the
        caller must check they match). [] with no key, no results or a failure."""
        key = os.environ.get("GOOGLE_FACTCHECK_KEY", "")
        if not key:
            return []
        query = " ".join(claim.split())[:MAX_QUERY_CHARS]
        path = self._cache_path(query, language)
        if path and path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - cached["t"] < CACHE_DAYS * 86400:
                return [FactCheck(**f) for f in cached["results"]]
        try:
            r = self._session.get(API_URL, params={"query": query, "languageCode": language,
                                                   "pageSize": 10, "key": key}, timeout=self._timeout)
            if r.status_code != 200:
                return []
            data = r.json()
        except (requests.RequestException, ValueError):
            return []
        out = []
        for c in data.get("claims", []):
            for rev in c.get("claimReview", []):
                rating = rev.get("textualRating", "")
                out.append(FactCheck(
                    claim_text=c.get("text", ""), rating=rating, verdict=normalise_rating(rating),
                    publisher=(rev.get("publisher") or {}).get("name") or (rev.get("publisher") or {}).get("site", ""),
                    url=rev.get("url", ""), review_date=rev.get("reviewDate", ""),
                    language=rev.get("languageCode", language)))
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"t": time.time(), "results": [asdict(f) for f in out]},
                                       ensure_ascii=False), encoding="utf-8")
        return out
