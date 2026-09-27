import { useState } from 'react'
import type { Claim, Language, Verdict } from '@/lib/types'
import { VERDICT } from '@/lib/verdicts'
import { cn } from '@/lib/utils'

type Filter = 'all' | Verdict

// Problems first: the eye should go to what needs checking.
const GROUP_ORDER: Verdict[] = ['Hallucinated', 'Uncertain', 'Verified']

export function VerdictChip({ verdict }: { verdict: Verdict }) {
  const v = VERDICT[verdict]
  return (
    <span className={cn('inline-flex h-6 items-center rounded border px-2 text-[12px] font-medium', v.chip)}>
      {v.label}
    </span>
  )
}

export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: { value: T; label: string; lang?: string; disabled?: boolean }[]
  onChange: (v: T) => void
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex flex-wrap rounded border border-rule bg-card p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          lang={o.lang}
          disabled={o.disabled}
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            'h-8 rounded px-3 text-[13px] transition-colors disabled:opacity-40',
            value === o.value ? 'bg-navy font-medium text-paper' : 'text-muted hover:text-navy',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function ClaimCard({ claim, n, language }: { claim: Claim; n: number; language: Language }) {
  return (
    <li className="relative rounded border border-rule bg-card py-4 pl-7 pr-5">
      <span className={cn('absolute inset-y-0 left-0 w-1 rounded-l', VERDICT[claim.verdict].bar)} aria-hidden="true" />
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-[13px] tabular-nums text-muted">Claim {n}</span>
        <VerdictChip verdict={claim.verdict} />
      </div>
      <p lang={language} className="mt-2 font-serif text-[17px] font-semibold leading-relaxed text-ink">
        {claim.text}
      </p>
      {claim.note && <p className="mt-1.5 text-[14px] text-muted">{claim.note}</p>}
    </li>
  )
}

/** Every claim, grouped by verdict (Hallucinated, Uncertain, Verified), each in
 * document order and keeping its claim number from the marked text. */
export default function ClaimGroups({ claims, language }: { claims: Claim[]; language: Language }) {
  const [filter, setFilter] = useState<Filter>('all')
  const numbered = claims.map((c, i) => ({ c, n: i + 1 }))
  const groups = GROUP_ORDER.map((v) => ({ verdict: v, items: numbered.filter(({ c }) => c.verdict === v) }))
  const count = (v: Verdict) => groups.find((g) => g.verdict === v)!.items.length
  const flagged = count('Hallucinated') + count('Uncertain')
  const shown = groups.filter((g) => g.items.length > 0 && (filter === 'all' || g.verdict === filter))

  return (
    <section aria-labelledby="claims">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="claims" className="label-caps">
          Claims
        </h2>
        {claims.length > 0 && (
          <Segmented<Filter>
            label="Show claims by verdict"
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'all', label: `All ${claims.length}` },
              ...GROUP_ORDER.map((v) => ({ value: v, label: `${VERDICT[v].label} ${count(v)}`, disabled: count(v) === 0 })),
            ]}
          />
        )}
      </div>

      {flagged === 0 && (
        // Stated plainly, no celebration: the detector misses things.
        <p className="mt-4 rounded border border-rule bg-card px-5 py-4 text-ink">No claims were flagged in this text.</p>
      )}

      <div className="mt-4 space-y-6">
        {shown.map((g) => (
          <div key={g.verdict}>
            <h3 className={cn('mb-2 flex items-baseline gap-2 text-[14px] font-medium', VERDICT[g.verdict].text)}>
              {VERDICT[g.verdict].label}
              <span className="text-[13px] font-normal tabular-nums text-muted">
                {g.items.length} {g.items.length === 1 ? 'claim' : 'claims'}
              </span>
            </h3>
            <ol className="space-y-3">
              {g.items.map(({ c, n }) => (
                <ClaimCard key={c.claim_id} claim={c} n={n} language={language} />
              ))}
            </ol>
          </div>
        ))}
      </div>
    </section>
  )
}
