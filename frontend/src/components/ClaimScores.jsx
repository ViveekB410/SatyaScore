import { VERDICT_META } from '../lib/verdicts'

// Every claim with its verdict and score. Shown on request; the default view
// stays verdict-only. The score is the support score (0 = contradicted by the
// evidence, 1 = supported); it is not a calibrated probability.
export default function ClaimScores({ claims, language }) {
  const font = language === 'hi' ? 'font-deva' : 'font-serif'
  return (
    <div className="overflow-hidden rounded-xl border border-rule bg-card shadow-card">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-rule bg-subtle text-xs uppercase tracking-wide text-ink/50">
            <tr>
              <th className="px-4 py-2.5 font-medium">Claim</th>
              <th className="px-4 py-2.5 font-medium">Verdict</th>
              <th className="px-4 py-2.5 text-right font-medium">Support score</th>
              <th className="px-4 py-2.5 text-right font-medium">P(Verified) [95% CI]</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((c) => {
              const meta = VERDICT_META[c.verdict]
              return (
                <tr key={c.claim_id} className="border-b border-rule align-top last:border-0 even:bg-zebra">
                  <td className={`min-w-[16rem] px-4 py-3 text-ink ${font}`}>{c.text}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-2 whitespace-nowrap text-ink/80">
                      <span className={`inline-block h-2 w-2 rounded-full ${meta.dot}`} />
                      {meta.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-ink/80">
                    {c.hallu_score.toFixed(2)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-ink/80">
                    {c.p_verified == null
                      ? '—'
                      : `${c.p_verified.toFixed(2)} [${c.p_verified_ci95[0].toFixed(2)}, ${c.p_verified_ci95[1].toFixed(2)}]`}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="border-t border-rule px-4 py-3 text-xs leading-relaxed text-ink/50">
        Support score: 0 = contradicted by evidence, 1 = supported. Below 0.35 is flagged as
        not supported, above 0.65 as supported. The score itself is not a probability; P(Verified)
        is the share of training claims with a similar score that were Verified, with a 95%
        interval. Wide or overlapping intervals mean the score is weak evidence either way.
      </p>
    </div>
  )
}
