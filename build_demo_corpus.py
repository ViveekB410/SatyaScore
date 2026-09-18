"""
build_demo_corpus.py — a BIGGER bilingual corpus for the live /detect demo, so
it works on everyday claims (capitals, science, history, health, sports, ...),
not just the 51 dataset topics.

Keeps the experiment corpus (corpus_passages.json / corpus_vectors.npy) UNTOUCHED
for reproducibility. Writes a separate demo corpus that the API prefers if present:
    corpus_passages_demo.json, corpus_vectors_demo.npy

Reuses evidence_corpus_cache.json (network only for the new topics). Embedding is
slow on CPU (single embed() call over all passages) — it is NOT hung; be patient.

    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python build_demo_corpus.py
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np

from build_corpus import fetch_extract, resolve_hi_title, chunk, CACHE
from member1_model.embeddings import CrossLingualEmbedder

# 51 dataset topics already cached; add broad general-knowledge topics a demo user might test.
NEW_TOPICS = [
    # geography
    "India", "New Delhi", "Mumbai", "United States", "China", "Japan", "France", "Paris",
    "London", "United Kingdom", "Russia", "Germany", "Brazil", "Australia", "Canada", "Egypt",
    "Himalayas", "Ganges", "Mount Everest", "Amazon rainforest", "Sahara",
    # science
    "Gravity", "Theory of relativity", "Evolution", "Photosynthesis", "Atom", "Solar System",
    "Earth", "Moon", "Sun", "Electricity", "Climate change", "Global warming", "Ozone layer",
    "DNA", "Newton's laws of motion", "Periodic table", "Big Bang", "Black hole",
    "Artificial intelligence", "Machine learning", "Internet", "Computer", "Oxygen", "Water",
    # history + people
    "World War II", "World War I", "Cold War", "French Revolution", "Roman Empire",
    "Ancient Egypt", "Mahatma Gandhi", "Jawaharlal Nehru", "B. R. Ambedkar", "Mughal Empire",
    "British Raj", "Albert Einstein", "Isaac Newton", "Charles Darwin", "Marie Curie",
    "A. P. J. Abdul Kalam",
    # health
    "Cancer", "Diabetes", "Malaria", "COVID-19", "Tuberculosis", "Human brain", "Heart",
    "Blood", "Vaccine", "Antibiotic", "Nutrition", "Vitamin",
    # India / government
    "Constitution of India", "Supreme Court of India", "Parliament of India",
    "President of India", "Prime Minister of India", "Indian rupee", "Taj Mahal",
    # sports
    "Cricket", "Association football", "Tennis", "Olympic Games", "FIFA World Cup",
    "Sachin Tendulkar", "Virat Kohli", "Indian Premier League",
]


def main() -> None:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    # 1) fetch any new topics not already cached (EN + langlink-resolved HI)
    to_fetch = [t for t in NEW_TOPICS if t not in cache]
    print(f"cached articles: {len(cache)} | new topics to fetch: {len(to_fetch)}", flush=True)
    import time
    for i, t in enumerate(to_fetch, 1):
        entry = {"en_title": t, "en_text": "", "hi_title": None, "hi_text": ""}
        try:
            entry["en_text"] = fetch_extract("en.wikipedia.org", t)
            hi = resolve_hi_title(t)
            entry["hi_title"] = hi
            if hi:
                entry["hi_text"] = fetch_extract("hi.wikipedia.org", hi)
        except Exception as e:
            print(f"  ! {t}: {e}", flush=True)
        cache[t] = entry
        time.sleep(0.15)
        if i % 15 == 0:
            print(f"  fetched {i}/{len(to_fetch)}", flush=True)
            CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    # 2) chunk ALL cached articles into language-tagged passages
    passages = []
    for t, e in cache.items():
        if e.get("en_text"):
            for j, c in enumerate(chunk(e["en_text"], "en")):
                passages.append({"id": f"{t}::en::{j}", "text": c, "lang": "en", "title": t})
        if e.get("hi_text"):
            for j, c in enumerate(chunk(e["hi_text"], "hi")):
                passages.append({"id": f"{t}::hi::{j}", "text": c, "lang": "hi", "title": t})
    en_p = sum(p["lang"] == "en" for p in passages)
    print(f"total passages: {len(passages)} (EN {en_p}, HI {len(passages)-en_p})", flush=True)

    # 3) embed in chunks with progress + incremental save (all XLM-R, single space)
    embedder = CrossLingualEmbedder()
    print(f"embedding on {embedder.device}...", flush=True)
    ids = [p["id"] for p in passages]
    texts = [p["text"] for p in passages]
    vecs = np.zeros((len(passages), 768), dtype=np.float32)
    STEP = 512
    for s in range(0, len(passages), STEP):
        res = embedder.embed(ids[s:s+STEP], texts[s:s+STEP], ["en"] * len(ids[s:s+STEP]))
        vecs[s:s+res.vectors.shape[0]] = res.vectors
        print(f"  embedded {min(s+STEP, len(passages))}/{len(passages)}", flush=True)
        np.save("corpus_vectors_demo.npy", vecs)

    Path("corpus_passages_demo.json").write_text(json.dumps(passages, ensure_ascii=False), encoding="utf-8")
    np.save("corpus_vectors_demo.npy", vecs)
    print(f"DONE: wrote corpus_passages_demo.json + corpus_vectors_demo.npy ({len(passages)} passages)", flush=True)


if __name__ == "__main__":
    main()
