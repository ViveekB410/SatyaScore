# SatyaScore Frontend

React + Vite + Tailwind single-page dashboard for the SatyaScore `/detect` API.
Paste AI-generated text → get it back with unsupported claims highlighted in place,
plus a list of flagged claims. Editorial/research styling; English + Hindi.

## Run

1. Start the backend (from the repo root):
   ```
   uvicorn member3_backend.api:app --port 8000
   ```
2. Install + run the frontend:
   ```
   cd frontend
   npm install
   npm run dev
   ```
   Serves on **http://localhost:5173** — the port `api.py`'s CORS config already allows.
   Don't change it.

## Config
- `VITE_API_URL` in `.env` (default `http://localhost:8000`). Never hardcoded elsewhere.
- Dev API key `dev-key-satyascore-2026` lives in `src/lib/api.js` with all other API config.

## Notes
- Requests are CPU-bound (~10–40s per call); the fetch timeout is **90s** with a staged
  waiting animation. Do not lower it.
- Curated, dependable example claims (from `DEMO_CLAIMS.md`) are in `src/lib/verdicts.js`.
- **No numeric scores are shown** anywhere — deliberate product decision.
- Devanagari renders via Noto Sans Devanagari (loaded in `index.html`).
- **Colab tunnel:** set `VITE_API_URL` to the tunnel URL **and** add that origin to the
  backend CORS allow-list (BACKEND_IMPROVEMENTS.md Task 5 — not yet implemented).
