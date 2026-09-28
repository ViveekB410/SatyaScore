// Shapes of the SatyaScore API (member3_backend/api.py, member3_backend/auth.py).

export type Verdict = 'Verified' | 'Uncertain' | 'Hallucinated'
export type Language = 'en' | 'hi'

export interface Claim {
  claim_id: string
  text: string
  verdict: Verdict
  note: string | null
  start_char: number
  end_char: number
  hallu_score: number
  active_signals: string[]
  extraction_method: string
  // Calibrated P(Verified); null when the claim had no evidence.
  p_verified?: number | null
  p_verified_ci95?: [number, number] | null
  calibration_n?: number | null
  // Where the claim was checked; the article that decided the verdict comes first.
  sources?: SourceRef[]
}

export interface SourceRef {
  title: string
  language: string // "en" | "hi" | "mul" (Wikidata)
  url: string
  role: 'supports' | 'contradicts' | 'knowledge graph' | 'fact-check' | 'checked'
  rating?: string | null // fact-check only: the publisher's own rating, e.g. "False"
}

/** What kind of reference this is, for the "(…)" after its name. */
export function sourceKind(s: SourceRef): string {
  if (s.role === 'fact-check') return s.rating ? `fact-check: ${s.rating}` : 'fact-check'
  if (s.role === 'knowledge graph' || s.language === 'mul') return 'knowledge graph'
  return 'Wikipedia'
}

// Whole-text verdict: Hallucinated when >= 1/3 of claims are Hallucinated.
export interface DocumentSummary {
  verdict: Verdict
  n_claims: number
  n_verified: number
  n_uncertain: number
  n_hallucinated: number
  supported_fraction: number
}

export interface DetectResponse {
  claims: Claim[]
  document?: DocumentSummary | null
  overall_score: number // legacy average; never displayed
  processing_time_ms: number
  analysis_id?: string // present when signed in: the result was saved to history
}

export interface Health {
  status: string
  index_size: number
}

export interface User {
  id: string
  email: string
  name: string
  created_at: string
}

/** One checked passage, as shown on the results screen. id is null when the
 * result was not saved (anonymous use). */
export interface Analysis {
  id: string | null
  created_at: string
  language: Language
  input_text: string
  claims: Claim[]
  document?: DocumentSummary | null
  processing_time_ms?: number | null
}

/** A history row (the server sends a preview, not the whole text). */
export interface HistorySummary {
  id: string
  created_at: string
  language: Language
  preview: string
  total_claims: number
  flagged_count: number
}
