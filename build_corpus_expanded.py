"""
build_corpus_expanded.py -- a larger, PERSISTENT evidence index (PRD FR-03).

  demo corpus (corpus_passages_demo.json, 245 articles)
+ every Wikipedia article already downloaded by on-demand expansion
  (results/_wiki_cache, instance/wiki_cache)
+ Wikipedia's Vital Articles, Level 3 (~1,000 core topics chosen by Wikipedia
  editors), English, plus each article's Hindi counterpart (interlanguage link)

Articles are fetched with the official API (member3_backend/wiki_expander.py:
polite, cached, downloaded once), split exactly like the corpus, embedded with the
pipeline's XLM-R embedder and saved. The API loads this file at startup when it
exists (instead of the demo corpus), so the larger index survives restarts; live
expansion still adds whatever is missing.

    .venv/Scripts/python.exe build_corpus_expanded.py        (GPU recommended)
Writes corpus_passages_expanded.json + corpus_vectors_expanded.npy (git-ignored:
too large for GitHub; rebuild with this command).
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

import numpy as np
import requests

from member2_data._http import USER_AGENT, polite_get
from member3_backend.wiki_expander import WikiExpander, chunk, indexed_titles_from_cache

ROOT = Path(__file__).resolve().parent
CACHES = [ROOT / "results" / "_wiki_cache", ROOT / "instance" / "wiki_cache"]
VITAL_PAGE = "Wikipedia:Vital articles/Level/3"


def vital_titles(session: requests.Session) -> list[str]:
    r = polite_get(session, "https://en.wikipedia.org/w/api.php", {
        "action": "parse", "page": VITAL_PAGE, "prop": "links", "format": "json", "redirects": 1}, timeout=60)
    return [l["*"] for l in r.json()["parse"]["links"] if l.get("ns") == 0 and "exists" in l]


def main() -> None:
    demo = json.loads((ROOT / "corpus_passages_demo.json").read_text(encoding="utf-8"))
    demo_vecs = np.load(ROOT / "corpus_vectors_demo.npy")
    known = indexed_titles_from_cache(ROOT / "evidence_corpus_cache.json")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    fetcher = WikiExpander(embedder=None, retriever=None, cache_dir=CACHES[0], session=session)

    # 1) Vital Articles (EN + HI counterpart) into the cache
    vital = vital_titles(session)
    print(f"Vital Articles Level 3: {len(vital)} titles", flush=True)
    t0, failed = time.time(), 0
    for i, title in enumerate(vital, 1):
        try:
            if ("en", title) not in known:
                fetcher.fetch(title, "en")
            hi = fetcher.langlink(title, "en", "hi")
            if hi and ("hi", hi) not in known:
                fetcher.fetch(hi, "hi")
        except Exception:
            failed += 1
        if i % 50 == 0:
            print(f"  {i}/{len(vital)} ({time.time() - t0:.0f}s, {failed} failed)", flush=True)

    # 2) every cached article not already in the demo corpus
    articles: dict[tuple[str, str], str] = {}
    for cache in CACHES:
        for f in cache.glob("*/*.json"):
            a = json.loads(f.read_text(encoding="utf-8"))
            key = (a["lang"], a["title"])
            if key not in known and a.get("text"):
                articles.setdefault(key, a["text"])
    ids, texts, langs = [], [], []
    for (lang, title), body in sorted(articles.items()):
        pieces = chunk(body)
        ids += [f"wiki:{lang}:{title}::{j}" for j in range(len(pieces))]
        texts += pieces
        langs += [lang] * len(pieces)
    n_en = sum(1 for (l, _) in articles if l == "en")
    print(f"new articles: {len(articles)} (EN {n_en}, HI {len(articles) - n_en}) -> {len(texts):,} passages; embedding...",
          flush=True)

    from member1_model.embeddings import CrossLingualEmbedder
    vecs = CrossLingualEmbedder().embed(ids, texts, langs).vectors.astype(np.float32)

    passages = demo + [{"id": i, "text": t, "lang": l, "title": i.split(":", 2)[2].rsplit("::", 1)[0]}
                       for i, t, l in zip(ids, texts, langs)]
    vectors = np.concatenate([demo_vecs.astype(np.float32), vecs])
    assert len(passages) == vectors.shape[0]
    (ROOT / "corpus_passages_expanded.json").write_text(json.dumps(passages, ensure_ascii=False), encoding="utf-8")
    np.save(ROOT / "corpus_vectors_expanded.npy", vectors)
    by_lang = {l: sum(1 for p in passages if p["lang"] == l) for l in ("en", "hi")}
    sys.stdout.buffer.write((f"wrote corpus_passages_expanded.json: {len(passages):,} passages {by_lang} "
                             f"({len(demo):,} demo + {len(texts):,} new; {failed} failed lookups)\n").encode("utf-8"))


if __name__ == "__main__":
    main()
