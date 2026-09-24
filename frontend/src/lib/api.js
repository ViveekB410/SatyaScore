// All API access, config, and error handling live here (per the spec).
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_KEY = 'dev-key-satyascore-2026'
const TIMEOUT_MS = 90_000 // requests are CPU-bound (~10-40s); 90s headroom, never 30s

export class ApiError extends Error {
  constructor(kind, message) {
    super(message)
    this.kind = kind // 'timeout' | 'network' | 'http_401' | 'http_429' | 'http_422' | 'http_503' | ...
  }
}

const HTTP_MESSAGES = {
  401: 'Invalid API key.',
  429: 'Rate limit reached (100 requests/minute). Wait a moment and try again.',
  422: 'Could not process this input — it may be empty or contain no extractable claims.',
  503: 'The backend is still loading its evidence corpus. Give it a few seconds and retry.',
}

async function errorFromResponse(res) {
  let detail = HTTP_MESSAGES[res.status]
  if (!detail) {
    try {
      const body = await res.json()
      detail = body?.detail ? String(body.detail) : `Request failed (HTTP ${res.status}).`
    } catch {
      detail = `Request failed (HTTP ${res.status}).`
    }
  }
  return new ApiError(`http_${res.status}`, detail)
}

// ngrok-skip-browser-warning lets a free-tier ngrok tunnel skip its interstitial.
const BASE_HEADERS = { 'ngrok-skip-browser-warning': 'true' }

export async function detect(text, language) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  let res
  try {
    res = await fetch(`${API_URL}/detect`, {
      method: 'POST',
      headers: { ...BASE_HEADERS, 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
      body: JSON.stringify({ text, language }),
      signal: controller.signal,
    })
  } catch (e) {
    clearTimeout(timer)
    if (e.name === 'AbortError') {
      throw new ApiError('timeout', 'The request took longer than 90 seconds. The model is CPU-bound — try again, or use a shorter text.')
    }
    throw new ApiError('network', `Could not reach the backend at ${API_URL}. Is the API running?`)
  }
  clearTimeout(timer)
  if (!res.ok) throw await errorFromResponse(res)
  return res.json()
}

// FR-06 file upload: .txt is read in the browser; .pdf is sent to the backend.
export async function fileToText(file) {
  const name = file.name.toLowerCase()
  if (name.endsWith('.txt')) return file.text()
  if (!name.endsWith('.pdf')) throw new ApiError('http_415', 'Only .txt and .pdf files are supported.')
  const form = new FormData()
  form.append('file', file)
  let res
  try {
    res = await fetch(`${API_URL}/extract-text`, {
      method: 'POST',
      headers: { ...BASE_HEADERS, 'X-API-Key': API_KEY },
      body: form,
    })
  } catch {
    throw new ApiError('network', `Could not reach the backend at ${API_URL}. Is the API running?`)
  }
  if (!res.ok) throw await errorFromResponse(res)
  return (await res.json()).text
}

export async function health() {
  try {
    const res = await fetch(`${API_URL}/health`, { headers: BASE_HEADERS })
    if (!res.ok) return { ok: false }
    const body = await res.json()
    return { ok: true, ...body }
  } catch {
    return { ok: false }
  }
}
