"""
round3_generate.py -- KG relational pilot, step 1 (round3/PREREGISTRATION.md).

1. Asks each fixed question in round3/questions.json to each model in GROQ_MODELS
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
import re
import sys
import time
from pathlib import Path

import pandas as pd

from dataset_pipeline.response_collector import OpenAICompatibleGenerator
from member2_data.entity_linker import EntityLinker
from member3_backend.claim_extractor import ClaimExtractor

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "round3"
RAW = OUT / "raw_responses_round3.json"
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
# Pre-registered model was the dataset's llama-3.3-70b-versatile; Groq returned HTTP 404 for it
# (no longer available to this key). Recorded deviation (round3/PREREGISTRATION.md): the two
# general chat models the key offers, from different families, one answer each, pooled.
GROQ_MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
DELAY_S = 2.0                             # Groq free-tier pacing, as collect_responses.py
MAX_CLAIMS, SEED = 70, 42
COLS = ["claim_id", "language", "source_question", "claim_text", "full_response",
        "verdict", "evidence_url", "notes"]


def _key() -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise SystemExit("GROQ_API_KEY is not set. In PowerShell: $env:GROQ_API_KEY = \"gsk_...\"")
    return key


def list_models() -> None:
    """Print the model ids this Groq key can use (the key itself is never printed)."""
    import requests
    r = requests.get("https://api.groq.com/openai/v1/models",
                     headers={"Authorization": f"Bearer {_key()}"}, timeout=30)
    r.raise_for_status()
    for m in sorted(r.json().get("data", []), key=lambda m: m["id"]):
        print(m["id"])


_THINK = re.compile(r"<think>.*?</think>", re.S)


def strip_reasoning(text: str) -> str:
    """Qwen3 can return its hidden reasoning inline as <think>...</think>; only the
    answer may be fact-checked, so the reasoning block is removed."""
    return _THINK.sub("", text).strip()


def _key_of(qid: str, model: str) -> str:
    return f"{qid}@{model}"


def collect(questions: list[dict], models: list[str]) -> dict:
    raw = json.loads(RAW.read_text(encoding="utf-8")) if RAW.exists() else {}
    for model in models:
        todo = [q for q in questions if _key_of(q["id"], model) not in raw]
        if not todo:
            continue
        gen = OpenAICompatibleGenerator(api_key=_key(), base_url=GROQ_BASE_URL, model=model)
        for i, q in enumerate(todo, 1):
            print(f"[{model} {i}/{len(todo)}] {q['id']}: {q['question']}", flush=True)
            try:
                text = gen.generate(q["question"], "en")
            except Exception as e:  # a re-run retries only the failures
                resp = getattr(e, "response", None)
                status = getattr(resp, "status_code", None)
                try:
                    detail = resp.json().get("error", {}).get("message", "") if resp is not None else ""
                except ValueError:
                    detail = (resp.text or "")[:300] if resp is not None else ""
                print(f"  failed: {type(e).__name__} {status or ''} {detail}".rstrip(), flush=True)
                if status in (400, 401, 403, 404):
                    # bad key, no access, or model unavailable: every call would fail the same way
                    raise SystemExit(f"Stopping: Groq returned HTTP {status}. Fix the cause above and re-run.")
                continue
            raw[_key_of(q["id"], model)] = {"qid": q["id"], "question": q["question"],
                                            "relation": q["relation"], "model": model,
                                            "response_text": text}
            RAW.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(DELAY_S)
    return raw


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-models", action="store_true", help="show the models your key can use")
    ap.add_argument("--models", nargs="+", default=GROQ_MODELS,
                    help="Groq model ids (default: the recorded deviation models)")
    args, _ = ap.parse_known_args()
    if args.list_models:
        list_models()
        return
    OUT.mkdir(exist_ok=True)
    questions = json.loads((OUT / "questions.json").read_text(encoding="utf-8"))
    raw = collect(questions, args.models)
    stray = {v["model"] for v in raw.values()} - set(args.models)
    if stray:
        raise SystemExit(f"{RAW.name} has answers from other models {stray}; delete it and re-run.")
    missing = [_key_of(q["id"], m) for m in args.models for q in questions
               if _key_of(q["id"], m) not in raw]
    if missing:
        raise SystemExit(f"{len(missing)} questions still have no answer ({missing}); re-run.")

    ce, el = ClaimExtractor(), EntityLinker()
    rows = []
    for model in args.models:
        tag = re.sub(r"[^a-z0-9]", "", model.split("/")[-1].lower())
        for q in questions:
            text = strip_reasoning(raw[_key_of(q["id"], model)]["response_text"])
            for k, c in enumerate(ce.extract(text, "en")):
                phrase = el.find_relation_phrase(c.text)
                if phrase:  # the pre-registered text rule; no KG lookup involved
                    rows.append({"claim_id": f"r3_{q['id']}_{tag}_{k}", "language": "en",
                                 "source_question": q["question"], "claim_text": c.text,
                                 "full_response": text, "relation_phrase": phrase,
                                 "source_llm": model})
    df = pd.DataFrame(rows).drop_duplicates("claim_text").reset_index(drop=True)
    n_eligible = len(df)
    if n_eligible > MAX_CLAIMS:
        df = df.sample(MAX_CLAIMS, random_state=SEED).sort_values("claim_id").reset_index(drop=True)
    df.to_csv(OUT / "claims_round3.csv", index=False, encoding="utf-8")

    from make_round2_set import write_xlsx  # needs openpyxl (.venv); imported only here
    blind = df.assign(verdict="", evidence_url="", notes="")[COLS]
    for tag in ("A", "B"):
        write_xlsx(blind, OUT / f"round3_annotator_{tag}.xlsx", "round3")
    sys.stdout.buffer.write(
        (f"\n{len(raw)} answers; {n_eligible} relational claims; {len(df)} in the pilot.\n"
         f"By relation: {df.relation_phrase.value_counts().to_dict()}\n"
         f"By model: {df.source_llm.value_counts().to_dict()}\n"
         f"Wrote round3/claims_round3.csv and round3/round3_annotator_A/B.xlsx\n").encode("utf-8"))


if __name__ == "__main__":
    main()
