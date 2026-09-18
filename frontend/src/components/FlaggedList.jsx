import { VERDICT_META } from '../lib/verdicts'

// Literal class strings so Tailwind keeps them.
const BORDER = {
  Hallucinated: 'border-flag-hallucinated',
  Uncertain: 'border-flag-uncertain',
}

export default function FlaggedList({ claims, language }) {
  const flagged = claims.filter(
    (c) => c.verdict === 'Hallucinated' || c.verdict === 'Uncertain',
  )
  const font = language === 'hi' ? 'font-deva' : 'font-serif'

  if (flagged.length === 0) {
    // Do not celebrate — the detector misses things.
    return <p className="text-ink/70">No claims were flagged in this text.</p>
  }

  return (
    <ul className="space-y-5">
      {flagged.map((c) => {
        const meta = VERDICT_META[c.verdict]
        return (
          <li key={c.claim_id} className={`border-l-2 pl-4 ${BORDER[c.verdict]}`}>
            <p className={`text-ink ${font}`}>{c.text}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className={`rounded px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${meta.chip}`}>
                {meta.label}
              </span>
              {c.note && <span className="text-sm text-ink/60">{c.note}</span>}
            </div>
          </li>
        )
      })}
    </ul>
  )
}
