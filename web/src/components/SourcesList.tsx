import { useState } from 'react'
import type { Claim, SourceRef } from '@/lib/types'
import { cn } from '@/lib/utils'

const ROLE_LABEL: Record<SourceRef['role'], string> = {
  supports: 'supports a claim',
  contradicts: 'contradicts a claim',
  'knowledge graph': 'decided a claim (knowledge graph)',
  checked: 'checked',
}

function SourceLink({ s }: { s: SourceRef }) {
  return (
    <a href={s.url} target="_blank" rel="noopener noreferrer" lang={s.language === 'hi' ? 'hi' : undefined}
       className="text-navy underline decoration-rule underline-offset-2 hover:decoration-navy">
      {s.title}
    </a>
  )
}

/** Every reference the claims were checked against, de-duplicated: the ones that
 * decided a verdict first, the rest ("also consulted") on request. */
export default function SourcesList({ claims }: { claims: Claim[] }) {
  const [showAll, setShowAll] = useState(false)
  const byKey = new Map<string, { s: SourceRef; roles: Set<string> }>()
  for (const c of claims) {
    for (const s of c.sources ?? []) {
      const key = `${s.language}|${s.title}`
      const entry = byKey.get(key) ?? { s, roles: new Set<string>() }
      entry.roles.add(s.role)
      byKey.set(key, entry)
    }
  }
  if (byKey.size === 0) return null
  const all = [...byKey.values()]
  const deciding = all.filter((e) => [...e.roles].some((r) => r !== 'checked'))
  const consulted = all.filter((e) => !deciding.includes(e))
  const langs = new Set(all.map((e) => e.s.language))
  const wiki = [langs.has('en') && 'English', langs.has('hi') && 'Hindi'].filter(Boolean).join(' and ')

  return (
    <section aria-labelledby="sources" className="border-t border-rule pt-6">
      <h2 id="sources" className="label-caps">
        Sources
      </h2>
      <p className="mt-2 max-w-[70ch] text-[15px] text-ink">
        These claims were checked against trusted open references:{' '}
        {wiki && <>Wikipedia ({wiki})</>}
        {wiki && langs.has('mul') && ' and '}
        {langs.has('mul') && 'Wikidata'}. Follow the links to verify for yourself.
      </p>
      {deciding.length > 0 && (
        <ul className="mt-3 space-y-1.5 text-[14px]">
          {deciding.map(({ s, roles }) => (
            <li key={`${s.language}|${s.title}`} className="flex flex-wrap items-baseline gap-x-2">
              <SourceLink s={s} />
              <span className="text-[13px] text-muted">
                {s.language === 'mul' ? 'Wikidata' : `Wikipedia (${s.language === 'hi' ? 'Hindi' : 'English'})`}
                {' · '}
                {[...roles].filter((r) => r !== 'checked').map((r) => ROLE_LABEL[r as SourceRef['role']]).join(', ')}
              </span>
            </li>
          ))}
        </ul>
      )}
      {consulted.length > 0 && (
        <div className="mt-3">
          <button type="button" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}
                  className="text-[13px] text-navy underline decoration-rule underline-offset-4 hover:decoration-navy">
            {showAll ? 'Hide' : 'Show'} {consulted.length} more article{consulted.length > 1 ? 's' : ''} consulted
          </button>
          {showAll && (
            <ul className={cn('mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[13px]')}>
              {consulted.map(({ s }) => (
                <li key={`${s.language}|${s.title}`}>
                  <SourceLink s={s} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
