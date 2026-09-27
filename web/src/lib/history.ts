// History is stored on the server, per signed-in user (member3_backend/auth.py).
// A check is saved by the server itself when a signed-in user runs /detect, so
// the browser never writes history. This interface is what components use.
import { deleteAnalysis, getAnalysis, listHistory } from './api'
import type { Analysis, DetectResponse, HistorySummary, Language } from './types'

export interface HistoryStore {
  list(params: { q?: string; language?: Language }): Promise<HistorySummary[]>
  get(id: string): Promise<Analysis>
  remove(id: string): Promise<void>
}

export const history: HistoryStore = {
  list: listHistory,
  get: getAnalysis,
  remove: deleteAnalysis,
}

/** The result screen's model of a fresh /detect response. */
export function fromResponse(text: string, language: Language, res: DetectResponse): Analysis {
  return {
    id: res.analysis_id ?? null,
    created_at: new Date().toISOString(),
    language,
    input_text: text,
    claims: res.claims,
    document: res.document ?? null,
    processing_time_ms: res.processing_time_ms,
  }
}
