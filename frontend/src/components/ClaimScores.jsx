import { VERDICT_META } from '../lib/verdicts'

// Every claim with its verdict and score. Shown on request; the default view
// stays verdict-only. The score is the support score (0 = contradicted by the
// evidence, 1 = supported); it is not a calibrated probability.
export default function ClaimScores({ claims, language }) {
  const font = language === 'hi' ? 'font-deva' : 'font-serif'
  return (
    <div className="overflow-x-auto rounded-md border border-rule bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-rule text-xs uppercase tracking-wide text-ink/50">
          <tr>
            <th className="px-4 py-2 font-medium">Claim</th>
            <th className="px-4 py-2 font-medium">Verdict</th>
            <th className="px-4 py-2 text-right font-medium">Support score</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((c) => {
            const meta = VERDICT_META[c.verdict]
            return (
              <tr key={c.claim_id} className="border-b border-rule last:border-0 align-top">
                <td className={`px-4 py-3 text-ink ${font}`}>{c.text}</td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-2 whitespace-nowrap text-ink/80">
                    <span className={`inline-block h-2 w-2 rounded-full ${meta.dot}`} />
                    {meta.label}
                  </span>
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-ink/80">
                  {c.hallu_score.toFixed(2)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="border-t border-rule px-4 py-2 text-xs text-ink/50">
        Support score: 0 = contradicted by evidence, 1 = supported. Below 0.35 is flagged as
        not supported, above 0.65 as supported. Scores are not calibrated probabilities.
      </p>
    </div>
  )
}
