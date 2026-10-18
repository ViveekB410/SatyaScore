import { useEffect, useState } from 'react'

// A designed waiting state (not a bare spinner): cycle stage labels so a ~10-40s
// request reads as progress, over a skeleton of the result cards.
const STAGES = [
  'Extracting claims…',
  'Retrieving evidence…',
  'Checking entailment…',
  'Scoring claims…',
]

export default function WaitingState() {
  const [i, setI] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setI((p) => (p + 1) % STAGES.length), 2600)
    return () => clearInterval(t)
  }, [])
  return (
    <div className="space-y-4" aria-live="polite">
      <div className="flex flex-wrap items-center gap-3 text-navy">
        <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-navy" />
        <span key={i} className="animate-fade-in font-sans text-sm font-medium tracking-wide">{STAGES[i]}</span>
        <span className="font-sans text-xs text-ink/40">this can take up to a minute</span>
      </div>
      <div className="rounded-xl border border-rule bg-card p-6 shadow-card">
        <div className="skeleton h-3 w-24 rounded" />
        <div className="skeleton mt-4 h-9 w-56 rounded" />
        <div className="skeleton mt-5 h-2 w-full rounded-full" />
        <div className="mt-4 grid grid-cols-3 gap-3">
          {[0, 1, 2].map((k) => <div key={k} className="skeleton h-16 rounded-lg" />)}
        </div>
      </div>
      <div className="rounded-xl border border-rule bg-card p-6 shadow-card">
        <div className="flex h-28 items-end gap-2">
          {[60, 35, 80, 50, 70, 25].map((h, k) => (
            <div key={k} className="skeleton flex-1 rounded-t-md" style={{ height: `${h}%` }} />
          ))}
        </div>
      </div>
    </div>
  )
}
