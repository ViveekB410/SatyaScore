"""
On-demand Wikipedia expansion of the evidence index.

PRD FR-03 asks for a FAISS index of multilingual Wikipedia passages that "SHALL
support index updates without a full rebuild". The fixed demo corpus covers 245
articles, and the evaluations showed that most claims fail for lack of evidence,
not for lack of a better judge. This module grows the index on demand:

  for each claim:
    1. search the claim's own Wikipedia (en.wikipedia / hi.wikipedia) with the
       official search API, top SEARCH_LIMIT articles;
    2. for a Hindi article also take its English counterpart (Wikipedia's own
       interlanguage link): Hindi articles are often short;
    3. articles already indexed are skipped; new ones are chunked exactly like
       the existing corpus (build_corpus.chunk), embedded with the pipeline's
       embedder and ADDED to the FAISS index (no rebuild).

Only the claim text is used (never labels or annotators' evidence links), so the
same thing happens for any user's input. Wikipedia's official API only: no web
scraping. Article text is cached on disk, so each article is downloaded once.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

from member2_data._http import USER_AGENT, polite_get

SEARCH_LIMIT = 3
MAX_NEW_ARTICLES_PER_CLAIM = 4
MIN_CHARS, MAX_CHARS = 40, 1000        # identical to build_corpus.chunk (tested)
MAX_QUERY_CHARS = 300                  # the search API rejects very long queries
SEARCH_TTL_S = 24 * 3600               # search results / language links remembered for a day
MAX_PARALLEL = 6                       # concurrent lookups per expansion (each host still paced)
_SENTENCE_END = re.compile(r"(?<=[।.!?])\s+")


def api_url(lang: str) -> str:
    return f"https://{lang}.wikipedia.org/w/api.php"


def chunk(text: str) -> list[str]:
    """Paragraph chunks; long paragraphs split on sentence ends (danda for Hindi).
    Same rules and limits as build_corpus.chunk, so new passages look like the
    existing corpus."""
    out = []
    for para in re.split(r"\n{2,}", text):
        para = re.sub(r"\s+", " ", para).strip()
        if para.startswith("==") or len(para) < MIN_CHARS:
            continue
        if len(para) <= MAX_CHARS:
            out.append(para)
            continue
        buf = ""
        for sent in _SENTENCE_END.split(para):
            if len(buf) + len(sent) > MAX_CHARS and buf:
                out.append(buf.strip())
                buf = ""
            buf += sent + " "
        if buf.strip():
            out.append(buf.strip())
    return out


@dataclass
class ExpansionStats:
    searched: int = 0
    articles_added: int = 0
    passages_added: int = 0
    failures: int = 0
    added_titles: list[tuple[str, str]] = field(default_factory=list)


class WikiExpander:
    def __init__(self, embedder, retriever, cache_dir: Path | str,
                 indexed: set[tuple[str, str]] | None = None,
                 session: requests.Session | None = None):
        """`indexed`: (lang, title) pairs already in the index, so they are never
        added twice. `retriever` must support add_passages() (FAISSRetriever)."""
        self.embedder, self.retriever = embedder, retriever
        self.cache_dir = Path(cache_dir)
        self.indexed: set[tuple[str, str]] = set(indexed or ())
        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", USER_AGENT)
        self._lock = threading.Lock()
        self._memo: dict[tuple, tuple[float, object]] = {}

    # -- Wikipedia API --------------------------------------------------------

    def search(self, text: str, lang: str) -> list[str]:
        """Wikipedia's top articles for a text; remembered in memory for SEARCH_TTL_S (speed)."""
        q = " ".join(text.split())[:MAX_QUERY_CHARS]
        key = ("search", lang, q)
        if (hit := self._memo_get(key)) is not None:
            return hit
        r = polite_get(self._session, api_url(lang), params={
            "action": "query", "list": "search", "srsearch": q, "srlimit": SEARCH_LIMIT,
            "srnamespace": 0, "format": "json"}, timeout=15)
        out = [h["title"] for h in r.json().get("query", {}).get("search", [])]
        self._memo_set(key, out)
        return out

    def _memo_get(self, key):
        with self._lock:
            hit = self._memo.get(key)
        return hit[1] if hit and time.monotonic() - hit[0] < SEARCH_TTL_S else None

    def _memo_set(self, key, value) -> None:
        with self._lock:
            self._memo[key] = (time.monotonic(), value)

    def langlink(self, title: str, from_lang: str, to_lang: str) -> str | None:
        key = ("langlink", title, from_lang, to_lang)
        if (hit := self._memo_get(key)) is not None:
            return hit or None
        out = self._langlink(title, from_lang, to_lang)
        self._memo_set(key, out or "")
        return out

    def _langlink(self, title: str, from_lang: str, to_lang: str) -> str | None:
        r = polite_get(self._session, api_url(from_lang), params={
            "action": "query", "prop": "langlinks", "lllang": to_lang, "redirects": 1,
            "titles": title, "format": "json"}, timeout=15)
        for page in r.json().get("query", {}).get("pages", {}).values():
            for ll in page.get("langlinks", []):
                if ll.get("lang") == to_lang:
                    return ll.get("*")
        return None

    def _cache_path(self, lang: str, title: str) -> Path:
        h = hashlib.sha1(f"{lang}|{title}".encode("utf-8")).hexdigest()[:20]
        return self.cache_dir / lang / f"{h}.json"

    def fetch(self, title: str, lang: str) -> str:
        """Plain text of an article; cached on disk (downloaded once)."""
        path = self._cache_path(lang, title)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["text"]
        r = polite_get(self._session, api_url(lang), params={
            "action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
            "titles": title, "format": "json"}, timeout=25)
        pages = r.json().get("query", {}).get("pages", {})
        text = (next(iter(pages.values())).get("extract", "") or "") if pages else ""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"lang": lang, "title": title, "text": text,
                                    "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                                   ensure_ascii=False), encoding="utf-8")
        return text

    # -- expansion --------------------------------------------------------------

    def _candidates(self, text: str, lang: str) -> list[tuple[str, str]]:
        found = [(lang, t) for t in self.search(text, lang)]
        if lang == "hi":  # add the English counterpart of each Hindi article
            for _, t in list(found):
                en = self.langlink(t, "hi", "en")
                if en:
                    found.append(("en", en))
        new = [c for c in dict.fromkeys(found) if c not in self.indexed]
        return new[:MAX_NEW_ARTICLES_PER_CLAIM]

    def expand(self, claims: list[tuple[str, str]]) -> ExpansionStats:
        """Search, fetch, chunk, embed and add new articles for (text, lang) claims.
        A failed lookup is counted and skipped: expansion never breaks a request."""
        stats = ExpansionStats()

        def candidates(claim):  # searches run in parallel; results are used in claim order
            try:
                return self._candidates(*claim)
            except Exception:
                return None

        def fetch(c):
            try:
                return self.fetch(c[1], c[0])
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
            found = list(pool.map(candidates, claims))
            todo: list[tuple[str, str]] = []
            for f in found:
                stats.searched += 1
                if f is None:
                    stats.failures += 1
                    continue
                todo += [c for c in f if c not in todo]
            bodies = list(pool.map(fetch, todo))
        ids, texts, langs = [], [], []
        for (lang, title), body in zip(todo, bodies):
            if body is None:
                stats.failures += 1
                continue
            pieces = chunk(body)
            if not pieces:
                continue
            ids += [f"wiki:{lang}:{title}::{j}" for j in range(len(pieces))]
            texts += pieces
            langs += [lang] * len(pieces)
            stats.added_titles.append((lang, title))
        if texts:
            vectors = self.embedder.embed(ids, texts, langs).vectors
            with self._lock:
                self.retriever.add_passages(ids, texts, vectors)
        with self._lock:
            self.indexed.update(stats.added_titles)
        stats.articles_added = len(stats.added_titles)
        stats.passages_added = len(texts)
        return stats


def indexed_titles_from_passages(passages: list[dict]) -> set[tuple[str, str]]:
    """(lang, title) of articles added by expansion or build_corpus_expanded.py
    (passage ids "wiki:<lang>:<title>::<n>")."""
    out = set()
    for p in passages:
        pid = p.get("id", "")
        if pid.startswith("wiki:"):
            _, lang, rest = pid.split(":", 2)
            out.add((lang, rest.rsplit("::", 1)[0]))
    return out


def indexed_titles_from_cache(cache_path: Path | str) -> set[tuple[str, str]]:
    """(lang, title) pairs already in the demo corpus, from evidence_corpus_cache.json."""
    p = Path(cache_path)
    if not p.exists():
        return set()
    out = set()
    for key, e in json.loads(p.read_text(encoding="utf-8")).items():
        if e.get("en_text"):
            out.add(("en", e.get("en_title") or key))
        if e.get("hi_text") and e.get("hi_title"):
            out.add(("hi", e["hi_title"]))
    return out
