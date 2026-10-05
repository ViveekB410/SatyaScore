# Real-time: where a check spends its time, before and after (2026-10-06)

Live pipeline (scratchpad latency probe), same three texts; "cold" = first check of these topics in a fresh
process (Wikipedia article texts already on disk from earlier runs), "warm" = the same check again.

| Text | Before: cold / warm | After: cold / warm |
|---|---|---|
| Chatbot answer, 6 claims (EN) | 27.7 s / 10.1 s | **5.1 s / 0.7 s** |
| General facts, 4 claims (EN) | 7.5 s / 4.4 s | **1.6 s / 0.3 s** |
| Hindi answer, 3 claims | 15.9 s / 9.4 s | **3.7 s / 0.4 s** |

Before, nearly all the time was live web lookups (Wikidata 5-13 s, Wikipedia search 3-9 s), not the
models (NLI + embeddings < 2 s). Changes, none of which changes a verdict:

1. **Per-service pacing** (member2_data/_http.py): one pace per host instead of one shared pace, so
   Wikipedia, Wikidata and the World Bank no longer wait for each other; up to 10 requests/s per host;
   Retry-After still honoured. Rate-limit retries during the measurements: 0.
2. **Remembered searches**: Wikidata name searches and Wikipedia searches / language links are kept in
   memory for a day (entity_linker.py, wiki_expander.py).
3. **Parallel lookups**: the claims' Wikipedia searches and article fetches, knowledge-graph lookups,
   fact-check searches and fact-name lookups run concurrently (6 at a time); the knowledge-graph lookups
   run at the same time as the Wikipedia expansion.
4. **Bounded waits**: a slow World Bank / WHO answer is given up after 8 s, one retry (the evaluation
   keeps 30 s, three tries).

**Same verdicts:** the 13 claims of these texts got identical verdicts from the old code (from git) and
the new code. All 245 tests pass.

**Still slower:** a topic never seen before needs its Wikipedia articles downloaded (a few seconds each,
in parallel); the first check after starting the server also loads the models (~20 s, once).