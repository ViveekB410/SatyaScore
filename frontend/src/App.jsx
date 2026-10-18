import { useEffect, useState } from 'react'
import { detect, health, fileToText, ApiError } from './lib/api'
import { exportCsv, exportJson } from './lib/exportResults'
import ScoreChart from './components/ScoreChart'
import { EXAMPLES } from './lib/verdicts'
import { loadHistory, saveHistory } from './lib/history'
import AnnotatedText from './components/AnnotatedText'
import FlaggedList from './components/FlaggedList'
import WaitingState from './components/WaitingState'
import LoadingGate from './components/LoadingGate'
import HistoryPanel from './components/HistoryPanel'
import DocumentSummary from './components/DocumentSummary'
import ClaimScores from './components/ClaimScores'

function Legend({ color, label }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} />
      {label}
    </span>
  )
}

function Section({ title, action, delay = 0, children }) {
  return (
    <section className="animate-fade-in-up" style={{ animationDelay: `${delay}ms` }}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-serif text-xl font-semibold text-navy">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function StatusPill({ backend }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-rule bg-card px-3 py-1 text-xs text-ink/70">
      <span className={`inline-block h-2 w-2 rounded-full ${backend.ok ? 'bg-flag-verified' : 'bg-flag-hallucinated'}`} />
      {backend.ok ? (
        <>
          <span className="sm:hidden">Online</span>
          <span className="hidden sm:inline">
            Backend online · {backend.index_size != null ? backend.index_size.toLocaleString() : '?'} evidence passages
          </span>
        </>
      ) : (
        'Backend offline'
      )}
    </span>
  )
}

const PILL_OUTLINE =
  'rounded-full border border-rule bg-card px-4 py-1.5 text-sm text-ink transition hover:border-navy/40 hover:bg-subtle'

function newId() {
  try {
    return crypto.randomUUID()
  } catch {
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`
  }
}

export default function App() {
  // connection gate
  const [phase, setPhase] = useState('connecting') // 'connecting' | 'ready' | 'offline'
  const [backend, setBackend] = useState({ ok: null })

  // analysis
  const [text, setText] = useState('')
  const [language, setLanguage] = useState('en')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [submitted, setSubmitted] = useState({ text: '', language: 'en' })
  const [error, setError] = useState(null)
  const [showScores, setShowScores] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // history
  const [history, setHistory] = useState(() => loadHistory())
  const [activeId, setActiveId] = useState(null)

  async function connect() {
    setPhase('connecting')
    for (let attempt = 0; attempt < 30; attempt++) {
      const h = await health()
      if (h.ok) {
        setBackend(h)
        setPhase('ready')
        return
      }
      await new Promise((r) => setTimeout(r, 2000))
    }
    setPhase('offline')
  }

  useEffect(() => {
    connect()
  }, [])

  async function analyse() {
    if (!text.trim() || loading) return
    setLoading(true)
    setError(null)
    setResult(null)
    setActiveId(null)
    try {
      const r = await detect(text, language)
      setResult(r)
      setSubmitted({ text, language })
      const entry = { id: newId(), text, language, result: r, ts: Date.now() }
      const next = [entry, ...history].slice(0, 30)
      setHistory(next)
      saveHistory(next)
      setActiveId(entry.id)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  function restore(entry) {
    setText(entry.text)
    setLanguage(entry.language)
    setResult(entry.result)
    setSubmitted({ text: entry.text, language: entry.language })
    setActiveId(entry.id)
    setError(null)
    setLoading(false)
    setDrawerOpen(false)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function clearHistory() {
    setHistory([])
    saveHistory([])
    setActiveId(null)
  }

  if (phase !== 'ready') {
    return <LoadingGate offline={phase === 'offline'} onRetry={connect} />
  }

  const historyProps = { items: history, activeId, onSelect: restore, onClear: clearHistory }

  return (
    <div className="min-h-screen bg-paper">
      {/* Top bar */}
      <header className="sticky top-0 z-30 border-b border-rule bg-paper/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-page items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setDrawerOpen(true)}
              className="rounded-full border border-rule bg-card px-3 py-1 text-xs text-ink/80 md:hidden"
            >
              History
            </button>
            <span className="font-serif text-xl font-semibold text-navy">SatyaScore</span>
          </div>
          <StatusPill backend={backend} />
        </div>
      </header>

      {/* Mobile history drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 animate-fade-in bg-ink/30" onClick={() => setDrawerOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-[85%] max-w-[320px] animate-fade-in overflow-y-auto border-r border-rule bg-paper p-4 shadow-lift">
            <div className="mb-3 flex justify-end">
              <button onClick={() => setDrawerOpen(false)} className="rounded-full px-2 text-sm text-ink/60" aria-label="Close history">
                ✕
              </button>
            </div>
            <HistoryPanel {...historyProps} sticky={false} />
          </div>
        </div>
      )}

      <div className="mx-auto flex max-w-page gap-10 px-4 py-8 sm:px-6">
        <HistoryPanel {...historyProps} className="hidden w-[280px] shrink-0 md:block" />

        <main className="min-w-0 flex-1 animate-fade-in">
          <div>
            <h1 className="font-serif text-[32px] font-semibold leading-tight text-navy">SatyaScore</h1>
            <p className="mt-2 max-w-xl text-ink/70">
              Paste AI-generated text. Each factual claim is checked against evidence and flagged
              in place where it isn’t supported.
            </p>
          </div>

          {/* Input */}
          <section className="mt-6 rounded-xl border border-rule bg-card p-4 shadow-card sm:p-5">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) analyse()
              }}
              rows={7}
              placeholder="Paste a chatbot answer or any AI-generated text to fact-check…"
              className={`w-full resize-y rounded-lg border border-rule bg-paper p-4 text-ink outline-none transition placeholder:text-ink/40 focus:border-navy focus:ring-1 focus:ring-navy ${
                language === 'hi' ? 'font-deva' : 'font-sans'
              }`}
            />
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <div className="inline-flex rounded-full bg-subtle p-1">
                {[
                  ['en', 'English'],
                  ['hi', 'हिन्दी'],
                ].map(([code, label]) => (
                  <button
                    key={code}
                    onClick={() => setLanguage(code)}
                    aria-pressed={language === code}
                    className={`rounded-full px-3.5 py-1 text-sm transition ${
                      language === code ? 'bg-card font-medium text-navy shadow-card' : 'text-ink/60 hover:text-ink'
                    } ${code === 'hi' ? 'font-deva' : ''}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {/* PRD FR-06: .txt / .pdf upload fills the text box */}
              <label className={`cursor-pointer ${PILL_OUTLINE}`}>
                Upload .txt / .pdf
                <input
                  type="file"
                  accept=".txt,.pdf"
                  className="sr-only"
                  onChange={async (e) => {
                    const f = e.target.files?.[0]
                    e.target.value = ''
                    if (!f) return
                    try {
                      setError(null)
                      setText(await fileToText(f))
                    } catch (err) {
                      setError(err.message || 'Could not read that file.')
                    }
                  }}
                />
              </label>
              <button
                onClick={analyse}
                disabled={loading || !text.trim()}
                className="ml-auto rounded-full bg-navy px-6 py-2 text-sm font-medium text-on-navy shadow-card transition hover:-translate-y-px hover:shadow-lift disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
              >
                {loading ? 'Analysing…' : 'Analyse'}
              </button>
            </div>

            <div className="mt-4 border-t border-rule pt-4">
              <span className="text-xs uppercase tracking-wide text-ink/50">Try an example</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {EXAMPLES.map((ex, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setText(ex.text)
                      setLanguage(ex.lang)
                    }}
                    className={`rounded-full bg-subtle px-3 py-1 text-sm text-ink/80 transition hover:bg-rule hover:text-ink ${
                      ex.lang === 'hi' ? 'font-deva' : ''
                    }`}
                  >
                    {ex.label}
                  </button>
                ))}
              </div>
            </div>
          </section>

          <p className="mt-5 border-l-2 border-rule pl-3 text-[13px] italic text-ink/60">
            Research prototype. Verdicts are indicative, not authoritative.
          </p>

          {/* Results */}
          <div className="mt-8 min-h-[3rem]">
            {loading && (
              <div className="animate-fade-in">
                <WaitingState />
              </div>
            )}

            {error && !loading && (
              <div className="animate-fade-in rounded-xl border border-flag-hallucinated/40 bg-flag-hallucinated/5 p-5">
                <p className="text-flag-hallucinated">{error}</p>
                <button
                  onClick={analyse}
                  className="mt-3 rounded-full border border-navy px-4 py-1 text-sm text-navy transition hover:bg-navy hover:text-on-navy"
                >
                  Retry
                </button>
              </div>
            )}

            {result && !loading && (
              <div className="space-y-10">
                <div className="animate-fade-in-up">
                  <DocumentSummary result={result} />
                </div>

                <Section
                  title="HalluScore by claim"
                  delay={80}
                  action={
                    /* PRD FR-06: export results */
                    <div className="flex gap-2">
                      <button onClick={() => exportCsv(result)} className={`${PILL_OUTLINE} px-3 py-1 text-xs`}>
                        Export CSV
                      </button>
                      <button onClick={() => exportJson(result, submitted)} className={`${PILL_OUTLINE} px-3 py-1 text-xs`}>
                        Export JSON
                      </button>
                    </div>
                  }
                >
                  <ScoreChart claims={result.claims} />
                </Section>

                <Section title="Annotated text" delay={160}>
                  <div className="rounded-xl border border-rule bg-card p-6 shadow-card">
                    <AnnotatedText
                      text={submitted.text}
                      language={submitted.language}
                      claims={result.claims}
                    />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-4 text-xs text-ink/60">
                    <Legend color="bg-flag-hallucinated" label="Not supported by evidence" />
                    <Legend color="bg-flag-uncertain" label="Could not verify" />
                    <Legend color="bg-flag-verified" label="Supported by evidence" />
                  </div>
                </Section>

                <Section title="Flagged claims" delay={240}>
                  <FlaggedList claims={result.claims} language={submitted.language} />
                </Section>

                <div className="animate-fade-in-up" style={{ animationDelay: '320ms' }}>
                  <button
                    onClick={() => setShowScores((s) => !s)}
                    aria-expanded={showScores}
                    className={PILL_OUTLINE}
                  >
                    {showScores ? 'Hide' : 'Show'} all claims with scores
                  </button>
                  {showScores && (
                    <div className="mt-3 animate-fade-in">
                      <ClaimScores claims={result.claims} language={submitted.language} />
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
