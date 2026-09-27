import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { history } from '@/lib/history'
import type { HistorySummary, Language } from '@/lib/types'
import { cn, formatDate } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Segmented } from '@/components/FlaggedClaims'
import Reveal from '@/components/Reveal'

type LangFilter = 'all' | Language

function SignedOut() {
  return (
    <Reveal className="py-10">
      <p className="font-serif text-[20px] text-ink">Sign in to see your history.</p>
      <p className="mt-2 max-w-[60ch] text-[15px] text-muted">
        Checks are saved to your account on the server, and only you can see them. You can still check text
        without an account; it just is not saved.
      </p>
      <div className="mt-4 flex flex-wrap gap-4">
        <Button asChild>
          <Link to="/login?next=/history">Sign in</Link>
        </Button>
        <Button asChild variant="link">
          <Link to="/register?next=/history">Create an account</Link>
        </Button>
      </div>
    </Reveal>
  )
}

export default function History() {
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [entries, setEntries] = useState<HistorySummary[] | null>(null)
  const [anyAtAll, setAnyAtAll] = useState<boolean | null>(null)
  const [lang, setLang] = useState<LangFilter>('all')
  const [query, setQuery] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<HistorySummary | null>(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    try {
      setError(null)
      const list = await history.list({ q: query, language: lang === 'all' ? undefined : lang })
      setEntries(list)
      if (!query.trim() && lang === 'all') setAnyAtAll(list.length > 0)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load your history.')
    }
  }, [query, lang])

  // Server-side search: debounce typing.
  useEffect(() => {
    if (!user) return
    const t = setTimeout(() => void load(), query ? 250 : 0)
    return () => clearTimeout(t)
  }, [user, load, query])

  async function confirmDelete() {
    if (!pending) return
    setDeleting(true)
    try {
      await history.remove(pending.id)
      setPending(null)
      toast.success('Entry deleted')
      await load()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Could not delete the entry.')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div>
      <div className="border-b border-rule pb-4">
        <h1 className="font-serif text-[32px] font-semibold leading-tight text-navy">History</h1>
        <p className="mt-1 text-[13px] text-muted">
          {user
            ? `Checks saved to ${user.email}, newest first. Opening one shows the saved result without re-checking it.`
            : 'Your saved checks.'}
        </p>
      </div>

      {authLoading ? null : !user ? (
        <SignedOut />
      ) : error ? (
        <div role="alert" className="mt-6 text-[15px]">
          <p className="text-flag-no">{error}</p>
          <Button size="sm" className="mt-3" onClick={() => void load()}>
            Retry
          </Button>
        </div>
      ) : entries === null ? (
        <p className="mt-6 text-[15px] text-muted">Loading…</p>
      ) : anyAtAll === false ? (
        <Reveal className="py-12">
          <p className="font-serif text-[20px] text-ink">Nothing analysed yet.</p>
          <Button asChild variant="link" className="mt-2">
            <Link to="/analyse">Check a passage</Link>
          </Button>
        </Reveal>
      ) : (
        <>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <label htmlFor="history-search" className="sr-only">
              Search saved texts
            </label>
            <Input
              id="history-search"
              type="search"
              placeholder="Search saved texts"
              value={query}
              maxLength={200}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full sm:w-72"
            />
            <Segmented<LangFilter>
              label="Filter by language"
              value={lang}
              onChange={setLang}
              options={[
                { value: 'all', label: 'All' },
                { value: 'en', label: 'English', lang: 'en' },
                { value: 'hi', label: 'हिन्दी', lang: 'hi' },
              ]}
            />
          </div>

          {entries.length === 0 ? (
            <p className="mt-8 text-[15px] text-muted">No saved checks match.</p>
          ) : (
            <Reveal>
              <ul className="mt-5 divide-y divide-rule border-y border-rule">
                {entries.map((e) => {
                  const flagged = e.flagged_count > 0
                  return (
                    <li key={e.id} className="flex items-start gap-3 py-3.5">
                      <button
                        type="button"
                        onClick={() => navigate(`/analyse?id=${encodeURIComponent(e.id)}`)}
                        className="group min-w-0 flex-1 rounded text-left"
                      >
                        <span className="block text-[13px] tabular-nums text-muted">{formatDate(e.created_at)}</span>
                        <span
                          lang={e.language}
                          className="mt-0.5 block truncate font-serif text-[17px] text-ink group-hover:text-navy group-hover:underline group-hover:decoration-rule group-hover:underline-offset-4"
                        >
                          {e.preview || '(empty)'}
                        </span>
                        <span className="mt-2 flex flex-wrap gap-2">
                          <span className="inline-flex h-6 items-center rounded border border-rule px-2 text-[12px] text-muted">
                            {e.language === 'hi' ? 'हिन्दी' : 'English'}
                          </span>
                          <span
                            className={cn(
                              'inline-flex h-6 items-center rounded border px-2 text-[12px] font-medium',
                              flagged
                                ? 'border-flag-no/30 bg-flag-no-bg text-flag-no'
                                : 'border-flag-yes/30 bg-flag-yes-bg text-flag-yes',
                            )}
                          >
                            {flagged
                              ? `${e.flagged_count} of ${e.total_claims} flagged`
                              : `None of ${e.total_claims} flagged`}
                          </span>
                        </span>
                      </button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setPending(e)}
                        aria-label={`Delete the check from ${formatDate(e.created_at)}`}
                        className="shrink-0 text-muted hover:text-flag-no"
                      >
                        Delete
                      </Button>
                    </li>
                  )
                })}
              </ul>
            </Reveal>
          )}
        </>
      )}

      <Dialog open={pending !== null} onOpenChange={(open) => !open && !deleting && setPending(null)}>
        <DialogContent>
          <DialogTitle>Delete this check?</DialogTitle>
          <DialogDescription>It is removed from your history on the server. This can’t be undone.</DialogDescription>
          {pending && (
            <p lang={pending.language} className="mt-3 truncate border-l-2 border-rule pl-3 font-serif text-[15px] text-ink">
              {pending.preview}
            </p>
          )}
          <div className="mt-6 flex justify-end gap-2">
            <DialogClose asChild>
              <Button variant="outline" size="sm" disabled={deleting}>
                Cancel
              </Button>
            </DialogClose>
            <Button variant="danger" size="sm" onClick={() => void confirmDelete()} disabled={deleting}>
              {deleting ? 'Deleting…' : 'Delete'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
