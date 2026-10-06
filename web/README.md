# SatyaScore — web app (`web/`)

The SatyaScore web app: check AI-generated English or Hindi text claim by claim, with
accounts and per-user history. The older `frontend/` is kept as a fallback. Both use port
5173 (the origin `api.py` allows in CORS), so run one at a time.

```powershell
# 1. backend (from the repo root)
python -m uvicorn member3_backend.api:app --port 8000
# 2. web app
cd web
npm install
npm run dev        # http://localhost:5173
npm run build      # type-check + production build
```

`VITE_API_URL` sets the backend address (default `http://localhost:8000`).

## Accounts and security

Sign-up is open; signing in is optional. Anyone can check text; signed-in users get their
checks saved to their own history on the server. Implemented in `member3_backend/auth.py`
(tests: `tests/test_auth.py`).

| Concern | How it is handled |
|---|---|
| Passwords | scrypt with a per-user random salt; minimum 10 characters; never stored in plain text |
| Sessions | random 256-bit token in an **HttpOnly, SameSite=Lax** cookie (page scripts cannot read it); only its SHA-256 is stored; expires after 7 days; sign-out deletes it on the server |
| CSRF | state-changing requests carrying the cookie must come from an allowed Origin (the CORS list) |
| Brute force | failed sign-ins throttled per IP+email (5 / 15 min) and per IP; sign-ups per IP |
| Account enumeration | sign-in gives one message for unknown email and wrong password, at the same cost |
| API key | no longer shipped in the browser; kept only for scripts and tests |
| Rate limits | 100 requests/min per signed-in user; 20/min per IP when anonymous |
| History privacy | every query is scoped to the signed-in user; another user's entry returns 404 |
| Headers | `nosniff`, `X-Frame-Options: DENY`, `no-referrer`; auth and history responses `no-store` |

Data is stored in SQLite at `instance/satyascore.db` (git-ignored; set `SATYASCORE_DB` to
move it). **Behind HTTPS** (a real deployment) set `SATYASCORE_COOKIE_SECURE=true`; for a
frontend on a different site also set `SATYASCORE_COOKIE_SAMESITE=none` and add its origin to
`SATYASCORE_CORS_ORIGINS`.

Passwords can be changed when signed in, and reset with a one-time code issued by the administrator
(`python -m member3_backend.auth reset-code <email>`; see the main README).
Not included (known limits): email verification, emailed reset links, and throttling that
survives a restart or spans several server processes.

## Verdicts

Shown by name: **Verified**, **Uncertain**, **Hallucinated** (thresholds 0.35 / 0.65, PRD
FR-04). The whole text is **Hallucinated** when a third or more of its claims are hallucinated;
fewer hallucinated claims, or any uncertain claim, make it **Uncertain**; **Verified** needs every
claim verified. Scores are hidden by default behind
**Show scores**.

## Changes from `FRONTEND_V2_SPEC.md`

| Spec | Built | Why |
|---|---|---|
| No numeric score | Verdicts by default; **Show scores** reveals the HalluScore bar and calibrated P(Verified) | PRD FR-04 / FR-06; the guide asked for claim scores |
| Summary line only | **Whole-text verdict** above the summary line | The guide asked for a whole-text result |
| Supported claims unmarked | **Mark verified claims** switch, on by default | PRD FR-06 red / amber / green |
| No upload, no export | **Upload .txt / .pdf**, **Export CSV / JSON** | PRD FR-06 |
| Mock mode | Removed | The app always talks to the real backend |
| `/login` stub, history in the browser | Real sign-in / sign-up, history on the server per user | Requested |
| "Not supported / Unverifiable / Supported" | **Hallucinated / Uncertain / Verified** | Requested; matches the PRD and the API |
