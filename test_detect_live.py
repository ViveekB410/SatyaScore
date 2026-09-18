"""Quick end-to-end check that /detect works with trained weights + cached
bilingual corpus. Not a unit test — a live smoke check. Run:
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/Scripts/python.exe test_detect_live.py
"""
import sys
from fastapi.testclient import TestClient
from member3_backend.api import app

H = {"X-API-Key": "dev-key-satyascore-2026"}


def out(s):
    sys.stdout.buffer.write((s + "\n").encode("utf-8")); sys.stdout.flush()


with TestClient(app) as client:  # context manager triggers startup (corpus load)
    out(f"health: {client.get('/health').json()}")
    # auth check
    out(f"no-key -> {client.post('/detect', json={'text':'x','language':'en'}).status_code} (expect 422/401)")
    for lang, text in [("en", "Delhi is the capital of India."),
                       ("hi", "भारत की राजधानी दिल्ली है।")]:
        r = client.post("/detect", json={"text": text, "language": lang}, headers=H)
        out(f"\n[{lang}] status={r.status_code}")
        if r.status_code == 200:
            j = r.json()
            out(f"  overall_score={j['overall_score']:.3f}  time_ms={j['processing_time_ms']:.0f}  claims={len(j['claims'])}")
            for c in j["claims"]:
                out(f"    verdict={c['verdict']} score={c['hallu_score']:.3f} signals={c['active_signals']} note={c.get('note')}")
                out(f"      claim: {c['text'][:70]}")
        else:
            out(f"  body={r.json()}")
