"""
build_corpus.py  --  Stage 1 of the bilingual signal recompute.

Builds a TARGETED bilingual evidence corpus from the AI Evidence URLs the claims
were anchored to (51 unique English Wikipedia articles). For each English article
it also resolves the Hindi counterpart via the MediaWiki langlinks API (never by
guessing the Hindi title) and fetches that too. Everything is cached to
evidence_corpus_cache.json so reruns need no network, and chunked into
language-tagged passages saved to corpus_passages.json.

Network only. Writes: evidence_corpus_cache.json, corpus_passages.json.
Touches nothing else.
"""
from __future__ import annotations
import json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path
import pandas as pd

SRC = "final annotator file(Sheet1) (1).csv"
CACHE = Path("evidence_corpus_cache.json")
PASSAGES = Path("corpus_passages.json")
UA = {"User-Agent": "SatyaScore/1.0 (B.Tech capstone; contact vivekborkar410@gmail.com)"}
MIN_CHARS, MAX_CHARS = 40, 1000


def api_get(host: str, params: dict) -> dict:
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def fetch_extract(host: str, title: str) -> str:
    d = api_get(host, {"action": "query", "prop": "extracts", "explaintext": 1,
                       "redirects": 1, "titles": title, "format": "json"})
    pages = d.get("query", {}).get("pages", {})
    if not pages:
        return ""
    return next(iter(pages.values())).get("extract", "") or ""


def resolve_hi_title(en_title: str) -> str | None:
    d = api_get("en.wikipedia.org", {"action": "query", "prop": "langlinks", "lllang": "hi",
                                     "redirects": 1, "titles": en_title, "format": "json"})
    pages = d.get("query", {}).get("pages", {})
    for p in pages.values():
        for ll in p.get("langlinks", []):
            if ll.get("lang") == "hi":
                return ll.get("*")
    return None


def title_from_url(url: str) -> str:
    slug = str(url).rstrip("/").split("/wiki/")[-1]
    return urllib.parse.unquote(slug).replace("_", " ")


def chunk(text: str, lang: str) -> list[str]:
    """Paragraph chunks, long ones split on sentence boundaries (danda for Hindi)."""
    out = []
    for para in re.split(r"\n{2,}", text):
        para = re.sub(r"\s+", " ", para).strip()
        if para.startswith("==") or len(para) < MIN_CHARS:
            continue
        if len(para) <= MAX_CHARS:
            out.append(para)
            continue
        buf = ""
        for sent in re.split(r"(?<=[।.!?])\s+", para):
            if len(buf) + len(sent) > MAX_CHARS and buf:
                out.append(buf.strip()); buf = ""
            buf += sent + " "
        if buf.strip():
            out.append(buf.strip())
    return out


def main() -> None:
    src = pd.read_csv(SRC, encoding="utf-8")
    titles = sorted({title_from_url(u) for u in src["AI Evidence URL"].dropna()
                     if "/wiki/" in str(u)})
    print(f"unique English articles to fetch: {len(titles)}")

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    failed = []
    for i, t in enumerate(titles, 1):
        if t in cache:
            continue
        entry = {"en_title": t, "en_text": "", "hi_title": None, "hi_text": ""}
        try:
            entry["en_text"] = fetch_extract("en.wikipedia.org", t)
            hi = resolve_hi_title(t)
            entry["hi_title"] = hi
            if hi:
                entry["hi_text"] = fetch_extract("hi.wikipedia.org", hi)
        except Exception as e:
            failed.append((t, repr(e)))
        cache[t] = entry
        if not entry["en_text"]:
            failed.append((t, "no EN extract"))
        time.sleep(0.15)
        if i % 10 == 0:
            print(f"  fetched {i}/{len(titles)}")
            CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    # build language-tagged passages
    passages = []
    en_articles = hi_articles = 0
    for t, e in cache.items():
        if e.get("en_text"):
            en_articles += 1
            for j, c in enumerate(chunk(e["en_text"], "en")):
                passages.append({"id": f"{t}::en::{j}", "text": c, "lang": "en", "title": t})
        if e.get("hi_text"):
            hi_articles += 1
            for j, c in enumerate(chunk(e["hi_text"], "hi")):
                passages.append({"id": f"{t}::hi::{j}", "text": c, "lang": "hi", "title": t})
    PASSAGES.write_text(json.dumps(passages, ensure_ascii=False), encoding="utf-8")

    en_p = sum(1 for p in passages if p["lang"] == "en")
    hi_p = sum(1 for p in passages if p["lang"] == "hi")
    no_hi = [t for t, e in cache.items() if not e.get("hi_text")]
    print("\n=== corpus summary ===")
    print(f"articles: EN {en_articles}, HI resolved+fetched {hi_articles}")
    print(f"passages: EN {en_p}, HI {hi_p}, total {len(passages)}")
    print(f"articles with NO Hindi version: {len(no_hi)}")
    if no_hi:
        sys.stdout.buffer.write(("  e.g. " + ", ".join(no_hi[:8]) + "\n").encode("utf-8"))
    if failed:
        print("failures:", failed[:8])
    # spot check: one Hindi passage
    hi_ex = next((p for p in passages if p["lang"] == "hi"), None)
    if hi_ex:
        sys.stdout.buffer.write(("sample HI passage: " + hi_ex["text"][:120] + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
