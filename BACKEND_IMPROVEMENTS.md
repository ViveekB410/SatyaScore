# SatyaScore — Backend Improvements Spec

**Purpose:** get the `/detect` endpoint from ~40s per request to real-time (PRD target: <500ms per claim, <3s per 10-claim document on GPU), and make the backend deployable from a Colab GPU session so frontend work can proceed against a fast API.

**Audience:** Claude Code, working inside the `satyascore/` repo.

---

## Ground rules

Read these before changing anything.

1. **Scores must not change.** `RESULTS_SUMMARY.md`, `ablation_clean_*.md` and `results/*.json` are committed, reported results. Every task below is a performance or deployment change. If any task alters a `hallu_score`, `nli_prob`, `sem_sim` or verdict for the same input, it is wrong — revert and reconsider.

2. **Tests must stay green.** The repo has 108 passing tests. Run `python -m pytest` before you start and after every task.

3. **Do not change scoring semantics.** Specifically, leave these exactly as they are:
   - `MIN_RELEVANCE_THRESHOLD = 0.3` in `pipeline.py`
   - the net-score formula `0.5 + 0.5 * (entailment_prob - contradiction_prob)`
   - the "most decisive passage" selection: `max(net_scores, key=lambda s: abs(s - 0.5))`
   - `CMHSAScorer` renormalisation behaviour when a signal is `None`
   - the `NLI_EVIDENCE_TOP_K = 3` value

4. **Don't add new model downloads or swap checkpoints.** `mDeBERTa-v3-base-mnli-xnli` stays.

---

## Task 1 — Batch NLI across all claims (highest impact)

**File:** `member3_backend/pipeline.py`

**Current behaviour.** `DetectionPipeline.run()` loops over claims, and inside that loop calls `self.nli_scorer.score_batch(...)` once per claim with up to 3 passages. A 10-claim document therefore runs **10 forward passes of batch size ≤3**, not one pass of batch 30. This is the dominant cost in the request.

**Required change.** Restructure `run()` into phases:

1. Extract claims, embed them (both already batched — leave as is).
2. Loop over claims to do retrieval and relevance filtering only. Store each claim's `relevant_passages` list. Do **not** call the NLI scorer inside this loop.
3. After the loop, flatten every `(claim_index, passage)` pair across all claims into one flat list. If it is non-empty, make a **single** `score_batch` call with all pairs.
4. Regroup the results back to their originating claim, then compute `nli_prob` per claim using the unchanged net-score formula and unchanged decisive-passage selection.
5. Continue to fusion as before.

**Edge cases to preserve.** Claims with zero relevant passages must still get `nli_prob = None`, and must still fall through to the existing `insufficient evidence` `ClaimScore` path if every signal is unavailable. Claims must keep their original order in the response.

**Acceptance criteria.**
- Running the 12 claims in `DEMO_CLAIMS.md` produces `hallu_score` values identical to the documented ones (to 2 decimal places).
- `python -m pytest` still passes.
- Exactly one `score_batch` call per `/detect` request, verifiable via a test that mocks `NLIScorer.score_batch` and asserts `call_count == 1`.

---

## Task 2 — Stage-wise timing instrumentation

**Files:** `member3_backend/pipeline.py`, `member3_backend/api.py`

**Why.** The project currently only times the whole request. Stage-level numbers are needed to support the PRD's "real-time architecture" claim with evidence, and to produce a latency table for the paper.

**Required change.**
- Add a `timings_ms: dict[str, float]` field to `PipelineResult`, with keys: `claim_extraction`, `embedding`, `retrieval`, `nli`, `kg`, `fusion`, `total`.
- Measure each stage with `time.perf_counter()`. Retrieval and KG are inside loops — accumulate across iterations.
- Add an optional `timings` field to `DetectResponse` in `api.py`, populated from the pipeline result. Include it only when the request body sets `"include_timings": true`, so the default response shape stays unchanged for existing consumers.

**Acceptance criteria.** The timing keys sum to approximately `total` (small overhead difference is fine). Default `/detect` responses are byte-identical in shape to before.

---

## Task 3 — Warm up models at startup

**File:** `member3_backend/api.py`

**Current behaviour.** `NLIScorer._ensure_loaded()` is lazy, so the first `/detect` request after server start pays the full model load (~500MB). On Colab this penalty recurs every session.

**Required change.** In the existing `@app.on_event("startup")` hook, after the corpus loads, force both the NLI model and the embedder to load. Log the device in use and how long each load took.

**Acceptance criteria.** Server startup logs show the device (`cuda` or `cpu`) and load durations. The first `/detect` request is no slower than subsequent ones.

---

## Task 4 — GPU and fp16 support

**File:** `member1_model/nli_scorer.py`

**Note.** `CrossLingualEmbedder` already auto-detects CUDA and batches at 128 — leave it alone.

**Required change.** In `NLIScorer._ensure_loaded()`, when `self.device == "cuda"`, load the model in half precision (`torch_dtype=torch.float16`). Keep fp32 on CPU, since fp16 on CPU is slower, not faster.

**Acceptance criteria.** On CPU, outputs are bit-identical to before. On GPU, `entailment_prob` values match the CPU values within 1e-2 — if they diverge further than that, fp16 is unsafe for this model; drop the change and report it.

---

## Task 5 — Configuration via environment variables

**File:** `member3_backend/api.py`

**Why.** Colab-plus-tunnel deployment means the allowed CORS origin and the public URL change every session. These are currently hardcoded.

**Required change.** Read from environment variables, with the current values as defaults so nothing breaks if the variables are unset:

| Variable | Default | Controls |
|---|---|---|
| `SATYASCORE_API_KEY` | `dev-key-satyascore-2026` | the valid API key |
| `SATYASCORE_CORS_ORIGINS` | `http://localhost:5173` | comma-separated allowed origins |
| `SATYASCORE_NLI_TOP_K` | `3` | passages checked per claim |
| `SATYASCORE_DISABLE_KG` | `false` | see Task 6 |

**Acceptance criteria.** With no environment variables set, behaviour is unchanged. Setting `SATYASCORE_CORS_ORIGINS` to a comma-separated list allows all of them.

---

## Task 6 — Make the KG signal skippable

**Files:** `member3_backend/pipeline.py`, `member3_backend/api.py`

**Why.** `_try_kg_verification()` makes a live Wikidata SPARQL network call per claim. Measured coverage is 0% (`RESULTS_SUMMARY.md` §6), so it contributes nothing to scores but adds unpredictable network latency to live requests.

**Required change.** When `SATYASCORE_DISABLE_KG=true`, construct the pipeline without `entity_linker` and `wikidata` (both are already optional constructor arguments — use that existing mechanism rather than adding new branching logic inside `run()`).

**Acceptance criteria.** With KG disabled, `kg_conf` is `None` for every claim and `CMHSAScorer` renormalises over the remaining signals, exactly as it already does today for unlinkable claims. Final scores are unchanged from a KG-enabled run on the `DEMO_CLAIMS.md` set.

---

## Task 7 — Latency benchmark script

**New file:** `benchmark_latency.py` (project root, matching the existing flat script layout)

**Required behaviour.**
- Loads the claims from `DEMO_CLAIMS.md` (or an inline copy of them).
- Runs each through `DetectionPipeline` directly — not over HTTP, so network noise is excluded.
- Discards the first run as warm-up.
- Reports mean and median per-stage timings, plus per-claim and per-document totals.
- Prints a markdown table suitable for pasting into the paper, and writes it to `results/latency_benchmark.md`.
- Prints the detected device and the PRD targets (<500ms per claim, <3s per 10-claim document) alongside the measured values, marking each as met or missed.

**Acceptance criteria.** Runs on both CPU and GPU without code changes. Output states plainly whether the PRD latency targets were met.

---

## Task 8 — Improve `/health` for the frontend

**File:** `member3_backend/api.py`

**Required change.** Extend the `/health` response to include: `device`, `models_loaded` (bool), `corpus_size`, and `kg_enabled`. The frontend uses this for a backend-status indicator.

**Acceptance criteria.** `/health` requires no API key (unchanged) and returns valid JSON when models have not yet loaded.

---

## Task 9 — Fix the stale comment

**File:** `member3_backend/pipeline.py`

The comment on `self.nli_top_k` says the live API sets it to 1 to cut latency ~3x. `api.py` actually sets it to 3. Correct the comment to match reality.

---

## Optional (only if Tasks 1–9 are done and verified)

**Task 10 — File upload endpoint.** `POST /detect/file` accepting `.txt` and `.pdf`, extracting text and reusing the existing detection path. This closes FR-06, still listed as unbuilt in `README.md`. Enforce the same 20,000-character limit as `DetectRequest`.

**Task 11 — Demo claims endpoint.** `GET /examples` returning the curated claims from `DEMO_CLAIMS.md` as JSON, so the frontend can render example chips without duplicating the list.

---

## Verification checklist

Run before declaring done:

```bash
python -m pytest                      # expect 108 passing
python benchmark_latency.py           # record CPU numbers
```

Then confirm the 12 claims in `DEMO_CLAIMS.md` still produce their documented scores. If any score moved, a performance task changed behaviour — find it and fix it before proceeding.

---

## Deployment note (context, not a task)

The intended deployment is a Colab GPU session running uvicorn, exposed via an ngrok or cloudflared tunnel, with the Vite frontend running locally against that tunnel URL. Because `SATYASCORE_CORS_ORIGINS` defaults to `http://localhost:5173`, this works without further changes. Free-tier ngrok inserts a browser interstitial, which the frontend bypasses by sending an `ngrok-skip-browser-warning` header.

Colab sessions are ephemeral and GPU allocation is not guaranteed, so this is a development and benchmarking setup, not a stable host.
