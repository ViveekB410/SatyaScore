// PRD FR-06: export results as CSV or JSON (client-side download).
function download(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

const stamp = () => new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')

export function exportJson(result, submitted) {
  const body = { text: submitted.text, language: submitted.language, ...result }
  download(`satyascore-${stamp()}.json`, JSON.stringify(body, null, 2), 'application/json')
}

const COLUMNS = ['claim_id', 'text', 'verdict', 'hallu_score', 'p_verified', 'p_verified_ci_low',
  'p_verified_ci_high', 'start_char', 'end_char', 'extraction_method', 'note']

const cell = (v) => {
  const s = v === null || v === undefined ? '' : String(v)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function exportCsv(result) {
  const rows = result.claims.map((c) => [
    c.claim_id, c.text, c.verdict, c.hallu_score, c.p_verified,
    c.p_verified_ci95?.[0], c.p_verified_ci95?.[1], c.start_char, c.end_char,
    c.extraction_method, c.note,
  ].map(cell).join(','))
  // BOM so Excel opens Devanagari correctly
  download(`satyascore-${stamp()}.csv`, '﻿' + [COLUMNS.join(','), ...rows].join('\n'), 'text/csv')
}
