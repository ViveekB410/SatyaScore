"""
STEP 1 of 2: Collect responses to all 100 seed queries from Groq.

Saves raw responses to a JSON file as it goes (checkpointed) — if the
run fails partway (rate limit, network blip), you can inspect what was
collected so far without losing everything, and the script skips
queries it's already collected on a re-run.

Run:
    python collect_responses.py
"""

import json
import os
import time
from pathlib import Path

from dataset_pipeline.query_bank import get_seed_queries
from dataset_pipeline.response_collector import OpenAICompatibleGenerator, ResponseCollector

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Groq's free tier has a requests-per-minute limit. A small delay between
# calls keeps you comfortably under it instead of hitting 429 errors.
DELAY_BETWEEN_CALLS_SECONDS = 2.0

OUTPUT_PATH = Path("raw_responses.json")

if not GROQ_API_KEY:
    raise SystemExit("GROQ_API_KEY is not set. See test_groq_generation.py's SETUP comment.")

generator = OpenAICompatibleGenerator(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL, model=GROQ_MODEL)
collector = ResponseCollector(generators=[generator])

queries = get_seed_queries()

# Resume support: load whatever's already been collected, skip those query_ids.
already_collected: dict = {}
if OUTPUT_PATH.exists():
    with open(OUTPUT_PATH, encoding="utf-8") as f:
        already_collected = json.load(f)
    print(f"Resuming — {len(already_collected)} responses already collected in {OUTPUT_PATH}")

for i, query in enumerate(queries):
    if query.query_id in already_collected:
        continue

    print(f"[{i+1}/{len(queries)}] {query.query_id}: {query.text[:60]}...")
    responses = collector.collect(query.query_id, query.text, query.language)

    if not responses:
        print("  -> FAILED, skipping")
        continue

    already_collected[query.query_id] = {
        "query_text": query.text,
        "language": query.language,
        "domain": query.domain,
        "responses": [
            {"source_llm": r.source_llm, "response_text": r.response_text} for r in responses
        ],
    }

    # Save after EVERY query, not just at the end — this is the checkpoint.
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(already_collected, f, ensure_ascii=False, indent=2)

    time.sleep(DELAY_BETWEEN_CALLS_SECONDS)

print(f"\nDone. {len(already_collected)}/{len(queries)} queries collected -> {OUTPUT_PATH}")
