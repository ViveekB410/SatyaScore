import { VERDICT_META } from '../lib/verdicts'

// PRD FR-06: bar chart of HalluScore across all claims. One bar per claim,
// coloured by verdict, with the 0.35 / 0.65 verdict cut-offs marked.
export default function ScoreChart({ claims }) {
  const H = 140
  return (
    <div className="rounded-md border border-rule bg-white p-4">
      <div className="relative" style={{ height: H }}>
        {[0.35, 0.65].map((t) => (
          <div key={t} className="absolute left-0 right-0 border-t border-dashed border-ink/30"
               style={{ bottom: `${t * 100}%` }}>
            <span className="absolute -top-4 right-0 text-[10px] text-ink/50">{t}</span>
          </div>
        ))}
        <div className="absolute inset-0 flex items-end gap-1">
          {claims.map((c, i) => (
            <div key={c.claim_id} className="group relative flex-1" style={{ height: '100%' }}>
              <div className={`absolute bottom-0 w-full rounded-t-sm ${VERDICT_META[c.verdict].dot}`}
                   style={{ height: `${Math.max(2, c.hallu_score * 100)}%` }}
                   title={`Claim ${i + 1}: ${c.hallu_score.toFixed(2)} — ${VERDICT_META[c.verdict].label}`} />
            </div>
          ))}
        </div>
      </div>
      <div className="mt-2 flex justify-between text-xs text-ink/50">
        <span>Claims 1–{claims.length}, in text order</span>
        <span>HalluScore (0 = contradicted, 1 = supported)</span>
      </div>
    </div>
  )
}
