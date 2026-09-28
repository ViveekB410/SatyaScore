import { Fragment } from 'react'
import type { Claim, SourceRef } from '@/lib/types'

/** One line: the references that decided a verdict (supported, contradicted, or
 * Wikidata), de-duplicated and linked. Nothing when none decided anything. */
export default function SourcesList({ claims }: { claims: Claim[] }) {
  const seen = new Map<string, SourceRef>()
  for (const c of claims) {
    for (const s of c.sources ?? []) {
      if (s.role !== 'checked') seen.set(`${s.language}|${s.title}`, s)
    }
  }
  const sources = [...seen.values()]
  if (!sources.length) return null
  return (
    <p className="text-[14px] text-muted">
      {sources.length === 1 ? 'Source: ' : 'Sources: '}
      {sources.map((s, i) => (
        <Fragment key={`${s.language}|${s.title}`}>
          {i > 0 && ', '}
          <a href={s.url} target="_blank" rel="noopener noreferrer" lang={s.language === 'hi' ? 'hi' : undefined}
             className="text-navy underline decoration-rule underline-offset-2 hover:decoration-navy">
            {s.title}
          </a>
          {s.language !== 'mul' && ' (Wikipedia)'}
        </Fragment>
      ))}
    </p>
  )
}
