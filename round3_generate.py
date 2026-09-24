"""
round3_generate.py -- KG relational pilot, step 1 (round3/PREREGISTRATION.md).

1. Asks each fixed question in round3/questions.json to llama-3.3-70b-versatile
   via Groq with the unchanged dataset generator (checkpointed: re-running
   resumes and never re-asks a collected question).
2. Extracts claims with the current ClaimExtractor and keeps those containing a
   RELATION_TO_PID phrase; samples 70 with seed 42 if more qualify.
3. Writes round3/claims_round3.csv and two identical BLIND sheets
   round3/round3_annotator_A.xlsx / _B.xlsx.

Run (PowerShell), with your own key in your own shell -- it is read from the
environment and never printed or saved:
    $env:GROQ_API_KEY = "gsk_..."
    .venv/Scripts/python.exe round3_generate.py
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

from dataset_pipeline.response_collector import OpenAICompatibleGenerator
from make_round2_set import write_xlsx
from member2_data.entity_linker import EntityLinker
from member3_backend.claim_extractor import ClaimExtractor

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "round3"
RAW = OUT / "raw_responses_round3.json"
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"   # the dataset's model
DELAY_S = 2.0                             # Groq free-tier pacing, as collect_responses.py
MAX_CLAIMS, SEED = 70, 42
COLS = ["claim_id", "language", "source_question", "claim_text", "full_response",
        "verdict", "evidence_url", "notes"]


def collect(questions: list[dict]) -> dict:
    raw = json.loads(RAW.read_text(encoding="utf-8")) if RAW.exists() else {}
    todo = [q for q in questions if q["id"] not in raw]
    if todo:
        key = os.environ.get("GROQ_API_KEY", "")
        if not key:
            raise SystemExit("GROQ_API_KEY is not set. In PowerShell: $env:GROQ_API_KEY = \"gsk_...\"")
        gen = OpenAICompatibleGenerator(api_key=key, base_url=GROQ_BASE_URL, model=GROQ_MODEL)
        for i, q in enumerate(todo, 1):
            print(f"[{i}/{len(todo)}] {q['id']}: {q['question']}", flush=True)
            try:
                text = gen.generate(q["question"], "en")
            except Exception as e:  # keep going; a re-run retries only the failures
                print(f"  failed ({type(e).__name__}); re-run to retry", flush=True)
                continue
            raw[q["id"]] = {"question": q["question"], "relation": q["relation"],
                            "model": GROQ_MODEL, "response_text": text}
            RAW.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(DELAY_S)
    return raw


def main() -> None:
    OUT.mkdir(exist_ok=True)
    questions = json.loads((OUT / "questions.json").read_text(encoding="utf-8"))
    raw = collect(questions)
    missing = [q["id"] for q in questions if q["id"] not in raw]
    if missing:
        raise SystemExit(f"{len(missing)} questions still have no answer ({missing}); re-run.")

    ce, el = ClaimExtractor(), EntityLinker()
    rows = []
    for q in questions:
        text = raw[q["id"]]["response_text"]
        for k, c in enumerate(ce.extract(text, "en")):
            phrase = el.find_relation_phrase(c.text)
            if phrase:  # the pre-registered text rule; no KG lookup involved
                rows.append({"claim_id": f"r3_{q['id']}_{k}", "language": "en",
                             "source_question": q["question"], "claim_text": c.text,
                             "full_response": text, "relation_phrase": phrase})
    df = pd.DataFrame(rows).drop_duplicates("claim_text").reset_index(drop=True)
    n_eligible = len(df)
    if n_eligible > MAX_CLAIMS:
        df = df.sample(MAX_CLAIMS, random_state=SEED).sort_values("claim_id").reset_index(drop=True)
    df.to_csv(OUT / "claims_round3.csv", index=False, encoding="utf-8")

    blind = df.assign(verdict="", evidence_url="", notes="")[COLS]
    for tag in ("A", "B"):
        write_xlsx(blind, OUT / f"round3_annotator_{tag}.xlsx", "round3")
    sys.stdout.buffer.write(
        (f"\n{len(raw)} answers; {n_eligible} relational claims; {len(df)} in the pilot.\n"
         f"By relation: {df.relation_phrase.value_counts().to_dict()}\n"
         f"Wrote round3/claims_round3.csv and round3/round3_annotator_A/B.xlsx\n").encode("utf-8"))


if __name__ == "__main__":
    main()
