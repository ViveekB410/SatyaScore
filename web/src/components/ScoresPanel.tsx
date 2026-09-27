import type { Claim, Language } from '@/lib/types'
import { VERDICT } from '@/lib/verdicts'
import { cn } from '@/lib/utils'

const LOW = 0.35
const HIGH = 0.65

// Per-claim scores (PRD FR-04 / FR-06), shown only on request. The support score
// is drawn as a plain CSS bar against the two verdict cut-offs; no chart library.
function ScoreBar({ score, bar }: { score: number; bar: string }) {
  const pct = Math.max(0, Math.min(1, score)) * 100
  return (
    <span className="relative inline-block h-1.5 w-24 rounded-full bg-rule align-middle" aria-hidden="true">
      <span className={cn('absolute inset-y-0 left-0 rounded-full', bar)} style={{ width: `${pct}%` }} />
      <span className="absolute -inset-y-1 w-px bg-ink/40" style={{ left: `${LOW * 100}%` }} />
      <span className="absolute -inset-y-1 w-px bg-ink/40" style={{ left: `${HIGH * 100}%` }} />
    </span>
  )
}

export default function ScoresPanel({ claims, language }: { claims: Claim[]; language: Language }) {
  return (
    <div className="rounded border border-rule bg-card">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <caption className="sr-only">Support score and P(Verified) for every claim</caption>
          <thead className="border-b border-rule">
            <tr className="label-caps">
              <th scope="col" className="px-4 py-2.5 font-medium">#</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Claim</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Verdict</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Support score</th>
              <th scope="col" className="px-4 py-2.5 text-right font-medium">P(Verified) [95% CI]</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((c, i) => {
              const v = VERDICT[c.verdict]
              const ci = c.p_verified_ci95
              return (
                <tr key={c.claim_id} className="border-b border-rule align-top last:border-0">
                  <td className="px-4 py-3 tabular-nums text-muted">{i + 1}</td>
                  <td lang={language} className="px-4 py-3 font-serif text-ink">{c.text}</td>
                  <td className={cn('whitespace-nowrap px-4 py-3 font-medium', v.text)}>{v.label}</td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span className="inline-flex items-center gap-2.5">
                      <ScoreBar score={c.hallu_score} bar={v.bar} />
                      <span className="tabular-nums text-ink">{c.hallu_score.toFixed(2)}</span>
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-ink">
                    {c.p_verified == null || !ci
                      ? '—'
                      : `${c.p_verified.toFixed(2)} [${ci[0].toFixed(2)}, ${ci[1].toFixed(2)}]`}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="border-t border-rule px-4 py-3 text-[13px] leading-relaxed text-muted">
        Support score: 0 = contradicted by evidence, 1 = supported. Below {LOW} is Hallucinated, above {HIGH}{' '}
        Verified, in between Uncertain (the ticks on each bar). The score itself is not a probability; P(Verified) is the share
        of training claims with a similar score that were Verified, with a 95% interval. Wide or overlapping
        intervals mean the score is weak evidence either way.
      </p>
    </div>
  )
}
