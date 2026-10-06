import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { AuthCard, Field, FormError } from './Login'

const MIN_PASSWORD = 10 // same rule as the server (member3_backend/auth.py)

/** Forgot password: set a new one with a one-time reset code from the administrator
 * (no email is sent by this deployment; see README "Accounts"). */
export default function ResetPassword() {
  const { resetPassword } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (password.length < MIN_PASSWORD) return setError(`Use a password of at least ${MIN_PASSWORD} characters.`)
    if (password !== confirm) return setError('The two passwords do not match.')
    setBusy(true)
    try {
      const u = await resetPassword(email, code, password)
      toast.success(`Password reset. Welcome back, ${u.name}.`)
      navigate('/analyse', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reset the password. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title="Reset password">
      <p className="-mt-1 mb-4 text-[14px] text-muted">
        Ask the administrator for a one-time reset code. It is valid for 30 minutes and works once.
      </p>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <FormError message={error} />
        <Field id="email" label="Email" type="email" autoComplete="email" required maxLength={254}
               value={email} onChange={(e) => setEmail(e.target.value)} />
        <Field id="code" label="Reset code" autoComplete="one-time-code" required maxLength={64}
               placeholder="e.g. 3F9A1C-0B7D22-9E4410"
               value={code} onChange={(e) => setCode(e.target.value)} />
        <Field id="password" label="New password" type="password" autoComplete="new-password" required
               minLength={MIN_PASSWORD} maxLength={128} hint={`At least ${MIN_PASSWORD} characters.`}
               value={password} onChange={(e) => setPassword(e.target.value)} />
        <Field id="confirm" label="Confirm new password" type="password" autoComplete="new-password" required
               value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        <Button type="submit" className="w-full" disabled={busy || !email || !code || !password || !confirm}>
          {busy ? 'Resetting…' : 'Reset password'}
        </Button>
      </form>
      <p className="mt-5 border-t border-rule pt-4 text-[14px] text-muted">
        Remembered it?{' '}
        <Link to="/login" className="text-navy underline underline-offset-4">
          Sign in
        </Link>
      </p>
    </AuthCard>
  )
}
