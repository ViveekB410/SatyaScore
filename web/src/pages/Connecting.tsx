import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { API_URL } from '@/lib/api'
import { useHealth } from '@/lib/health'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import Reveal from '@/components/Reveal'

// The corpus and model load once per server session; this screen is honest about
// that wait instead of hiding it. /health answers only after startup has loaded
// both, so one successful check means every stage is done.
const MAX_ATTEMPTS = 12
const RETRY_MS = 5000
const STAGES = ['Reaching the API', 'Loading evidence corpus', 'Warming the entailment model']

type Phase = 'trying' | 'ready' | 'failed'
type RowStatus = 'Queued' | 'Working' | 'Ready'

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

export default function Connecting() {
  const { check, indexSize } = useHealth()
  const [phase, setPhase] = useState<Phase>('trying')
  const [attempt, setAttempt] = useState(1)
  const [readyRows, setReadyRows] = useState(0)
  const [run, setRun] = useState(0)

  useEffect(() => {
    let cancelled = false
    setPhase('trying')
    setReadyRows(0)
    ;(async () => {
      for (let a = 1; a <= MAX_ATTEMPTS; a++) {
        if (cancelled) return
        setAttempt(a)
        if (await check()) {
          for (let r = 1; r <= STAGES.length; r++) {
            if (cancelled) return
            setReadyRows(r)
            await sleep(180)
          }
          if (!cancelled) setPhase('ready')
          return
        }
        if (a < MAX_ATTEMPTS) await sleep(RETRY_MS)
      }
      if (!cancelled) setPhase('failed')
    })()
    return () => {
      cancelled = true
    }
  }, [check, run])

  const rowStatus = (i: number): RowStatus =>
    i < readyRows ? 'Ready' : phase === 'trying' && i === readyRows && readyRows === 0 ? 'Working' : 'Queued'
  const progress = phase === 'ready' ? 1 : readyRows / STAGES.length || (attempt - 1) / (MAX_ATTEMPTS * 3)

  return (
    <div className="mx-auto max-w-lg pt-6 sm:pt-12">
      <Reveal>
        <p className="font-serif text-[32px] font-semibold text-navy">
          SatyaScore
          {phase === 'trying' && (
            <span className="ml-2 inline-flex gap-1 align-middle" aria-hidden="true">
              {[0, 1, 2].map((d) => (
                <span key={d} className="h-1.5 w-1.5 animate-soft-pulse rounded-full bg-navy" style={{ animationDelay: `${d * 200}ms` }} />
              ))}
            </span>
          )}
        </p>
        <p className="mt-1 text-[15px] text-muted">Claim-level hallucination checking for English and Hindi text.</p>
      </Reveal>

      <Reveal order={1}>
        <h1 className="label-caps mt-10">Starting the analysis server</h1>
        <ol className="mt-3 divide-y divide-rule border-y border-rule" aria-live="polite">
          {STAGES.map((label, i) => {
            const s = rowStatus(i)
            return (
              <li key={label} className="flex items-center justify-between py-3">
                <span className={cn('text-[15px]', s === 'Queued' ? 'text-muted' : 'text-ink')}>
                  {label}
                  {i === 1 && s === 'Ready' && indexSize != null && (
                    <span className="text-muted"> · {indexSize.toLocaleString()} passages</span>
                  )}
                </span>
                <span
                  className={cn(
                    'text-[13px] font-medium',
                    s === 'Ready' ? 'text-flag-yes' : s === 'Working' ? 'text-navy' : 'text-muted',
                  )}
                >
                  {s}
                </span>
              </li>
            )
          })}
        </ol>
        <div className="mt-4 h-px bg-rule" aria-hidden="true">
          <div className="h-px bg-navy transition-[width] duration-300 ease-out" style={{ width: `${Math.max(0.04, progress) * 100}%` }} />
        </div>

        <div className="mt-6 min-h-[5rem]">
          {phase === 'trying' && attempt > 1 && (
            <p className="text-[13px] text-muted">
              No answer yet. Retrying every 5 seconds (attempt {attempt} of {MAX_ATTEMPTS}).
            </p>
          )}
          {phase === 'ready' && (
            <Reveal>
              <Button asChild size="lg">
                <Link to="/analyse">Open the workspace</Link>
              </Button>
            </Reveal>
          )}
          {phase === 'failed' && (
            <Reveal className="relative rounded border border-rule bg-card py-4 pl-6 pr-5">
              <span className="absolute inset-y-0 left-0 w-1 rounded-l bg-flag-no" aria-hidden="true" />
              <p className="font-medium text-flag-no">Can’t reach the analysis server</p>
              <p className="mt-1 text-[14px] text-muted">
                Tried {MAX_ATTEMPTS} times at <span className="font-medium text-ink">{API_URL}</span>. Start it from the
                project folder, then retry:
              </p>
              <code className="mt-2 block overflow-x-auto rounded bg-paper px-3 py-2 text-[13px] text-ink">
                python -m uvicorn member3_backend.api:app --port 8000
              </code>
              <div className="mt-4 flex flex-wrap items-center gap-4">
                <Button onClick={() => setRun((r) => r + 1)}>Retry</Button>
                <Button asChild variant="link">
                  <Link to="/history">Open your history</Link>
                </Button>
              </div>
            </Reveal>
          )}
        </div>
      </Reveal>
    </div>
  )
}
