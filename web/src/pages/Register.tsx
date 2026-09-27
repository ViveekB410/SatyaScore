import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError } from '@/lib/api'
import { safeNext, useAuth } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { AuthCard, Field, FormError } from './Login'

const MIN_PASSWORD = 10 // same rule as the server (member3_backend/auth.py)

export default function Register() {
  const { user, loading, signUp } = useAuth()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const next = safeNext(params.get('next'))
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!loading && user) return <Navigate to={next} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (password.length < MIN_PASSWORD) return setError(`Use a password of at least ${MIN_PASSWORD} characters.`)
    if (password !== confirm) return setError('The two passwords do not match.')
    setBusy(true)
    try {
      const u = await signUp(name, email, password)
      toast.success(`Account created. Welcome, ${u.name}.`)
      navigate(next, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create the account. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title="Create an account">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <FormError message={error} />
        <Field id="name" label="Name" autoComplete="name" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
        <Field
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          required
          maxLength={254}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Field
          id="password"
          label="Password"
          type="password"
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD}
          maxLength={128}
          hint={`At least ${MIN_PASSWORD} characters. A short phrase is easier to remember and harder to guess.`}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Field
          id="confirm"
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        <Button type="submit" className="w-full" disabled={busy || !name.trim() || !email || !password || !confirm}>
          {busy ? 'Creating account…' : 'Create account'}
        </Button>
      </form>
      <p className="mt-5 border-t border-rule pt-4 text-[14px] text-muted">
        Already have an account?{' '}
        <Link to={`/login?next=${encodeURIComponent(next)}`} className="text-navy underline underline-offset-4">
          Sign in
        </Link>
        . Your checks are stored on the server and only you can see them.
      </p>
    </AuthCard>
  )
}
