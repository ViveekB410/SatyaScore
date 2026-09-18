import { useEffect, useState } from 'react'

// A designed waiting state (not a bare spinner): cycle stage labels so a ~10-40s
// request reads as progress rather than a hang.
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
    <div className="flex items-center gap-3 text-navy">
      <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-navy" />
      <span className="font-sans text-sm tracking-wide">{STAGES[i]}</span>
      <span className="font-sans text-xs text-ink/40">this can take up to a minute</span>
    </div>
  )
}
