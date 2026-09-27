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

export function Field({
  id,
  label,
  hint,
  ...props
}: { id: string; label: string; hint?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label htmlFor={id} className="label-caps">
        {label}
      </label>
      <Input id={id} className="mt-1.5" aria-describedby={hint ? `${id}-hint` : undefined} {...props} />
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
