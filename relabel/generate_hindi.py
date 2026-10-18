"""
relabel/generate_hindi.py -- Version 2 data, step 1b (relabel/PROTOCOL.md): one Groq answer to each of the
50 new Hindi questions (even index: openai/gpt-oss-20b, odd index: qwen/qwen3.8-27b), then claims extracted
with the current extractor. Checkpointed: re-running resumes and never re-asks a collected question.

Your Groq key is read from your own shell and never printed or saved:
    $env:GROQ_API_KEY = "gsk_..."
    .venv/Scripts/python.exe relabel/generate_hindi.py
Writes relabel/raw_responses_hi_new.json and relabel/claims_v2_new_hi.csv.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dataset_pipeline.response_collector import OpenAICompatibleGenerator  # noqa: E402
from member3_backend.claim_extractor import ClaimExtractor  # noqa: E402

QUESTIONS = ROOT / "relabel" / "questions_hi_new.json"
RAW = ROOT / "relabel" / "raw_responses_hi_new.json"
OUT = ROOT / "relabel" / "claims_v2_new_hi.csv"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = ("openai/gpt-oss-20b", "qwen/qwen3.8-27b")   # fixed in relabel/PROTOCOL.md
DELAY_S = 2.5
_THINK = re.compile(r"<think>.*?</think>", re.S)  # Qwen may return its reasoning; it is not the answer


def main() -> None:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        sys.exit('GROQ_API_KEY is not set. In PowerShell: $env:GROQ_API_KEY = "gsk_..."')
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    done = json.loads(RAW.read_text(encoding="utf-8")) if RAW.exists() else {}
    gens = {m: OpenAICompatibleGenerator(api_key=key, base_url=GROQ_URL, model=m, timeout=120) for m in MODELS}
    for i, q in enumerate(questions):
        if q["id"] in done:
            continue
        model = MODELS[i % 2]
        for attempt in range(4):
            try:
                text = _THINK.sub("", gens[model].generate(q["question"], "hi")).strip()
                break
            except Exception as e:  # rate limit or network: wait and retry; the key is never shown
                print(f"  retry {attempt + 1} for {q['id']} ({type(e).__name__})", flush=True)
                time.sleep(10 * (attempt + 1))
        else:
            print(f"FAILED {q['id']}: left for the next run", flush=True)
            continue
        done[q["id"]] = {"query_text": q["question"], "language": "hi", "domain": q["domain"],
                         "source_llm": model, "response_text": text}
        RAW.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{len(done)}/{len(questions)}] {q['id']} ({model})", flush=True)
        time.sleep(DELAY_S)

    extractor = ClaimExtractor()
    rows = []
    for qid, e in done.items():
        for n, c in enumerate(extractor.extract(e["response_text"], "hi")):
            rows.append({"claim_id": f"v2_{qid}_c{n:02d}", "source_query_id": qid, "set": "new_hindi",
                         "language": "hi", "domain": e["domain"], "source_llm": e["source_llm"],
                         "source_question": e["query_text"], "claim_text": c.text, "start_char": c.start_char,
                         "end_char": c.end_char, "extraction_method": c.extraction_method,
                         "needs_context": bool(c.had_unresolved_pronoun), "full_response": e["response_text"]})
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"{len(df)} claims from {len(done)} answers -> {OUT.relative_to(ROOT)}")
    if len(done) < len(questions):
        print(f"WARNING: {len(questions) - len(done)} questions still unanswered; run again later.")


if __name__ == "__main__":
    main()
