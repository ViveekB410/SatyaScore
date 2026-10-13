"""
v2data/paraphrase_hiwiki.py -- set 4b "hiwiki_para" of results/v2_data_PROTOCOL.md: Hindi Wikipedia true sentences
reworded by qwen/qwen3.8-27b (Groq) so they no longer match Wikipedia word for word. A paraphrase is kept only if
(a) the multilingual NLI model gives entailment >= 0.80 in BOTH directions and (b) it contains exactly the same
numbers. The false item is the kept paraphrase with one number changed (same rule as set 4).
Checkpointed (v2data/sets/_paraphrases.json). Your Groq key is read from your shell, never printed.

    .venv/Scripts/python.exe v2data/paraphrase_hiwiki.py
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "v2data"))
from build_eval_sets import DEV2ASC, OUT, SEED, alter_number, save  # noqa: E402

MODEL = "qwen/qwen3.8-27b"
URL = "https://api.groq.com/openai/v1/chat/completions"
CACHE = OUT / "_paraphrases.json"
MIN_ENTAIL = 0.80
PROMPT = ("नीचे दिए गए हिंदी वाक्य को अपने शब्दों में दोबारा लिखिए। सभी तथ्य, नाम, तारीखें और संख्याएँ बिल्कुल "
          "वैसी ही रखें; कोई जानकारी न जोड़ें और न हटाएँ। केवल एक वाक्य लिखिए, और कुछ नहीं।")
_THINK = re.compile(r"<think>.*?</think>", re.S)
_DIGITS = re.compile(r"[\d०-९]+(?:[.,][\d०-९]+)*")


def numbers(s: str) -> list[str]:
    return sorted(n.translate(DEV2ASC).replace(",", "") for n in _DIGITS.findall(s))


def paraphrase(session: requests.Session, key: str, sentence: str) -> str:
    for attempt in range(5):
        r = session.post(URL, headers={"Authorization": f"Bearer {key}"}, timeout=90, json={
            "model": MODEL, "temperature": 0.3, "max_completion_tokens": 1024,
            "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": sentence}]})
        if r.status_code == 200:
            text = _THINK.sub("", r.json()["choices"][0]["message"].get("content") or "").strip()
            return " ".join(text.split()).strip('"“”')
        if r.status_code in (429, 500, 502, 503):
            time.sleep(min(60, float(r.headers.get("Retry-After", 2 ** attempt))))
            continue
        raise RuntimeError(f"Groq HTTP {r.status_code}")
    raise RuntimeError("Groq did not answer")


def main() -> None:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        sys.exit('GROQ_API_KEY is not set. In PowerShell: $env:GROQ_API_KEY = "gsk_..."')
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    items = pd.concat([pd.read_csv(OUT / f"hiwiki_{s}.csv", encoding="utf-8", dtype=str) for s in ("dev", "test")])
    items = items[items.label == "Verified"]
    session = requests.Session()
    for k, r in enumerate(items.itertuples(), 1):
        if r.item_id in cache:
            continue
        try:
            cache[r.item_id] = paraphrase(session, key, r.text)
        except Exception as e:
            print(f"skip {r.item_id}: {type(e).__name__}", flush=True)
            continue
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        if k % 20 == 0:
            print(f"{k}/{len(items)}", flush=True)
        time.sleep(2.5)

    from member1_model.nli_scorer import NLIScorer
    nli = NLIScorer()
    pairs = [(r.item_id, r.split, r.text, cache[r.item_id], r.meta) for r in items.itertuples() if r.item_id in cache]
    fwd = nli.score_batch([p[0] for p in pairs], [p[2] for p in pairs], [p[3] for p in pairs])
    bwd = nli.score_batch([p[0] for p in pairs], [p[3] for p in pairs], [p[2] for p in pairs])
    rng = random.Random(SEED)
    rows, stats = [], {"paraphrased": len(pairs), "failed_nli": 0, "failed_numbers": 0, "same_text": 0, "kept": 0}
    for (iid, split, orig, para, meta), f, b in zip(pairs, fwd, bwd):
        if para == orig:
            stats["same_text"] += 1
            continue
        if numbers(para) != numbers(orig):
            stats["failed_numbers"] += 1
            continue
        if min(f.entailment_prob, b.entailment_prob) < MIN_ENTAIL:
            stats["failed_nli"] += 1
            continue
        altered = alter_number(para, rng)
        if altered is None:
            continue
        stats["kept"] += 1
        m = json.dumps({**json.loads(meta), "original": orig, "entail_min": round(min(f.entailment_prob, b.entailment_prob), 3)},
                       ensure_ascii=False)
        rows.append({"item_id": iid.replace("-t", "-pt"), "set": "hiwiki_para", "split": split, "language": "hi",
                     "text": para, "label": "true", "meta": m})
        rows.append({"item_id": iid.replace("-t", "-pf"), "set": "hiwiki_para", "split": split, "language": "hi",
                     "text": altered, "label": "false", "meta": m})
    print("checks:", stats)
    save(rows, "hiwiki_para")


if __name__ == "__main__":
    main()
