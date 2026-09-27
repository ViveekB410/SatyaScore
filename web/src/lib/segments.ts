import type { Claim } from './types'

export interface Segment {
  text: string
  claim: Claim | null
  n: number | null // 1-based claim number, in response order
}

/** Split the submitted text into plain and highlighted runs from the claim
 * offsets. Offsets are clamped, sorted by start, and any claim overlapping one
 * already applied is skipped, so no character is drawn twice and a bad offset
 * can never break rendering. */
export function buildSegments(text: string, claims: Claim[], markSupported: boolean): Segment[] {
  const len = text.length
  const clamp = (v: unknown) => {
    const n = Math.floor(Number(v))
    return Number.isFinite(n) ? Math.max(0, Math.min(n, len)) : 0
  }
  const spans = claims
    .map((claim, i) => ({ claim, n: i + 1, start: clamp(claim.start_char), end: clamp(claim.end_char) }))
    .filter((s) => s.end > s.start && (markSupported || s.claim.verdict !== 'Verified'))
    .sort((a, b) => a.start - b.start)

  const out: Segment[] = []
  let cursor = 0
  for (const s of spans) {
    if (s.start < cursor) continue // overlaps a span already applied
    if (s.start > cursor) out.push({ text: text.slice(cursor, s.start), claim: null, n: null })
    out.push({ text: text.slice(s.start, s.end), claim: s.claim, n: s.n })
    cursor = s.end
  }
  if (cursor < len) out.push({ text: text.slice(cursor), claim: null, n: null })
  return out
}
