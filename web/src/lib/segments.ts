import type { Claim } from './types'

export interface Segment {
  text: string
  claim: Claim | null
  n: number | null // 1-based claim number, in response order
  // The wrong words inside this claim's run, as [start, end] code-point offsets into `text`.
  errors: [number, number][]
}

/** Split the submitted text into plain and highlighted runs from the claim
 * offsets. Offsets are clamped, sorted by start, and any claim overlapping one
 * already applied is skipped, so no character is drawn twice and a bad offset
 * can never break rendering.
 *
 * The server's offsets count Unicode characters (Python str indices). A JS string
 * counts UTF-16 units, where an emoji such as 🩸 is 2, so slicing `text` directly
 * shifted every highlight after an emoji by one. We slice an array of code points. */
export function buildSegments(text: string, claims: Claim[], markSupported: boolean): Segment[] {
  const chars = Array.from(text) // one element per Unicode code point, like Python
  const len = chars.length
  const slice = (a: number, b?: number) => chars.slice(a, b).join('')
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
    if (s.start > cursor) out.push({ text: slice(cursor, s.start), claim: null, n: null, errors: [] })
    // error spans narrower than the claim only (a whole-claim span adds nothing to the claim's own mark)
    const errors = (s.claim.error_spans ?? [])
      .map(([a, b]) => [Math.max(clamp(a), s.start) - s.start, Math.min(clamp(b), s.end) - s.start] as [number, number])
      .filter(([a, b]) => b > a && b - a < s.end - s.start)
      .sort((x, y) => x[0] - y[0])
    out.push({ text: slice(s.start, s.end), claim: s.claim, n: s.n, errors })
    cursor = s.end
  }
  if (cursor < len) out.push({ text: slice(cursor), claim: null, n: null, errors: [] })
  return out
}

/** A claim run split into plain and wrong-word pieces (overlapping error spans are skipped). */
export function splitErrors(text: string, errors: [number, number][]): { text: string; wrong: boolean }[] {
  const chars = Array.from(text)
  const out: { text: string; wrong: boolean }[] = []
  let cursor = 0
  for (const [a, b] of errors) {
    if (a < cursor) continue
    if (a > cursor) out.push({ text: chars.slice(cursor, a).join(''), wrong: false })
    out.push({ text: chars.slice(a, b).join(''), wrong: true })
    cursor = b
  }
  if (cursor < chars.length) out.push({ text: chars.slice(cursor).join(''), wrong: false })
  return out
}
