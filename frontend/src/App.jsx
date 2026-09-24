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
      <span className={`inline-block h-3 w-3 rounded-sm ${color}`} />
      {label}
    </span>
  )
}

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

  return (
    <div className="min-h-screen bg-paper">
      <div className="mx-auto flex max-w-6xl gap-8 px-5 py-8">
        <HistoryPanel
          items={history}
          activeId={activeId}
          onSelect={restore}
          onClear={clearHistory}
          className="hidden w-64 shrink-0 md:block"
        />

        <main className="min-w-0 max-w-3xl flex-1 animate-fade-in">
          <header className="border-b border-rule pb-6">
            <h1 className="font-serif text-4xl font-semibold text-navy">SatyaScore</h1>
            <p className="mt-2 max-w-xl text-ink/70">
              Paste AI-generated text. Each factual claim is checked against evidence and flagged
              in place where it isn’t supported.
            </p>
          </header>

          {/* Input */}
          <section className="mt-8">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={7}
              placeholder="Paste a chatbot answer or any AI-generated text to fact-check…"
              className={`w-full resize-y rounded-md border border-rule bg-white p-4 text-ink shadow-sm outline-none transition focus:border-navy ${
                language === 'hi' ? 'font-deva' : 'font-sans'
              }`}
            />
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <div className="inline-flex overflow-hidden rounded-md border border-rule">
                {[
                  ['en', 'English'],
                  ['hi', 'हिन्दी'],
                ].map(([code, label]) => (
                  <button
                    key={code}
                    onClick={() => setLanguage(code)}
                    className={`px-3 py-1.5 text-sm transition ${
                      language === code ? 'bg-navy text-white' : 'bg-white text-ink hover:bg-rule/40'
                    } ${code === 'hi' ? 'font-deva' : ''}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <button
                onClick={analyse}
                disabled={loading || !text.trim()}
                className="rounded-md bg-navy px-5 py-1.5 text-sm font-medium text-white transition hover:bg-navy/90 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {loading ? 'Analysing…' : 'Analyse'}
              </button>
              {/* PRD FR-06: .txt / .pdf upload fills the text box */}
              <label className="cursor-pointer rounded-md border border-rule bg-white px-3 py-1.5 text-sm text-ink transition hover:bg-rule/40">
                Upload .txt / .pdf
                <input
                  type="file"
                  accept=".txt,.pdf"
                  className="hidden"
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
            </div>

            <div className="mt-4">
              <span className="text-xs uppercase tracking-wide text-ink/50">Try an example</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {EXAMPLES.map((ex, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setText(ex.text)
                      setLanguage(ex.lang)
                    }}
                    className={`rounded-full border border-rule bg-white px-3 py-1 text-sm text-ink/80 transition hover:border-navy hover:text-navy ${
                      ex.lang === 'hi' ? 'font-deva' : ''
                    }`}
                  >
                    {ex.label}
                  </button>
                ))}
              </div>
            </div>
          </section>

          <p className="mt-8 border-l-2 border-rule pl-3 text-sm italic text-ink/60">
            Research prototype. Verdicts are indicative, not authoritative.
          </p>

          {/* Results */}
          <section className="mt-6 min-h-[3rem]">
            {loading && (
              <div className="animate-fade-in rounded-md border border-rule bg-white p-6">
                <WaitingState />
              </div>
            )}

            {error && !loading && (
              <div className="animate-fade-in rounded-md border border-flag-hallucinated/40 bg-flag-hallucinated/5 p-4">
                <p className="text-flag-hallucinated">{error}</p>
                <button
                  onClick={analyse}
                  className="mt-3 rounded border border-navy px-3 py-1 text-sm text-navy transition hover:bg-navy hover:text-white"
                >
                  Retry
                </button>
              </div>
            )}

            {result && !loading && (
              <div className="animate-fade-in-up space-y-10">
                <DocumentSummary result={result} />

                <div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="font-serif text-xl text-navy">HalluScore by claim</h2>
                    {/* PRD FR-06: export results */}
                    <div className="flex gap-2">
                      <button onClick={() => exportCsv(result)}
                              className="rounded border border-rule px-3 py-1 text-xs text-ink transition hover:bg-rule/40">
                        Export CSV
                      </button>
                      <button onClick={() => exportJson(result, submitted)}
                              className="rounded border border-rule px-3 py-1 text-xs text-ink transition hover:bg-rule/40">
                        Export JSON
                      </button>
                    </div>
                  </div>
                  <div className="mt-3">
                    <ScoreChart claims={result.claims} />
                  </div>
                </div>

                <div>
                  <h2 className="font-serif text-xl text-navy">Annotated text</h2>
                  <div className="mt-3 rounded-md border border-rule bg-white p-6">
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
                </div>

                <div>
                  <h2 className="font-serif text-xl text-navy">Flagged claims</h2>
                  <div className="mt-3">
                    <FlaggedList claims={result.claims} language={submitted.language} />
                  </div>
                </div>

                <div>
                  <button
                    onClick={() => setShowScores((s) => !s)}
                    className="text-sm text-navy underline decoration-rule underline-offset-4 transition hover:decoration-navy"
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
          </section>

          <footer className="mt-14 flex items-center gap-2 border-t border-rule pt-4 text-xs text-ink/50">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                backend.ok ? 'bg-flag-verified' : 'bg-flag-hallucinated'
              }`}
            />
            {backend.ok
              ? `Backend online · ${backend.index_size ?? '?'} evidence passages`
              : 'Backend offline'}
          </footer>
        </main>
      </div>
    </div>
  )
}
