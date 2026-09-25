# SatyaScore — Frontend Spec for Lovable

A complete brief for building the SatyaScore dashboard in Lovable (React + Tailwind). Every API
field below is taken from the running backend (`member3_backend/api.py`). Section 8 is a prompt
you can paste into Lovable directly.

---

## 1. What the app does

A user pastes AI-generated text (English or Hindi), or uploads a `.txt` / `.pdf`. The backend
splits it into factual claims and checks each against evidence. The app shows:

- a **whole-text verdict** (the text is judged by its weakest claim);
- the original text with each claim **highlighted in place**: red = not supported, amber =
  could not verify, green = supported;
- a list of **flagged claims**;
- a **bar chart** of each claim's score;
- a **table** of every claim with its score and **P(Verified) with a 95% interval**;
- **export** as CSV or JSON;
- a **history** of past analyses (stored in the browser).

It is a **research prototype**: the UI must say so, and must never overstate certainty
(section 6).

---

## 2. Connecting to the backend

| Setting | Value |
|---|---|
| Base URL | `http://localhost:8000` locally; make it configurable (`VITE_API_URL`) |
| Auth header | `X-API-Key: dev-key-satyascore-2026` on `/detect` and `/extract-text` (not `/health`) |
| Timeout | **90 seconds** for `/detect` (CPU inference is slow: ~10 s per claim) |

**CORS — required for Lovable.** The backend only accepts browser requests from origins it
knows. Before using a Lovable preview or published URL, start the backend with that origin
added (PowerShell):

```powershell
$env:SATYASCORE_CORS_ORIGINS = "http://localhost:5173,https://YOUR-APP.lovable.app"
python -m uvicorn member3_backend.api:app --port 8000
```

Use the exact origin shown in the browser address bar (scheme + host, no trailing slash).

**Reaching the backend from a hosted page.** A Lovable page runs in your browser. Chrome lets it
call `http://localhost:8000` on the same computer. To let **other people** use it, expose the
backend over HTTPS with a tunnel (e.g. ngrok), set `VITE_API_URL` to the tunnel URL, add the
Lovable origin to `SATYASCORE_CORS_ORIGINS`, and send the header
`ngrok-skip-browser-warning: true` on every request.

---

## 3. API contract (exact)

### `GET /health`
Response `200`: `{ "status": "ok", "index_size": 9351 }` — `index_size` = evidence passages loaded.
Any network error or non-200 means the backend is offline.

### `POST /detect`
Request body:
```json
{ "text": "The capital of Japan is Beijing.", "language": "en" }
```
- `text`: string, 1–20,000 characters. `language`: `"en"` or `"hi"`.
- Optional (leave out for the normal UI): `threshold` (0–1), `active_signals`
  (`["semsim","nli","kg"]` subset, for ablation), `include_timings` (bool).

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

Field meanings:
- `verdict`: exactly `"Verified"`, `"Uncertain"` or `"Hallucinated"`.
- `hallu_score`: 0–1, **higher = more supported** (0 = contradicted by evidence, 1 = supported).
  Tiers: < 0.35 Hallucinated, 0.35–0.65 Uncertain, > 0.65 Verified.
- `start_char` / `end_char`: character offsets into the **exact text the user submitted**. Use
  them for in-place highlighting. Some spans cover the whole sentence; spans may overlap or be
  out of order — sort by `start_char` and never render the same character twice.
- `note`: e.g. `"insufficient evidence: no sufficiently relevant passage found in the corpus"`.
  Show it under the claim when not null.
- `p_verified`, `p_verified_ci95`, `calibration_n`: may be **null** (no evidence for that claim) —
  show "—".
- `document.verdict`: the whole-text verdict (worst claim decides). **Use this, not
  `overall_score`**, as the headline. `overall_score` is kept only for older clients.

### `POST /extract-text` (file upload)
Multipart form, field name `file`, `.txt` or `.pdf`, max 5 MB. Response `200`:
`{ "filename": "a.pdf", "text": "…", "truncated": false }`. Put `text` into the text box; the
user then presses Analyse. (`.txt` can also be read directly in the browser.)

### Errors (show a clear message and a Retry button; never crash)
| Code | Meaning | Message to show |
|---|---|---|
| network error / timeout | backend unreachable or slow | "Could not reach the backend. Is it running?" / "Took longer than 90 s — try a shorter text." |
| 401 | wrong API key | "Invalid API key." |
| 413 | file too large | "File too large (max 5 MB)." |
| 415 | wrong file type | "Only .txt and .pdf files are supported." |
| 422 | empty input, no claims found, or unreadable file | use the response `detail` |
| 429 | rate limit (100 requests/min) | "Too many requests — wait a moment." |
| 501 | PDF support not installed on the server | use the response `detail` |
| 503 | evidence corpus still loading | "The backend is still loading. Retry in a few seconds." |

---

## 4. Screens and components

1. **Loading gate** (on open): poll `GET /health` every ~3 s. Show "Connecting to the backend…"
   with a small animation; after ~30 s without success show "Backend offline" and a Retry
   button. Show the main app once `/health` returns 200.
2. **Header**: title "SatyaScore", one-line description: "Paste AI-generated text. Each factual
   claim is checked against evidence and flagged in place where it isn't supported."
3. **Input**: large textarea (use the Devanagari font when Hindi is selected); language toggle
   **English | हिन्दी**; **Analyse** button (disabled while empty or running); **Upload .txt /
   .pdf** button.
4. **Example chips** (fill the textarea and set the language):
   - EN: "The capital of France is Paris." · "The capital of Japan is Beijing." ·
     "Mahatma Gandhi was a leader of the Indian independence movement." ·
     "Dengue fever is a type of bone cancer."
   - HI: "पेरिस फ्रांस की राजधानी है।" · "ताजमहल फ्रांस में स्थित है।"
5. **Waiting state** while `/detect` runs: a calm message ("Checking each claim against evidence…
   this can take up to a minute").
6. **Results** (in this order):
   1. **Whole-text card**: the document verdict as a coloured label, "X of N claims supported
      (P%)", counts of supported / could not verify / not supported, and the line "The text is
      judged by its weakest claim: one unsupported claim marks the whole text."
   2. **Score chart**: one bar per claim (height = `hallu_score`), coloured by verdict, dashed
      lines at 0.35 and 0.65, tooltip with the claim number, score and label. Buttons **Export
      CSV** and **Export JSON** beside the heading.
   3. **Annotated text**: the submitted text with each claim span highlighted (light background
      tint + coloured underline), and a legend: red "Not supported by evidence", amber "Could not
      verify", green "Supported by evidence".
   4. **Flagged claims**: only Hallucinated and Uncertain claims, each with its label chip and
      `note` if present. If none: "No claims were flagged in this text." (do not celebrate —
      the detector misses things).
   5. **"Show all claims with scores"** toggle → table: claim | verdict | support score (2 dp) |
      P(Verified) [95% CI], with the footnote in section 6.
7. **History sidebar**: past analyses saved in `localStorage` (text preview, language, number
   flagged, relative time, a dot in the worst verdict's colour); click to restore; "Clear" button.
   Keep the last ~20.
8. **Footer**: "● Backend online · N evidence passages" (green dot) or "Backend offline" (red).
   A line: "Research prototype. Verdicts are indicative, not authoritative."

**Export formats.**
- JSON: `{ "text", "language", ...the full /detect response }`.
- CSV columns: `claim_id, text, verdict, hallu_score, p_verified, p_verified_ci_low,
  p_verified_ci_high, start_char, end_char, extraction_method, note`. Start the file with a UTF-8
  BOM (`﻿`) so Excel shows Hindi correctly. Quote cells containing commas, quotes or newlines.

---

## 5. Design

| Token | Value | Use |
|---|---|---|
| navy | `#0B2545` | headings, primary buttons, selected toggle |
| paper | `#FBFAF8` | page background |
| ink | `#1A1A1A` | body text |
| rule | `#E2E0DB` | borders, dividers |
| flag-hallucinated | `#B23A48` | Not supported |
| flag-uncertain | `#C08A2E` | Could not verify |
| flag-verified | `#2E6B4F` | Supported |

Fonts (Google Fonts): **Lora** (headings, claim text), **Inter** (UI), **Noto Sans Devanagari**
(all Hindi text). Calm, editorial look: white cards with thin `rule` borders, generous spacing,
no big tick/cross icons, no confetti. Must work on a phone (single column, 16 px side margin).

Verdict labels shown to users — always these exact words:
- Hallucinated → **"Not supported by evidence"**
- Uncertain → **"Could not verify"**
- Verified → **"Supported by evidence"**

---

## 6. Honesty rules (do not break these)

- Never call `hallu_score` a probability or "confidence". Label it **"Support score"**.
- Show `p_verified` only as **"P(Verified)"** with its interval, and include this footnote under
  the table: *"Support score: 0 = contradicted by evidence, 1 = supported. The score itself is not
  a probability; P(Verified) is the share of training claims with a similar score that were
  Verified, with a 95% interval. Wide or overlapping intervals mean the score is weak evidence
  either way."*
- Headline = `document.verdict`, never the average `overall_score`.
- Keep the "Research prototype" line visible on every result.
- "No claims were flagged" must not read as "this text is true".

---

## 7. Acceptance checklist

- [ ] App waits for `/health`, shows offline + Retry when the backend is down.
- [ ] "The capital of France is Paris. The capital of Japan is Beijing." → whole-text card says
      Not supported, 1 of 2 claims supported; only the Beijing sentence is red; Paris is green.
- [ ] Hindi example renders in Noto Sans Devanagari everywhere (textarea, highlights, table).
- [ ] Every error code in section 3 shows its message and a Retry button.
- [ ] Upload: a `.txt` fills the box; a `.pdf` goes through `/extract-text` and fills the box.
- [ ] CSV opens in Excel with Hindi intact; JSON contains the full response.
- [ ] History survives a page reload and restores a past result without calling the API.
- [ ] Null `p_verified` shows "—", not an error.
- [ ] Works at 375 px wide without horizontal scrolling.

---

## 8. Prompt to paste into Lovable

> Build a React + Tailwind single-page app called **SatyaScore**, a research-prototype dashboard
> that checks AI-generated text for hallucinations by calling an existing REST API. Follow this
> spec exactly.
>
> **API** (base URL from env `VITE_API_URL`, default `http://localhost:8000`):
> - `GET /health` → `{status, index_size}`. Poll every 3 s on load; show a "Connecting to the
>   backend…" screen until it returns 200; after 30 s show "Backend offline" with Retry.
> - `POST /detect` with headers `Content-Type: application/json`,
>   `X-API-Key: dev-key-satyascore-2026`, `ngrok-skip-browser-warning: true`; body
>   `{text, language}` where language is `"en"` or `"hi"`; 90-second timeout. Response:
>   `claims[]` (`claim_id, text, hallu_score, verdict, active_signals, note, start_char,
>   end_char, extraction_method, p_verified, p_verified_ci95, calibration_n` — the last three can
>   be null), `document` (`verdict, n_claims, n_verified, n_uncertain, n_hallucinated,
>   supported_fraction`), `overall_score`, `processing_time_ms`. `verdict` is one of
>   Verified / Uncertain / Hallucinated.
> - `POST /extract-text` multipart field `file` (.txt/.pdf, ≤5 MB) with the same API-key header →
>   `{text}`; put it into the textarea.
> - Handle network errors, timeouts and HTTP 401/413/415/422/429/501/503 with clear messages and a
>   Retry button; show the response `detail` for 422/501.
>
> **UI**: header with title and description; textarea; English/हिन्दी toggle (use Noto Sans
> Devanagari for Hindi); Analyse button; Upload .txt/.pdf button; example chips
> (EN: "The capital of France is Paris.", "The capital of Japan is Beijing.", "Mahatma Gandhi was a
> leader of the Indian independence movement.", "Dengue fever is a type of bone cancer."; HI:
> "पेरिस फ्रांस की राजधानी है।", "ताजमहल फ्रांस में स्थित है।"); a calm waiting message while
> analysing. Results, in order: (1) whole-text card showing `document.verdict` as a coloured
> label, "X of N claims supported (P%)", the three counts, and "The text is judged by its weakest
> claim: one unsupported claim marks the whole text."; (2) a bar chart of `hallu_score` per claim
> coloured by verdict with dashed lines at 0.35 and 0.65, plus Export CSV and Export JSON buttons;
> (3) the submitted text with each claim span (`start_char`–`end_char`, sorted, never rendering a
> character twice) highlighted with a light tint and coloured underline, plus a legend; (4) a list
> of Hallucinated and Uncertain claims with their label and `note`, or "No claims were flagged in
> this text."; (5) a toggle "Show all claims with scores" revealing a table: claim | verdict |
> support score (2 decimals) | P(Verified) [low, high] ("—" when null), with this footnote:
> "Support score: 0 = contradicted by evidence, 1 = supported. The score itself is not a
> probability; P(Verified) is the share of training claims with a similar score that were
> Verified, with a 95% interval. Wide or overlapping intervals mean the score is weak evidence
> either way." A left sidebar keeps the last 20 analyses in localStorage (preview, language,
> flagged count, relative time, dot in the worst verdict colour; click to restore; Clear button).
> Footer: "● Backend online · N evidence passages" or "Backend offline", and "Research prototype.
> Verdicts are indicative, not authoritative."
>
> **Labels** (exact): Hallucinated = "Not supported by evidence", Uncertain = "Could not verify",
> Verified = "Supported by evidence". Never call `hallu_score` a probability; label it "Support
> score". The headline is `document.verdict`, never `overall_score`.
>
> **Exports**: JSON = `{text, language, ...response}`; CSV columns `claim_id, text, verdict,
> hallu_score, p_verified, p_verified_ci_low, p_verified_ci_high, start_char, end_char,
> extraction_method, note`, UTF-8 with BOM, properly quoted.
>
> **Design**: colours navy #0B2545, paper #FBFAF8 (background), ink #1A1A1A, rule #E2E0DB,
> not-supported #B23A48, could-not-verify #C08A2E, supported #2E6B4F. Fonts: Lora (headings and
> claim text), Inter (UI), Noto Sans Devanagari (Hindi). Calm editorial style, white cards with
> thin borders, no big tick/cross icons, responsive down to 375 px with no horizontal scroll.
