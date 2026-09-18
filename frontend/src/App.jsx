import { useEffect, useState } from 'react'
import { detect, health, ApiError } from './lib/api'
import { EXAMPLES } from './lib/verdicts'
import AnnotatedText from './components/AnnotatedText'
import FlaggedList from './components/FlaggedList'
import WaitingState from './components/WaitingState'

function Legend({ color, label }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-3 w-3 rounded-sm ${color}`} />
      {label}
    </span>
  )
}

export default function App() {
  const [text, setText] = useState('')
  const [language, setLanguage] = useState('en')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  // The exact text/language that produced `result` — claim spans index into THIS,
  // not the textarea (which the user may keep editing).
  const [submitted, setSubmitted] = useState({ text: '', language: 'en' })
  const [error, setError] = useState(null)
  const [backend, setBackend] = useState({ ok: null })

  useEffect(() => {
    health().then(setBackend)
  }, [])

  async function analyse() {
    if (!text.trim() || loading) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const r = await detect(text, language)
      setResult(r)
      setSubmitted({ text, language })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-paper">
      <div className="mx-auto max-w-3xl px-5 py-10 sm:py-14">
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
            className={`w-full resize-y rounded-md border border-rule bg-white p-4 text-ink shadow-sm outline-none focus:border-navy ${
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
                  className={`px-3 py-1.5 text-sm ${
                    language === code ? 'bg-navy text-white' : 'bg-white text-ink'
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
            <div className="rounded-md border border-rule bg-white p-6">
              <WaitingState />
            </div>
          )}

          {error && !loading && (
            <div className="rounded-md border border-flag-hallucinated/40 bg-flag-hallucinated/5 p-4">
              <p className="text-flag-hallucinated">{error}</p>
              <button
                onClick={analyse}
                className="mt-3 rounded border border-navy px-3 py-1 text-sm text-navy hover:bg-navy hover:text-white"
              >
                Retry
              </button>
            </div>
          )}

          {result && !loading && (
            <div className="space-y-10">
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
                </div>
              </div>

              <div>
                <h2 className="font-serif text-xl text-navy">Flagged claims</h2>
                <div className="mt-3">
                  <FlaggedList claims={result.claims} language={submitted.language} />
                </div>
              </div>
            </div>
          )}
        </section>

        <footer className="mt-14 flex items-center gap-2 border-t border-rule pt-4 text-xs text-ink/50">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              backend.ok ? 'bg-flag-verified' : backend.ok === false ? 'bg-flag-hallucinated' : 'bg-rule'
            }`}
          />
          {backend.ok
            ? `Backend online · ${backend.index_size ?? '?'} evidence passages`
            : backend.ok === false
              ? 'Backend offline — start the API (uvicorn member3_backend.api:app)'
              : 'Checking backend…'}
        </footer>
      </div>
    </div>
  )
}
