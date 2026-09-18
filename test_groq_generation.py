"""
Smoke test: run 3 real queries through Groq (Llama 3) before running the
full query bank. Confirms the API key, endpoint, and model name all work
together before spending real quota on 100 queries.

SETUP:
  1. Set your Groq API key as an environment variable (never hardcode it
     in a file you might commit to git or share):

     Windows PowerShell:
         $env:GROQ_API_KEY = "gsk_your_key_here"

     Then run this script in the SAME terminal session:
         python test_groq_generation.py

  2. If you'd rather not deal with environment variables right now, you
     can temporarily paste the key directly into the api_key="" line
     below — just don't commit/share the file afterward with the key
     still in it.
"""

import os

from dataset_pipeline.query_bank import get_seed_queries
from dataset_pipeline.response_collector import OpenAICompatibleGenerator, ResponseCollector

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"  # Groq's current Llama 3 model name

if not GROQ_API_KEY:
    raise SystemExit(
        "GROQ_API_KEY is not set. Set it as an environment variable first "
        "(see the SETUP comment at the top of this file), or paste your "
        "key directly into GROQ_API_KEY above for a quick local test."
    )

generator = OpenAICompatibleGenerator(
    api_key=GROQ_API_KEY,
    base_url=GROQ_BASE_URL,
    model=GROQ_MODEL,
)
collector = ResponseCollector(generators=[generator])

# Only the FIRST 3 seed queries — a real smoke test, not the full batch.
queries = get_seed_queries()[:3]

print(f"Testing {len(queries)} queries against Groq ({GROQ_MODEL})...\n")

for query in queries:
    print("=" * 70)
    print(f"[{query.domain} / {query.language}] {query.text}")
    responses = collector.collect(query.query_id, query.text, query.language)
    if not responses:
        print("  -> FAILED: no response returned (check your API key / network)")
        continue
    for r in responses:
        print(f"  -> ({r.source_llm}, {r.latency_ms:.0f}ms):")
        print(f"     {r.response_text}")

print("\n" + "=" * 70)
print("If you see real responses above (not errors), Groq is working.")
print("Next step: run the full 100-query batch — see README.md's")
print("'Dataset Generation' section for the full end-to-end script.")
