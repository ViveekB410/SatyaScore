import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError, MAX_CHARS, detect, extractText } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { exportCsv, exportJson } from '@/lib/exportResults'
import { fromResponse, history } from '@/lib/history'
import type { Analysis, Language } from '@/lib/types'
import { VERDICT, overallScore, summarise } from '@/lib/verdicts'
import { EXAMPLES, cn, detectLanguage, formatDate } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/input'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import ClaimGroups, { Segmented } from '@/components/FlaggedClaims'
import MarkedText from '@/components/MarkedText'
import Reveal from '@/components/Reveal'
import ScoresPanel from '@/components/ScoresPanel'
import SourcesList from '@/components/SourcesList'
import WaitingPanel from '@/components/WaitingPanel'
import WholeTextVerdict from '@/components/WholeTextVerdict'

type Phase = 'input' | 'waiting' | 'loading-saved' | 'results' | 'error'

type LangMode = 'auto' | Language

const LANG_MODES: { value: LangMode; label: string; lang?: string }[] = [
  { value: 'auto', label: 'Auto' },
  { value: 'en', label: 'English', lang: 'en' },
  { value: 'hi', label: 'हिन्दी', lang: 'hi' },
]

function Legend({ markVerified }: { markVerified: boolean }) {
  const items = (['Hallucinated', 'Uncertain', 'Verified'] as const).filter((v) => markVerified || v !== 'Verified')
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-muted">
      {items.map((v) => (
        <li key={v} className="inline-flex items-center gap-2">
          <span className={cn('inline-block h-[3px] w-5 rounded-full', VERDICT[v].bar)} aria-hidden="true" />
          {VERDICT[v].label}
        </li>
      ))}
    </ul>
  )
}

export default function Analyse() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [params, setParams] = useSearchParams()
  const [text, setText] = useState('')
  // Auto: the language is read from the script of the text (Devanagari -> Hindi).
  const [langMode, setLangMode] = useState<LangMode>('auto')
  const detected = useMemo(() => detectLanguage(text), [text])
  const language: Language = langMode === 'auto' ? (detected?.language ?? 'en') : langMode
  const [phase, setPhase] = useState<Phase>('input')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [markVerified, setMarkVerified] = useState(true)
  const [showScores, setShowScores] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const textArea = useRef<HTMLTextAreaElement>(null)

  // Opening a history row: load the saved result from the server (no re-check).
  const openId = params.get('id')
  useEffect(() => {
    if (!openId) return
    let cancelled = false
    setPhase('loading-saved')
    history
      .get(openId)
      .then((saved) => {
        if (cancelled) return
        setAnalysis(saved)
        setText(saved.input_text)
        setLangMode(detectLanguage(saved.input_text)?.language === saved.language ? 'auto' : saved.language)
        setShowScores(false)
        setPhase('results')
      })
      .catch((e) => {
        if (cancelled) return
        setParams({}, { replace: true })
        setPhase('input')
        if (e instanceof ApiError && e.status === 401) {
          toast.error('Sign in to open your saved checks.')
          navigate(`/login?next=${encodeURIComponent(location.pathname + location.search)}`)
        } else {
          toast.error(e instanceof ApiError ? e.message : 'Could not open that saved check.')
        }
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openId])

  async function run() {
    if (phase === 'waiting') return
    setError(null)
    setPhase('waiting')
    try {
      const res = await detect(text, language)
      setAnalysis(fromResponse(text, language, res))
      setShowScores(false)
      setPhase('results')
      window.scrollTo({ top: 0 })
    } catch (e) {
      // The text stays in the box, so retrying is one click.
      setError(e instanceof ApiError ? e.message : 'Something went wrong. Your text is kept; try again.')
      setPhase('error')
    }
  }

  // Empty the text box and start fresh (language back to auto-detect).
  function clearPassage() {
    setText('')
    setLangMode('auto')
    setError(null)
    setPhase('input')
    requestAnimationFrame(() => textArea.current?.focus())
  }

  function checkAnother() {
    setParams({}, { replace: true })
    clearPassage()
  }

  async function onFile(file: File) {
    try {
      const { text: t, truncated } = await extractText(file)
      setText(t)
      toast.success(`Loaded ${file.name}`, {
        description: truncated ? `Cut to the first ${MAX_CHARS.toLocaleString()} characters.` : undefined,
      })
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Could not read that file.')
    }
  }

  if (phase === 'loading-saved') {
    return <p className="text-[15px] text-muted">Opening the saved check…</p>
  }

  // ---- results -------------------------------------------------------------
  if (phase === 'results' && analysis) {
    const doc = summarise(analysis.claims, analysis.document)
    return (
      <div className="space-y-8">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-rule pb-4">
          <div>
            <h1 className="font-serif text-[32px] font-semibold leading-tight text-navy">Result</h1>
            <p className="mt-1 text-[13px] text-muted">
              {analysis.language === 'hi' ? 'Hindi' : 'English'} · {formatDate(analysis.created_at)}
              {analysis.processing_time_ms != null && ` · checked in ${(analysis.processing_time_ms / 1000).toFixed(1)} s`}
              {' · '}
              {analysis.id ? (
                'saved to your history'
              ) : (
                <>
                  not saved ·{' '}
                  <Link to="/login?next=/analyse" className="text-navy underline underline-offset-4">
                    sign in
                  </Link>{' '}
                  to keep your checks
                </>
              )}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm">
                  Export
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => exportCsv(analysis)}>CSV (spreadsheet)</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => exportJson(analysis)}>JSON (full result)</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button size="sm" onClick={checkAnother}>
              Check another passage
            </Button>
          </div>
        </div>

        <Reveal order={0}>
          <WholeTextVerdict doc={doc} score={overallScore(analysis.claims)} />
        </Reveal>

        <Reveal order={1}>
          <section aria-labelledby="marked">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="marked" className="label-caps">
                Your text, claim by claim
              </h2>
              <label className="inline-flex cursor-pointer items-center gap-2 text-[13px] text-muted">
                <input
                  type="checkbox"
                  checked={markVerified}
                  onChange={(e) => setMarkVerified(e.target.checked)}
                  className="h-4 w-4 accent-navy"
                />
                Mark verified claims
              </label>
            </div>
            <div className="mt-3 rounded border border-rule bg-card px-5 py-6 sm:px-8 sm:py-8">
              <MarkedText
                text={analysis.input_text}
                language={analysis.language}
                claims={analysis.claims}
                markSupported={markVerified}
              />
            </div>
            <div className="mt-3">
              <Legend markVerified={markVerified} />
            </div>
          </section>
        </Reveal>

        <Reveal order={2}>
          <ClaimGroups claims={analysis.claims} language={analysis.language} />
        </Reveal>

        <Reveal order={3}>
          <section aria-labelledby="scores" className="border-t border-rule pt-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="scores" className="label-caps">
                Scores
              </h2>
              <Button variant="link" size="sm" aria-expanded={showScores} onClick={() => setShowScores((s) => !s)}>
                {showScores ? 'Hide scores' : 'Show scores'}
              </Button>
            </div>
            {showScores ? (
              <div className="mt-3 animate-fade-in">
                <ScoresPanel claims={analysis.claims} language={analysis.language} />
              </div>
            ) : (
              <p className="mt-2 text-[13px] text-muted">
                The support score (HalluScore) behind each verdict. Hidden by default: the verdicts
                above are the result.
              </p>
            )}
          </section>
        </Reveal>

        <div className="space-y-3 border-t border-rule pt-6">
          <SourcesList claims={analysis.claims} />
          <Button variant="outline" onClick={checkAnother}>
            Check another passage
          </Button>
        </div>
      </div>
    )
  }

  // ---- input / waiting / error --------------------------------------------
  const busy = phase === 'waiting'
  const over = text.length > MAX_CHARS
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-[32px] font-semibold leading-tight text-navy">Check a passage</h1>
        <p className="mt-1 max-w-[62ch] text-[15px] text-muted">
          Each factual claim is checked against retrieved evidence and marked in place as Hallucinated, Uncertain or
          Verified.
          {!user && ' Signing in saves your checks to your history.'}
        </p>
      </div>

      <section aria-label="Text to check" className="rounded border border-rule bg-card p-4 sm:p-5">
        <label htmlFor="passage" className="label-caps">
          Text to check
        </label>
        <Textarea
          id="passage"
          ref={textArea}
          lang={language}
          value={text}
          readOnly={busy}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && text.trim() && !busy && !over) void run()
          }}
          rows={8}
          placeholder="Paste a chatbot answer or any AI-generated text"
          className="mt-2"
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Segmented<LangMode> label="Language of the text" value={langMode} options={LANG_MODES} onChange={setLangMode} />
          {langMode === 'auto' && (
            <span className="text-[13px] text-muted" aria-live="polite">
              {detected
                ? `Detected: ${detected.language === 'hi' ? 'Hindi' : 'English'}${detected.mixed ? ' (mixed scripts)' : ''}`
                : 'Detects the language as you type'}
            </span>
          )}
          <input
            ref={fileInput}
            type="file"
            accept=".txt,.pdf,text/plain,application/pdf"
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(e) => {
              const f = e.target.files?.[0]
              e.target.value = ''
              if (f) void onFile(f)
            }}
          />
          <Button variant="outline" size="sm" disabled={busy} onClick={() => fileInput.current?.click()}>
            Upload .txt / .pdf
          </Button>
          <Button variant="ghost" size="sm" disabled={busy || !text} onClick={clearPassage}>
            Clear
          </Button>
          <span className={cn('ml-auto text-[13px] tabular-nums', over ? 'font-medium text-flag-no' : 'text-muted')}>
            {text.length.toLocaleString()} / {MAX_CHARS.toLocaleString()}
          </span>
          <Button onClick={() => void run()} disabled={busy || !text.trim() || over}>
            {busy ? 'Analysing…' : 'Analyse'}
          </Button>
        </div>

        <div className="mt-4 border-t border-rule pt-3">
          <p className="label-caps">Examples</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex.label}
                type="button"
                lang={ex.language}
                disabled={busy}
                onClick={() => {
                  setText(ex.text)
                  setLangMode('auto')
                }}
                className="h-8 rounded border border-rule bg-paper px-3 text-[13px] text-ink transition-colors hover:border-navy/60 hover:text-navy disabled:opacity-40"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {busy && (
        <Reveal>
          <WaitingPanel />
        </Reveal>
      )}

      {phase === 'error' && error && (
        <Reveal>
          <section role="alert" className="relative rounded border border-rule bg-card py-4 pl-7 pr-5">
            <span className="absolute inset-y-0 left-0 w-1 rounded-l bg-flag-no" aria-hidden="true" />
            <p className="font-medium text-flag-no">The check could not be completed</p>
            <p className="mt-1 text-[15px] text-ink">{error}</p>
            <p className="mt-1 text-[13px] text-muted">Your text is still in the box above.</p>
            <div className="mt-3 flex gap-3">
              <Button size="sm" onClick={() => void run()} disabled={!text.trim() || over}>
                Retry
              </Button>
            </div>
          </section>
        </Reveal>
      )}
    </div>
  )
}
