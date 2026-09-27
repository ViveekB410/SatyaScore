# SatyaScore — Frontend Requirements

Requirements only: **what** the frontend must do, not how it must look. The visual design is
open. Paste this whole file into Claude together with your own design direction.

Every API detail is taken from the running backend (`member3_backend/api.py`).

---

## 1. Purpose

SatyaScore checks AI-generated text for hallucinations. A user gives text (English or Hindi).
The backend splits it into factual claims and scores each one against evidence. The frontend
shows, for the whole text and for every claim, whether it is **supported**, **could not be
verified**, or **not supported**.

It is a **research prototype** and must never overstate certainty (section 7).

---

## 2. Technical constraints

| Item | Requirement |
|---|---|
| Framework | React single-page app. The repo's existing frontend (`frontend/`) uses Vite + Tailwind; keep that stack if building there. |
| API base URL | Configurable via `VITE_API_URL`; default `http://localhost:8000` |
| Auth | Header `X-API-Key: dev-key-satyascore-2026` on `/detect` and `/extract-text` (not on `/health`) |
| Extra header | `ngrok-skip-browser-warning: true` on every request (harmless locally; needed for an ngrok tunnel) |
| Timeout | 90 seconds for `/detect` (CPU inference: roughly 10 s per claim) |
| CORS | The backend allows `http://localhost:5173` by default. Any other origin must be added when starting the backend: `$env:SATYASCORE_CORS_ORIGINS = "http://localhost:5173,https://your-origin"` |
| Storage | History in the browser's `localStorage` only; no accounts, no server-side storage |
| Fonts | Hindi text must render in a Devanagari font (e.g. Noto Sans Devanagari) everywhere it appears |

---

## 3. API contract

### `GET /health`
`200` → `{ "status": "ok", "index_size": 9351 }` (`index_size` = evidence passages loaded).
A network error or any non-200 status means the backend is offline.

### `POST /detect`
Request: `{ "text": "...", "language": "en" }`
- `text`: 1–20,000 characters. `language`: `"en"` or `"hi"`.
- Optional fields (not needed in the normal UI): `threshold`, `active_signals`, `include_timings`.

Response `200`:
```json
{
  "claims": [
    {
      "claim_id": "claim_0",
      "text": "The capital of Japan is Beijing.",
      "hallu_score": 0.19,
      "verdict": "Hallucinated",
      "active_signals": ["semsim", "nli", "kg"],
      "note": null,
      "start_char": 0,
      "end_char": 32,
      "extraction_method": "decomposed_base",
      "p_verified": 0.59,
      "p_verified_ci95": [0.43, 0.74],
      "calibration_n": 37
    }
  ],
  "document": {
    "verdict": "Hallucinated",
    "n_claims": 1,
    "n_verified": 0,
    "n_uncertain": 0,
    "n_hallucinated": 1,
    "supported_fraction": 0.0
  },
  "overall_score": 0.19,
  "processing_time_ms": 9832.4
}
```

| Field | Meaning |
|---|---|
| `verdict` | Exactly `"Verified"`, `"Uncertain"` or `"Hallucinated"` |
| `hallu_score` | 0–1, **higher = more supported**. Tiers: < 0.35 Hallucinated, 0.35–0.65 Uncertain, > 0.65 Verified |
| `start_char`, `end_char` | Character offsets into the exact text submitted. Spans may overlap or be out of order |
| `note` | Explanation such as "insufficient evidence: …"; may be null |
| `p_verified`, `p_verified_ci95`, `calibration_n` | May be **null** |
| `document.verdict` | Whole-text verdict: Hallucinated if ≥ 1/3 of claims are Hallucinated; else Uncertain if any claim is Hallucinated or Uncertain; else Verified — **the headline** |
| `overall_score` | Legacy average; **do not display as the headline** |

### `POST /extract-text`
Multipart form, field `file`, `.txt` or `.pdf`, max 5 MB, with the API-key header.
`200` → `{ "filename": "a.pdf", "text": "...", "truncated": false }`.

### Errors
| Case | Message to show |
|---|---|
| Network error | "Could not reach the backend. Is it running?" |
| Timeout (90 s) | "The request took longer than 90 seconds. Try again, or use a shorter text." |
| 401 | "Invalid API key." |
| 413 | "File too large (max 5 MB)." |
| 415 | "Only .txt and .pdf files are supported." |
| 422 | Show the response `detail` (empty input, no claims found, unreadable file) |
| 429 | "Rate limit reached (100 requests/minute). Wait a moment and try again." |
| 501 | Show the response `detail` (PDF support not installed on the server) |
| 503 | "The backend is still loading its evidence corpus. Retry in a few seconds." |

Every error: a clear message and a **Retry** action. The app must never crash or go blank.

---

## 4. Functional requirements

**FR-1 Connection.** On open, poll `GET /health` (about every 2–3 s). While waiting, show that
the app is connecting. After about 60 s without success, show "Backend offline" with a Retry
action and the command to start it: `uvicorn member3_backend.api:app --port 8000`. Show the
main app once `/health` succeeds.

**FR-2 Backend status.** While using the app, show whether the backend is online and how many
evidence passages it has (`index_size`).

**FR-3 Text input.** A large text area. A language choice: **English** / **हिन्दी**. An
**Analyse** action, disabled while the text is empty or a request is running.

**FR-4 File upload** (PRD FR-06). Accept `.txt` and `.pdf`. `.txt` may be read in the browser;
`.pdf` goes to `/extract-text`. The extracted text fills the text area; the user then analyses.

**FR-5 Examples.** One-click examples that fill the text area and set the language:
- EN: "The capital of France is Paris." · "The capital of Japan is Beijing." · "Mahatma Gandhi
  was a leader of the Indian independence movement." · "Dengue fever is a type of bone cancer."
- HI: "पेरिस फ्रांस की राजधानी है।" · "ताजमहल फ्रांस में स्थित है।"

**FR-6 Waiting state.** While `/detect` runs (10–60 s), show progress, not a frozen screen,
and say it can take up to a minute.

**FR-7 Whole-text result** (PRD: score for the whole text). Show `document.verdict` with its
label, "X of N claims supported (P%)", the three counts (supported / could not verify / not
supported), and the rule: "Hallucinated when a third or more of the claims are hallucinated; fewer
hallucinated claims, or any uncertain claim, make it Uncertain; Verified needs every claim
verified."

**FR-8 Score chart** (PRD FR-06). One bar per claim, in text order; height = `hallu_score`;
coloured by verdict; the 0.35 and 0.65 cut-offs marked; on hover or tap, the claim number,
score and label.

**FR-9 Highlighted text** (PRD FR-06). The submitted text with every claim span highlighted in
place in its verdict colour: **red = not supported, amber = could not verify, green =
supported**. Sort spans by `start_char`, clamp to the text length, and never render a
character twice (skip a span that overlaps one already drawn). Include a legend. Each
highlight shows its label on hover or tap.

**FR-10 Flagged claims.** List only Hallucinated and Uncertain claims, each with its label and
`note` when present. If none: "No claims were flagged in this text."

**FR-11 All claims with scores.** On request (hidden by default), a table: claim | verdict |
support score (2 decimals) | P(Verified) [low, high], with "—" where null, and the footnote in
section 7.

**FR-12 Export** (PRD FR-06).
- JSON: `{ "text", "language", ...the full /detect response }`.
- CSV columns: `claim_id, text, verdict, hallu_score, p_verified, p_verified_ci_low,
  p_verified_ci_high, start_char, end_char, extraction_method, note`. Start with a UTF-8 BOM so
  Excel shows Hindi correctly; quote cells containing commas, quotes or newlines.

**FR-13 History.** Keep the last 20–30 analyses in `localStorage`: text preview, language,
number flagged, relative time, and the worst verdict. Selecting one restores it **without
calling the API**. A Clear action. History must survive a page reload; if storage is
unavailable the app still works.

**FR-14 Disclaimer.** "Research prototype. Verdicts are indicative, not authoritative." must be
visible whenever results are shown.

---

## 5. Verdict labels (exact wording)

| API value | Label shown to users | Colour meaning |
|---|---|---|
| `Hallucinated` | **Not supported by evidence** | red |
| `Uncertain` | **Could not verify** | amber |
| `Verified` | **Supported by evidence** | green |

---

## 6. Non-functional requirements

- **Responsive:** usable from 375 px wide (phone) to desktop, with no horizontal page scroll.
- **Accessible:** text contrast of at least WCAG AA; keyboard-usable controls with visible
  focus; verdicts never shown by colour alone (always with the text label).
- **Bilingual:** all Hindi text (input, highlights, lists, table, history) in a Devanagari font.
- **Robust:** null fields, empty claim lists, overlapping spans and old history entries without
  a `document` field (derive it from the claims: any Hallucinated → Hallucinated, else any
  Uncertain → Uncertain, else Verified) must not break the page.
- **No new backend requirements:** use only the three endpoints above.

---

## 7. Honesty rules (must not be broken)

- Never call `hallu_score` a probability or "confidence". Label it **"Support score"**.
- Show `p_verified` only as **"P(Verified)"** with its interval, with this footnote under the
  table: *"Support score: 0 = contradicted by evidence, 1 = supported. Below 0.35 is flagged as
  not supported, above 0.65 as supported. The score itself is not a probability; P(Verified) is
  the share of training claims with a similar score that were Verified, with a 95% interval.
  Wide or overlapping intervals mean the score is weak evidence either way."*
- The headline is `document.verdict`, never the average `overall_score`.
- "No claims were flagged" must not be presented as "this text is true" (no celebration).

---

## 8. Acceptance tests

- [ ] With the backend stopped: connecting state, then "Backend offline" with Retry.
- [ ] "The capital of France is Paris. The capital of Japan is Beijing." → whole text: Not
      supported by evidence, 1 of 2 claims supported; Beijing sentence red, Paris sentence green.
- [ ] A Hindi example renders in a Devanagari font everywhere.
- [ ] Each error in section 3 shows its message and Retry.
- [ ] A `.txt` upload and a `.pdf` upload each fill the text area.
- [ ] CSV opens in Excel with Hindi intact; JSON contains the full response.
- [ ] History survives a reload and restores a result without a network request.
- [ ] A claim with null `p_verified` shows "—".
- [ ] At 375 px wide: everything usable, no horizontal scroll.
