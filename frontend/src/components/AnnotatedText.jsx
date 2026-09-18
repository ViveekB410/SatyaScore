import { VERDICT_META } from '../lib/verdicts'

// Split the original text into plain + highlighted segments using claim spans.
// Robust to overlaps and out-of-range offsets: clamp, sort, and skip any span
// that overlaps one already applied.
function buildSegments(text, claims) {
  const n = text.length
  const flags = claims
    .filter((c) => c.verdict === 'Hallucinated' || c.verdict === 'Uncertain')
    .map((c) => ({
      start: Math.max(0, Math.min(c.start_char ?? 0, n)),
      end: Math.max(0, Math.min(c.end_char ?? 0, n)),
      verdict: c.verdict,
    }))
    .filter((c) => c.end > c.start)
    .sort((a, b) => a.start - b.start)

  const applied = []
  let lastEnd = 0
  for (const f of flags) {
    if (f.start >= lastEnd) {
      applied.push(f)
      lastEnd = f.end
    }
  }

  const segs = []
  let cursor = 0
  for (const f of applied) {
    if (f.start > cursor) segs.push({ text: text.slice(cursor, f.start), verdict: null })
    segs.push({ text: text.slice(f.start, f.end), verdict: f.verdict })
    cursor = f.end
  }
  if (cursor < n) segs.push({ text: text.slice(cursor), verdict: null })
  return segs
}

export default function AnnotatedText({ text, language, claims }) {
  const segments = buildSegments(text, claims)
  const font = language === 'hi' ? 'font-deva' : 'font-serif'
  return (
    <div className={`whitespace-pre-wrap break-words text-lg leading-loose text-ink ${font}`}>
      {segments.map((s, i) =>
        s.verdict ? (
          <span
            key={i}
            title={VERDICT_META[s.verdict].label}
            className={`rounded-sm px-0.5 ${VERDICT_META[s.verdict].highlight}`}
          >
            {s.text}
          </span>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
    </div>
  )
}
