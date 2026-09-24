"""
Polite HTTP for Wikimedia APIs (Wikidata search, entity API, SPARQL).

Wikimedia rate-limits anonymous clients (HTTP 429 "too many requests") and asks
for (1) a User-Agent that identifies the tool with a contact, (2) paced
requests, and (3) honouring Retry-After. Without this, a burst of KG lookups
got 429s, every lookup failed, and KG silently produced no signal.
See https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits
"""
from __future__ import annotations
import threading
import time

import requests

USER_AGENT = "SatyaScore/1.0 (https://github.com/ViveekB410/SatyaScore; capstone research)"
MIN_INTERVAL_S = 0.25   # at most ~4 requests/second from this process
MAX_RETRIES = 2
MAX_RETRY_AFTER_S = 30

_lock = threading.Lock()
_last = 0.0


def polite_get(session, url: str, params: dict, timeout: float = 10):
    """GET with pacing and Retry-After handling. Raises on final failure (the
    callers already turn exceptions into "lookup failed")."""
    global _last
    for attempt in range(MAX_RETRIES + 1):
        with _lock:
            wait = MIN_INTERVAL_S - (time.monotonic() - _last)
            if wait > 0:
                time.sleep(wait)
            _last = time.monotonic()
        response = session.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        if getattr(response, "status_code", 200) == 429 and attempt < MAX_RETRIES:
            try:
                delay = float(response.headers.get("Retry-After", 5))
            except (TypeError, ValueError):
                delay = 5.0
            time.sleep(min(max(delay, 1.0), MAX_RETRY_AFTER_S))
            continue
        response.raise_for_status()
        return response
    raise requests.HTTPError("429 Too Many Requests (retries exhausted)")
