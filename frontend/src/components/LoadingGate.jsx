import { useEffect, useState } from 'react'

// Full-screen gate shown until the backend responds. The API warms models at
// startup (~1 min), so we cycle reassuring messages while polling.
const MESSAGES = [
  'Connecting to the backend…',
  'Waking the model…',
  'Loading the evidence corpus…',
  'Almost ready…',
]

export default function LoadingGate({ offline, onRetry }) {
  const [i, setI] = useState(0)
  useEffect(() => {
    if (offline) return
    const t = setInterval(() => setI((p) => Math.min(p + 1, MESSAGES.length - 1)), 3000)
    return () => clearInterval(t)
  }, [offline])

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-6">
      <div className="animate-fade-in text-center">
        <h1 className="font-serif text-5xl font-semibold text-navy">SatyaScore</h1>
        <p className="mt-2 text-sm tracking-wide text-ink/50">
          Claim-level hallucination detection
        </p>

        {offline ? (
          <div className="mt-10">
            <p className="text-flag-hallucinated">Couldn’t reach the backend.</p>
            <p className="mx-auto mt-2 max-w-sm text-sm text-ink/60">
              Start it, then retry:
              <br />
              <code className="mt-1 inline-block rounded bg-white px-2 py-1 text-xs text-ink/80 ring-1 ring-rule">
                uvicorn member3_backend.api:app --port 8000
              </code>
            </p>
            <button
              onClick={onRetry}
              className="mt-5 rounded-md bg-navy px-5 py-2 text-sm font-medium text-white transition hover:bg-navy/90"
            >
              Retry connection
            </button>
          </div>
        ) : (
          <div className="mt-12 flex flex-col items-center gap-5">
            <div className="flex gap-2">
              {[0, 1, 2].map((d) => (
                <span
                  key={d}
                  className="h-2.5 w-2.5 animate-bounce rounded-full bg-navy"
                  style={{ animationDelay: `${d * 150}ms` }}
                />
              ))}
            </div>
            <p key={i} className="animate-fade-in text-sm text-ink/60">
              {MESSAGES[i]}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
