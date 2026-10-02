// PRD FR-06: export a result as CSV or JSON (client-side download).
import { overallScore, summarise } from './verdicts'
import type { Analysis } from './types'

function download(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const stamp = () => new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')

export function exportJson(e: Analysis) {
  const body = {
    text: e.input_text,
    language: e.language,
    created_at: e.created_at,
    document: summarise(e.claims, e.document),
    overall_score: overallScore(e.claims),
    claims: e.claims,
    processing_time_ms: e.processing_time_ms ?? null,
  }
  download(`satyascore-${stamp()}.json`, JSON.stringify(body, null, 2), 'application/json')
}

const COLUMNS = [
  'claim_id', 'text', 'verdict', 'hallu_score', 'p_verified', 'p_verified_ci_low',
  'p_verified_ci_high', 'start_char', 'end_char', 'extraction_method', 'note', 'sources',
  'evidence_excerpt', 'wikidata_fact',
]

const cell = (v: unknown) => {
  const s = v === null || v === undefined ? '' : String(v)
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function exportCsv(e: Analysis) {
  const rows = e.claims.map((c) =>
    [
      c.claim_id, c.text, c.verdict, c.hallu_score, c.p_verified,
      c.p_verified_ci95?.[0], c.p_verified_ci95?.[1], c.start_char, c.end_char,
      c.extraction_method, c.note,
      (c.sources ?? []).map((s) => `${s.title} (${s.role}) ${s.url}`).join(' | '),
      c.evidence_excerpt,
      c.kg_fact ? `${c.kg_fact.subject} · ${c.kg_fact.property}: ${c.kg_fact.values.join(' / ')} (${c.kg_fact.status})` : '',
    ].map(cell).join(','),
  )
  // BOM so Excel opens Devanagari correctly
  download(`satyascore-${stamp()}.csv`, '﻿' + [COLUMNS.join(','), ...rows].join('\r\n'), 'text/csv')
}
