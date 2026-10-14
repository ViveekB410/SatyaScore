// All network access lives here. Components never call fetch directly.
//
// Security: the browser holds no API key. Signed-in users are identified by an
// HttpOnly session cookie that page scripts cannot read; every request sends it
// with credentials: 'include'. The server checks the Origin of state-changing
// requests (CSRF) and throttles sign-in attempts.
import type {
  Analysis,
  DetectResponse,
  Health,
  HistorySummary,
  Language,
  User,
} from './types'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// CPU inference can take up to ~60 s; the Version 2 cross-check with a local LLM takes ~5-10 s per claim
const DETECT_TIMEOUT_MS = 300_000
const DEFAULT_TIMEOUT_MS = 20_000
const UPLOAD_TIMEOUT_MS = 60_000
export const MAX_CHARS = 20_000 // api.py DetectRequest.text max_length
const MAX_FILE_BYTES = 5 * 1024 * 1024
// Lets a free ngrok tunnel skip its interstitial; harmless locally.
const BASE_HEADERS: Record<string, string> = { 'ngrok-skip-browser-warning': 'true' }

export type ApiErrorKind = 'network' | 'timeout' | 'http' | 'input'

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | null

  constructor(kind: ApiErrorKind, status: number | null, message: string) {
    super(message)
    this.kind = kind
    this.status = status
  }
}

const HTTP_MESSAGES: Record<number, string> = {
  401: 'Your session has ended. Sign in again.',
  403: 'The server refused this request (origin not allowed).',
  404: 'Not found.',
  413: 'That file is too large. The limit is 5 MB.',
  415: 'Only .txt and .pdf files can be uploaded.',
  422: 'No checkable claims could be extracted from this text, or the input was not valid.',
  429: 'Too many requests. Wait a moment, then try again.',
  501: 'PDF reading is not installed on the server. Paste the text instead.',
  503: 'The server is still loading its evidence corpus. Try again in a few seconds.',
}

async function errorFrom(res: Response): Promise<ApiError> {
  let detail: string | null = null
  try {
    const body: unknown = await res.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const d = (body as { detail: unknown }).detail
      if (typeof d === 'string') detail = d
    }
  } catch {
    // no JSON body
  }
  // The server's own message is specific (validation, throttling, sign-in); prefer it.
  const message = detail ?? HTTP_MESSAGES[res.status] ?? `The server returned an error (HTTP ${res.status}).`
  return new ApiError('http', res.status, message)
}

async function request(path: string, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(`${API_URL}${path}`, {
      ...init,
      credentials: 'include',
      headers: { ...BASE_HEADERS, ...(init.headers ?? {}) },
      signal: controller.signal,
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError(
        'timeout',
        null,
        `No answer after ${timeoutMs / 1000} seconds. The server may be busy; try again or check a shorter text.`,
      )
    }
    throw new ApiError('network', null, `Could not reach the analysis server at ${API_URL}. Check that it is running.`)
  } finally {
    clearTimeout(timer)
  }
}

async function json<T>(path: string, init?: RequestInit, timeoutMs?: number): Promise<T> {
  const res = await request(path, init, timeoutMs)
  if (!res.ok) throw await errorFrom(res)
  return (await res.json()) as T
}

const postJson = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

// ---- server status -----------------------------------------------------------

/** Null means offline (network error or non-200). */
export async function getHealth(): Promise<Health | null> {
  try {
    const res = await request('/health', {}, 10_000)
    return res.ok ? ((await res.json()) as Health) : null
  } catch {
    return null
  }
}

// ---- analysis ------------------------------------------------------------------

export async function detect(text: string, language: Language): Promise<DetectResponse> {
  if (!text.trim()) throw new ApiError('input', null, 'Paste some text to check first.')
  if (text.length > MAX_CHARS) {
    throw new ApiError(
      'input',
      null,
      `This text is ${text.length.toLocaleString()} characters; the limit is ${MAX_CHARS.toLocaleString()}. Shorten it and try again.`,
    )
  }
  return json<DetectResponse>('/detect', postJson({ text, language }), DETECT_TIMEOUT_MS)
}

/** PRD FR-06 upload: .txt is read in the browser, .pdf by the server's /extract-text. */
export async function extractText(file: File): Promise<{ text: string; truncated: boolean }> {
  const name = file.name.toLowerCase()
  if (file.size > MAX_FILE_BYTES) throw new ApiError('input', 413, HTTP_MESSAGES[413])
  if (name.endsWith('.txt')) {
    const text = await file.text()
    return { text: text.slice(0, MAX_CHARS), truncated: text.length > MAX_CHARS }
  }
  if (!name.endsWith('.pdf')) throw new ApiError('input', 415, HTTP_MESSAGES[415])
  const form = new FormData()
  form.append('file', file)
  const body = await json<{ text: string; truncated?: boolean }>(
    '/extract-text',
    { method: 'POST', body: form },
    UPLOAD_TIMEOUT_MS,
  )
  return { text: body.text, truncated: Boolean(body.truncated) }
}

// ---- accounts ----------------------------------------------------------------

export async function getMe(): Promise<User | null> {
  return (await json<{ user: User | null }>('/auth/me')).user
}

export async function signIn(email: string, password: string): Promise<User> {
  return (await json<{ user: User }>('/auth/login', postJson({ email, password }))).user
}

export async function signUp(name: string, email: string, password: string): Promise<User> {
  return (await json<{ user: User }>('/auth/register', postJson({ name, email, password }))).user
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<User> {
  return (await json<{ user: User }>('/auth/change-password',
    postJson({ current_password: currentPassword, new_password: newPassword }))).user
}

/** Ask for a 6-digit reset code by email. The answer is the same whether or not the account exists. */
export async function forgotPassword(email: string): Promise<string> {
  return (await json<{ message: string }>('/auth/forgot-password', postJson({ email }))).message
}

export async function resetPassword(email: string, code: string, newPassword: string): Promise<User> {
  return (await json<{ user: User }>('/auth/reset-password',
    postJson({ email, code, new_password: newPassword }))).user
}

export async function signOut(): Promise<void> {
  const res = await request('/auth/logout', { method: 'POST' })
  if (!res.ok && res.status !== 401) throw await errorFrom(res)
}

// ---- history (server-side, per user) ----------------------------------------------

export async function listHistory(params: { q?: string; language?: Language }): Promise<HistorySummary[]> {
  const qs = new URLSearchParams()
  if (params.q?.trim()) qs.set('q', params.q.trim())
  if (params.language) qs.set('language', params.language)
  const suffix = qs.toString() ? `?${qs}` : ''
  return (await json<{ entries: HistorySummary[] }>(`/history${suffix}`)).entries
}

export async function getAnalysis(id: string): Promise<Analysis> {
  return json<Analysis>(`/history/${encodeURIComponent(id)}`)
}

export async function deleteAnalysis(id: string): Promise<void> {
  const res = await request(`/history/${encodeURIComponent(id)}`, { method: 'DELETE' })
  if (!res.ok) throw await errorFrom(res)
}
