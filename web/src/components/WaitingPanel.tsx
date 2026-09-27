import { useEffect, useState } from 'react'
import { formatElapsed } from '@/lib/utils'

// A real request takes up to a minute on CPU. A bare spinner reads as frozen at
// that length, so: cycling stage, a progress rule, and a live elapsed counter.
const STAGES = ['Extracting claims…', 'Retrieving evidence…', 'Checking entailment…', 'Scoring claims…']
const STAGE_MS = 2600
const EXPECTED_MS = 60_000 // the rule fills towards this and stops short of the end

export default function WaitingPanel() {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const start = Date.now()
    const t = setInterval(() => setElapsed(Date.now() - start), 250)
    return () => clearInterval(t)
  }, [])
  const stage = STAGES[Math.floor(elapsed / STAGE_MS) % STAGES.length]
  const progress = Math.min(0.95, elapsed / EXPECTED_MS)

  return (
    <section aria-live="polite" aria-busy="true" className="rounded border border-rule bg-card px-5 py-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p key={stage} className="animate-fade-in font-serif text-[18px] text-navy">
          {stage}
        </p>
        <p className="text-[13px] tabular-nums text-muted">
          {formatElapsed(elapsed)} elapsed · usually under a minute
        </p>
      </div>
      <div className="mt-4 h-px w-full bg-rule" aria-hidden="true">
        <div className="h-px bg-navy transition-[width] duration-300 ease-out" style={{ width: `${progress * 100}%` }} />
      </div>
    </section>
  )
}
