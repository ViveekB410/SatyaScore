import { VERDICT_META } from '../lib/verdicts'

// PRD FR-06: bar chart of HalluScore across all claims. One bar per claim,
// coloured by verdict, with the 0.35 / 0.65 verdict cut-offs marked.
export default function ScoreChart({ claims }) {
  const H = 160
  return (
    <div className="rounded-xl border border-rule bg-card p-5 shadow-card">
      <div className="flex gap-3">
        <div className="relative w-6 shrink-0 text-right text-[11px] tabular-nums text-ink/40" style={{ height: H }}>
          <span className="absolute right-0 top-0 -translate-y-1/2">1.0</span>
          <span className="absolute right-0 top-1/2 -translate-y-1/2">0.5</span>
          <span className="absolute bottom-0 right-0 translate-y-1/2">0</span>
        </div>
        <div className="relative flex-1" style={{ height: H }}>
          {[0.25, 0.5, 0.75, 1].map((t) => (
            <div key={t} className="absolute left-0 right-0 border-t border-rule/70" style={{ bottom: `${t * 100}%` }} />
          ))}
          <div className="absolute bottom-0 left-0 right-0 border-t border-rule" />
          {[0.35, 0.65].map((t) => (
            <div key={t} className="absolute left-0 right-0 border-t border-dashed border-ink/35"
                 style={{ bottom: `${t * 100}%` }}>
              <span className="absolute -top-4 right-0 rounded bg-card px-1 text-[10px] text-ink/50">{t}</span>
            </div>
          ))}
          <div className="absolute inset-0 flex items-end justify-center gap-1.5">
            {claims.map((c, i) => {
              const meta = VERDICT_META[c.verdict]
              return (
                <div key={c.claim_id} className="group relative h-full max-w-[48px] flex-1">
                  <div
                    className={`absolute bottom-0 w-full rounded-t-md opacity-90 transition group-hover:opacity-100 ${meta.dot}`}
                    style={{ height: `${Math.max(2, c.hallu_score * 100)}%` }}
                    aria-label={`Claim ${i + 1}: ${c.hallu_score.toFixed(2)} — ${meta.label}`}
                  />
                  <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded-md bg-ink px-2 py-1 text-[11px] text-paper shadow-lift group-hover:block">
                    Claim {i + 1}: {c.hallu_score.toFixed(2)} — {meta.label}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap justify-between gap-2 pl-9 text-[13px] text-ink/50">
        <span>Claims 1–{claims.length}, in text order</span>
        <span>HalluScore (0 = contradicted, 1 = supported)</span>
      </div>
    </div>
  )
}
