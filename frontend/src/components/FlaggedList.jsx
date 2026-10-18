import { VERDICT_META } from '../lib/verdicts'

// Literal class strings so Tailwind keeps them.
const BORDER = {
  Hallucinated: 'border-l-flag-hallucinated',
  Uncertain: 'border-l-flag-uncertain',
}

export default function FlaggedList({ claims, language }) {
  const flagged = claims.filter(
    (c) => c.verdict === 'Hallucinated' || c.verdict === 'Uncertain',
  )
  const font = language === 'hi' ? 'font-deva' : 'font-serif'

  if (flagged.length === 0) {
    // Do not celebrate — the detector misses things.
    return (
      <p className="rounded-xl border border-rule bg-card p-5 text-ink/70 shadow-card">
        No claims were flagged in this text.
      </p>
    )
  }

  return (
    <ul className="space-y-3">
      {flagged.map((c) => {
        const meta = VERDICT_META[c.verdict]
        return (
          <li key={c.claim_id}
              className={`rounded-xl border border-l-4 border-rule bg-card p-4 pl-5 shadow-card ${BORDER[c.verdict]}`}>
            <p className={`text-[17px] leading-relaxed text-ink ${font}`}>{c.text}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${meta.chip}`}>
                {meta.label}
              </span>
            </div>
            {c.note && <p className="mt-2 text-sm text-ink/60">{c.note}</p>}
          </li>
        )
      })}
    </ul>
  )
}
