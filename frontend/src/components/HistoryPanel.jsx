import { useEffect, useState } from 'react'

const DOT = {
  Hallucinated: 'bg-flag-hallucinated',
  Uncertain: 'bg-flag-uncertain',
  Verified: 'bg-flag-verified',
}

function relTime(ts) {
  const s = Math.floor((Date.now() - ts) / 1000)
  if (s < 60) return 'just now'
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function worstVerdict(claims) {
  if (claims.some((c) => c.verdict === 'Hallucinated')) return 'Hallucinated'
  if (claims.some((c) => c.verdict === 'Uncertain')) return 'Uncertain'
  return 'Verified'
}

export default function HistoryPanel({ items, activeId, onSelect, onClear, className = '', sticky = true }) {
  // Tick every 30s so relative timestamps stay "alive" without a reload.
  const [, setTick] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 30_000)
    return () => clearInterval(t)
  }, [])

  return (
    <aside className={className}>
      <div className={sticky ? 'sticky top-20 max-h-[calc(100vh-6rem)] overflow-y-auto pb-4' : ''}>
        <div className="flex items-center justify-between border-b border-rule pb-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-navy">
            History
          </h2>
          {items.length > 0 && (
            <button
              onClick={onClear}
              className="rounded text-xs text-ink/40 transition hover:text-flag-hallucinated"
            >
              Clear
            </button>
          )}
        </div>

        {items.length === 0 ? (
          <p className="mt-4 text-[13px] leading-relaxed text-ink/40">
            Your analyses will appear here.
          </p>
        ) : (
          <ul className="mt-3 space-y-1">
            {items.map((it) => {
              const flagged = it.result.claims.filter(
                (c) => c.verdict === 'Hallucinated' || c.verdict === 'Uncertain',
              ).length
              const worst = worstVerdict(it.result.claims)
              const active = it.id === activeId
              return (
                <li key={it.id} className="animate-fade-in-up">
                  <button
                    onClick={() => onSelect(it)}
                    className={`w-full rounded-lg border-l-2 px-3 py-2.5 text-left transition ${
                      active
                        ? 'border-l-navy bg-card shadow-card'
                        : 'border-l-transparent hover:bg-card/70'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${DOT[worst]}`} />
                      <span
                        className={`line-clamp-2 text-sm text-ink/80 ${
                          it.language === 'hi' ? 'font-deva' : ''
                        }`}
                      >
                        {it.text}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-2 pl-4 text-[11px] text-ink/40">
                      <span className="uppercase">{it.language}</span>
                      <span>·</span>
                      <span>{flagged ? `${flagged} flagged` : 'none flagged'}</span>
                      <span>·</span>
                      <span>{relTime(it.ts)}</span>
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </aside>
  )
}
