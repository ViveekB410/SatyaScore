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
from urllib.parse import urlsplit

import requests

USER_AGENT = "SatyaScore/1.0 (https://github.com/ViveekB410/SatyaScore; capstone research)"
# Pacing is PER HOST (wikidata.org, en.wikipedia.org, api.worldbank.org, ... each have their
# own limits): a single shared pace made lookups to different services wait for each other.
MIN_INTERVAL_S = 0.1    # at most ~10 requests/second to any one host from this process
MAX_RETRIES = 2
MAX_RETRY_AFTER_S = 30

_lock = threading.Lock()
_next_slot: dict[str, float] = {}  # host -> earliest time the next request may start
stats = {"requests": 0, "retried_429": 0}  # for latency diagnostics


def _wait_turn(host: str) -> None:
    """Reserve this host's next send slot (threads queue up, MIN_INTERVAL_S apart)."""
    with _lock:
        now = time.monotonic()
        slot = max(now, _next_slot.get(host, 0.0))
        _next_slot[host] = slot + MIN_INTERVAL_S
    if slot > now:
        time.sleep(slot - now)


def polite_get(session, url: str, params: dict, timeout: float = 10):
    """GET with per-host pacing and Retry-After handling. Raises on final failure (the
    callers already turn exceptions into "lookup failed")."""
    host = urlsplit(url).netloc
    for attempt in range(MAX_RETRIES + 1):
        _wait_turn(host)
        stats["requests"] += 1
        response = session.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        if getattr(response, "status_code", 200) == 429 and attempt < MAX_RETRIES:
            stats["retried_429"] += 1
            try:
                delay = float(response.headers.get("Retry-After", 5))
            except (TypeError, ValueError):
                delay = 5.0
            time.sleep(min(max(delay, 1.0), MAX_RETRY_AFTER_S))
            continue
        response.raise_for_status()
        return response
    raise requests.HTTPError("429 Too Many Requests (retries exhausted)")
