import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError } from '@/lib/api'
import { safeNext, useAuth } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import Reveal from '@/components/Reveal'

export function AuthCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Reveal className="mx-auto max-w-sm pt-4 sm:pt-10">
      <h1 className="font-serif text-[32px] font-semibold text-navy">{title}</h1>
      <div className="mt-6 rounded border border-rule bg-card p-5 sm:p-6">{children}</div>
    </Reveal>
  )
}

function EyeIcon({ open }: { open: boolean }) {
  return (
    <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.75"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
      {!open && <path d="M4 4l16 16" />}
    </svg>
  )
}

export function Field({
  id,
  label,
  hint,
  type,
  ...props
}: { id: string; label: string; hint?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  // Password fields get a show/hide button (eye icon); the password is never shown by default.
  const [shown, setShown] = useState(false)
  const isPassword = type === 'password'
  return (
    <div>
      <label htmlFor={id} className="label-caps">
        {label}
      </label>
      <div className="relative mt-1.5">
        <Input
          id={id}
          type={isPassword && shown ? 'text' : type}
          className={isPassword ? 'pr-11' : undefined}
          aria-describedby={hint ? `${id}-hint` : undefined}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShown((s) => !s)}
            aria-label={shown ? 'Hide password' : 'Show password'}
            aria-pressed={shown}
            aria-controls={id}
            title={shown ? 'Hide password' : 'Show password'}
            className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r text-muted hover:text-navy focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-navy"
          >
            <EyeIcon open={!shown} />
          </button>
        )}
      </div>
      {hint && (
        <p id={`${id}-hint`} className="mt-1 text-[13px] text-muted">
          {hint}
        </p>
      )}
    </div>
  )
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p role="alert" className="relative rounded border border-rule bg-flag-no-bg py-2 pl-4 pr-3 text-[14px] text-flag-no">
      <span className="absolute inset-y-0 left-0 w-1 rounded-l bg-flag-no" aria-hidden="true" />
      {message}
    </p>
  )
}

export default function Login() {
  const { user, loading, signIn } = useAuth()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const next = safeNext(params.get('next'))
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!loading && user) return <Navigate to={next} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const u = await signIn(email, password)
      toast.success(`Signed in as ${u.name}`)
      navigate(next, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not sign in. Try again.')
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title="Sign in">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <FormError message={error} />
        <Field
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Field
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <p className="-mt-2 text-right text-[13px]">
          <Link to="/reset-password" className="text-navy underline decoration-rule underline-offset-4 hover:decoration-navy">
            Forgot password?
          </Link>
        </p>
        <Button type="submit" className="w-full" disabled={busy || !email || !password}>
          {busy ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
      <p className="mt-5 border-t border-rule pt-4 text-[14px] text-muted">
        No account?{' '}
        <Link to={`/register?next=${encodeURIComponent(next)}`} className="text-navy underline underline-offset-4">
          Create one
        </Link>
        . You can also check text without signing in; signing in saves your checks to your history.
      </p>
    </AuthCard>
  )
}
