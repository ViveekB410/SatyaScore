# SatyaScore — Frontend Spec

**Goal:** a single-page web dashboard where the user pastes LLM-generated text, gets the full text back with problem claims highlighted in place, and sees those claims listed separately below.

**Audience:** Claude Code, working in the `satyascore/` repo.

**Deadline context:** this is for a Phase 2 presentation demo. Prefer working and simple over complete. Do not add features not listed here.

---

## Ground rules

1. **Do not change any scoring logic.** Task 0 below touches the backend, but only to forward data that already exists. No formula, threshold, or weight changes. `RESULTS_SUMMARY.md` and `results/*.json` are committed results and must stay valid.
2. **Run `python -m pytest` before and after Task 0.** 108 tests pass today. They must still pass.
3. **Do not show numeric scores anywhere in the UI.** Deliberate product decision — verdicts only.
4. **Three verdicts, not two:** `Verified`, `Uncertain`, `Hallucinated`. Uncertain is common in real output and must be a first-class state, not an edge case.

---

## Task 0 — Backend: forward claim character spans (do this first)

The claim extractor already computes character offsets into the original input text, but they are discarded before reaching the API. The frontend needs them to highlight claims in place.

**File: `member3_backend/claim_extractor.py`** — no changes. `ExtractedClaim` already has `start_char`, `end_char`, `extraction_method`, `had_unresolved_pronoun`.

**File: `member3_backend/pipeline.py`**
- `_extract_claims()` currently returns `[c.text for c in self.claim_extractor.extract(...)]`, discarding the span data. Change it to return the `ExtractedClaim` objects.
- The naive sentence-splitter fallback (`_naive_split_into_claims`) must also produce objects with the same fields, computing real offsets as it splits. Use `extraction_method="sentence_level"`.
- `PipelineResult.claims` becomes a list of these objects rather than a list of strings. Update internal uses accordingly — claim text is now `claim.text`.

**File: `member3_backend/api.py`**
- Add to `ClaimResult`: `start_char: int`, `end_char: int`, `extraction_method: str`.
- Populate them from the pipeline result.

**Acceptance criteria**
- `python -m pytest` passes.
- The 12 claims in `DEMO_CLAIMS.md` produce the same verdicts as before.
- For a Hindi input, every returned span, when sliced out of the original text, matches the claim text exactly.
- For English, spans are valid ranges within the input (see caveat below).

**Known caveat — do not try to fix this.** Per `claim_extractor.py`'s docstring: for claims split out of a sentence by decomposition, the span is the exact clause. For the `decomposed_base` claim left over, the span covers the whole source sentence. So some English highlights will cover more text than the specific claim. This is documented upstream behaviour, not a bug. Hindi is always one sentence per claim and therefore exact.

---

## The API contract

`POST /detect`

Headers: `X-API-Key: dev-key-satyascore-2026`

Body:
```json
{ "text": "...", "language": "en" }
```

Response (after Task 0):
```json
{
  "claims": [
    {
      "claim_id": "claim_0",
      "text": "The capital of Japan is Beijing.",
      "hallu_score": 0.19,
      "verdict": "Hallucinated",
      "active_signals": ["semsim", "nli"],
      "note": null,
      "start_char": 0,
      "end_char": 32
    }
  ],
  "overall_score": 0.42,
  "processing_time_ms": 38200
}
```

`hallu_score` and `overall_score` are returned but **must not be displayed**.

`GET /health` returns `{status, index_size}` — use for a backend-status indicator.

Errors to handle: `401` invalid key, `429` rate limited, `422` invalid input or no claims extractable, `503` evidence corpus not loaded.

---

## Critical constraint: requests take ~40 seconds

The NLI model is CPU-bound. A request takes roughly 40 seconds. This is the single most important thing the UI must accommodate.

- Fetch timeout: **90 seconds minimum.** (The existing Streamlit dashboard uses 30s and times out against its own API — do not copy it.)
- The waiting state must be designed, not a bare spinner. Cycle through stage labels on a timer so it reads as progress rather than a hang:
  `Extracting claims…` → `Retrieving evidence…` → `Checking entailment…` → `Scoring claims…`
- Disable the submit button while a request is in flight.
- On timeout, show a clear message and let the user retry without retyping.

---

## Stack

- **React + Vite.** Vite's default dev port is 5173, which `api.py` already allows in its CORS config. Do not change the port.
- **Tailwind CSS.**
- API base URL from `.env` as `VITE_API_URL`, defaulting to `http://localhost:8000`. Never hardcode it.
- Put the API key, base URL, timeout and all error handling in one file: `src/lib/api.js`.

---

## Design direction

Editorial / research publication. Serious and typographic, not a startup SaaS dashboard. Think a journal or a research institute, not a product landing page.

Tokens (define once in Tailwind config, use everywhere):

| Token | Value | Use |
|---|---|---|
| `navy` | `#0B2545` | headers, primary text, buttons |
| `paper` | `#FBFAF8` | page background |
| `ink` | `#1A1A1A` | body text |
| `rule` | `#E2E0DB` | borders, dividers |
| `flag-hallucinated` | `#B23A48` | wrong claims |
| `flag-uncertain` | `#C08A2E` | unverifiable claims |
| `flag-verified` | `#2E6B4F` | supported claims (used sparingly) |

Type: a serif for headings (Lora, Source Serif, or similar), a clean sans for body and UI (Inter or system stack). Generous line height in the results panel — it is a reading surface.

**Devanagari must render correctly.** Include a font with Devanagari coverage (Noto Sans Devanagari) and test with the Hindi claims from `DEMO_CLAIMS.md` early, not at the end.

---

## Layout

Single page, three stacked sections.

### 1. Input
- Heading and one-line description of what the tool does.
- Large textarea, placeholder inviting pasted AI-generated text.
- Language selector: English / हिन्दी (`en` / `hi`). Do not offer Marathi — it has no trained weights.
- Primary button: **Analyse**.
- A row of example chips that fill the textarea on click. Pull these from `DEMO_CLAIMS.md` — a mix of true and false claims, both languages. These exist because the detector is unreliable on arbitrary input; they make the demo dependable.

### 2. Annotated text (the main output)
- Render the user's original text verbatim, preserving line breaks.
- Using `start_char` / `end_char`, wrap flagged claims in a span with a coloured underline or soft background tint:
  - `Hallucinated` → `flag-hallucinated`
  - `Uncertain` → `flag-uncertain`
  - `Verified` → no highlight (clean text is the default reading experience)
- Overlapping or out-of-range spans must not break rendering. Sort spans by `start_char`, skip any that overlap one already applied, and clamp to text length.
- Hovering a highlight shows the claim's verdict in a small tooltip.

### 3. Flagged claims list
- Below the annotated text, list only `Hallucinated` and `Uncertain` claims, in document order.
- Each entry: the claim text, a verdict label chip, and the `note` field if present (it explains insufficient-evidence cases).
- If nothing was flagged, show a plain line: *No claims were flagged in this text.* Do not celebrate it — the detector misses things.

---

## Honest framing (required)

The detector's discrimination on real hallucinations is near chance (see `RESULTS_SUMMARY.md`). The UI must not imply authority it does not have.

- Include a persistent one-line note near the results: *Research prototype. Verdicts are indicative, not authoritative.*
- Use neutral verb phrasing in labels — "Not supported by evidence" rather than "FALSE", "Could not verify" rather than "UNKNOWN".
- No confidence percentages, no large check or cross icons, no celebratory success states.

---

## Out of scope

Do not build: landing page, about page, research/results page, file upload, CSV/JSON export, ablation signal toggles, authentication UI, dark mode, animations beyond the waiting state.

---

## Definition of done

1. `npm run dev` serves on port 5173.
2. With uvicorn running locally, pasting an example claim and clicking Analyse returns a result within 90 seconds without a timeout.
3. Hindi text renders correctly and highlights land on the right characters.
4. Every error case (401, 429, 422, 503, timeout, network failure) shows a readable message rather than a blank screen or a console error.
5. No numeric score appears anywhere in the UI.
