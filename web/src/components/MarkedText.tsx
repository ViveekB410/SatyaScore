import { useState } from 'react'
import { buildSegments } from '@/lib/segments'
import type { Claim, Language } from '@/lib/types'
import { VERDICT } from '@/lib/verdicts'
import { cn } from '@/lib/utils'

// The reading surface, and the centrepiece: the user's text exactly as submitted
// (line breaks kept) with each claim marked in place. Hover, focus or tap shows
// the verdict; touch devices have no hover, so tap toggles it.
export default function MarkedText({
  text,
  language,
  claims,
  markSupported,
}: {
  text: string
  language: Language
  claims: Claim[]
  markSupported: boolean
}) {
  const [active, setActive] = useState<number | null>(null)
  const segments = buildSegments(text, claims, markSupported)

  return (
    <div
      lang={language}
      className="max-w-[70ch] whitespace-pre-wrap break-words font-serif text-[18px] leading-[1.9] text-ink"
    >
      {segments.map((s, i) => {
        if (!s.claim || s.n === null) return <span key={i}>{s.text}</span>
        const v = VERDICT[s.claim.verdict]
        const n = s.n
        const open = active === n
        return (
          <span
            key={i}
            tabIndex={0}
            role="button"
            aria-label={`Claim ${n}: ${v.label}`}
            aria-expanded={open}
            onMouseEnter={() => setActive(n)}
            onMouseLeave={() => setActive((a) => (a === n ? null : a))}
            onFocus={() => setActive(n)}
            onBlur={() => setActive((a) => (a === n ? null : a))}
            onClick={() => setActive((a) => (a === n ? null : n))}
            onKeyDown={(e) => {
              if (e.key === 'Escape') setActive(null)
            }}
            className={cn(
              'relative cursor-pointer rounded-sm underline decoration-2 underline-offset-[5px] [box-decoration-break:clone] [-webkit-box-decoration-break:clone]',
              s.claim.verdict === 'Verified' && 'decoration-1',
              v.mark,
            )}
          >
            {s.text}
            {open && (
              <span
                role="tooltip"
                className="pointer-events-none absolute bottom-full left-0 z-20 mb-1.5 whitespace-nowrap rounded bg-navy px-2 py-1 font-sans text-[12px] font-medium not-italic leading-normal text-paper shadow-overlay"
              >
                Claim {n} · {v.label}
              </span>
            )}
          </span>
        )
      })}
    </div>
  )
}
