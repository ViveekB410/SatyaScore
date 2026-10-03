"""
MedlinePlus as a second evidence source, for health claims.

MedlinePlus (https://medlineplus.gov) is the US National Library of Medicine's consumer
health encyclopedia: plain-language health topic summaries written and reviewed by medical
professionals. Health is where Wikipedia evidence was weakest in our data, and where a wrong
verdict matters most.

How it works (the same way as the Wikipedia expansion, member3_backend/wiki_expander.py):
  for each claim:
    1. search MedlinePlus health topics with its official web service
       (https://wsearch.nlm.nih.gov/ws/query, db=healthTopics), top SEARCH_LIMIT topics;
       a Hindi claim is searched with the English titles of its top Wikipedia articles
       (MedlinePlus is English-only; evidence is matched across languages by XLM-R, as for
       English Wikipedia);
    2. new topics are chunked like the Wikipedia corpus, embedded and ADDED to the FAISS
       index as passages "medline:en:<title>::<n>";
    3. each topic's URL and its "also called" names are kept (SOURCES) so the passage links
       to its page and the evidence rule recognises the topic under any of its names.
The official API only, no scraping; results cached on disk; failures are skipped.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

from member2_data._http import USER_AGENT, polite_get
from member3_backend.wiki_expander import ExpansionStats, chunk

API = "https://wsearch.nlm.nih.gov/ws/query"
SEARCH_LIMIT = 2   # topics per query
MAX_QUERIES = 3    # queries per claim
PREFIX = "medline"

# passage title -> {"url", "alt"} for every MedlinePlus topic added in this process
SOURCES: dict[str, dict] = {}
_TAG = re.compile(r"<[^>]+>")


def _plain(fragment: str) -> str:
    """MedlinePlus summaries are HTML with search highlights: paragraphs and list items
    become separate lines, tags are removed."""
    t = re.sub(r"</?(p|li|ul|ol|h\d)( [^>]*)?>", "\n\n", fragment, flags=re.I)  # "What is X?<p>X is ..."
    return html.unescape(_TAG.sub("", t)).strip()


def parse(xml_text: str) -> list[dict]:
    """[{title, url, alt, text}] from a healthTopics search response."""
    out = []
    root = ET.fromstring(xml_text)
    for doc in root.iter("document"):
        fields: dict[str, list[str]] = {}
        for c in doc.findall("content"):
            fields.setdefault(c.get("name", ""), []).append("".join(c.itertext()))
        title = _plain((fields.get("title") or [""])[0])
        text = _plain((fields.get("FullSummary") or [""])[0])
        if title and text:
            out.append({"title": title, "url": doc.get("url", ""), "text": text,
                        "alt": [_plain(a) for a in fields.get("altTitle", []) if _plain(a)]})
    return out


def passage_id(title: str, n: int) -> str:
    return f"{PREFIX}:en:{title}::{n}"


class MedlineExpander:
    def __init__(self, embedder, retriever, cache_dir: Path | str, wiki=None,
                 session: requests.Session | None = None):
        """`wiki`: the WikiExpander, used only to find English titles for Hindi claims."""
        self.embedder, self.retriever, self.wiki = embedder, retriever, wiki
        self.cache_dir = Path(cache_dir)
        self.indexed: set[str] = set()
        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", USER_AGENT)
        self._lock = threading.Lock()

    def _queries(self, text: str, lang: str) -> list[str]:
        """Short queries: the service ranks whole sentences poorly ("Dengue fever is spread
        by mosquitoes" did not find the Dengue topic; "dengue fever" does). English: the
        claim's noun phrases; Hindi: the English titles of its top Wikipedia articles."""
        if lang == "en":
            from member3_backend.claim_extractor import _get_english_pipeline
            doc = _get_english_pipeline()(text)
            out = []
            for nc in doc.noun_chunks:
                words = [t.text for t in nc if not (t.is_stop or t.pos_ in ("DET", "PRON", "NUM", "PUNCT"))]
                if words and any(t.pos_ in ("NOUN", "PROPN") for t in nc):
                    out.append(" ".join(words))
            return list(dict.fromkeys(out))[:MAX_QUERIES]
        if self.wiki is None:
            return []
        en = [t for t in (self.wiki.langlink(t, lang, "en") for t in self.wiki.search(text, lang)) if t]
        return list(dict.fromkeys(en))[:MAX_QUERIES]

    def search(self, query: str) -> list[dict]:
        """Topics for a query; cached on disk (each query asked once)."""
        h = hashlib.sha1(query.encode("utf-8")).hexdigest()[:20]
        path = self.cache_dir / f"{h}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["topics"]
        r = polite_get(self._session, API, params={"db": "healthTopics", "term": query,
                                                   "retmax": SEARCH_LIMIT}, timeout=20)
        topics = parse(r.text)[:SEARCH_LIMIT]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"query": query, "topics": topics,
                                    "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                                   ensure_ascii=False), encoding="utf-8")
        return topics

    def expand(self, claims: list[tuple[str, str]]) -> ExpansionStats:
        """Search, chunk, embed and add new MedlinePlus topics for (text, lang) claims.
        Never raises: a failed lookup is counted and skipped."""
        stats = ExpansionStats()
        new: dict[str, dict] = {}
        for text, lang in claims:
            stats.searched += 1
            try:
                for q in self._queries(text, lang):
                    for t in self.search(q):
                        if t["title"] not in self.indexed and t["title"] not in new:
                            new[t["title"]] = t
            except Exception:
                stats.failures += 1
        ids, texts = [], []
        for title, t in new.items():
            pieces = chunk(t["text"])
            if not pieces:
                continue
            SOURCES[title] = {"url": t["url"], "alt": t.get("alt", [])}
            ids += [passage_id(title, j) for j in range(len(pieces))]
            texts += pieces
            stats.added_titles.append(("en", title))
        if texts:
            vectors = self.embedder.embed(ids, texts, ["en"] * len(texts)).vectors
            with self._lock:
                self.retriever.add_passages(ids, texts, vectors)
        with self._lock:
            self.indexed.update(t for _, t in stats.added_titles)
        stats.articles_added = len(stats.added_titles)
        stats.passages_added = len(texts)
        return stats
