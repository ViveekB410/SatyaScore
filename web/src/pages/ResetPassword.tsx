import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError, forgotPassword } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { AuthCard, Field, FormError } from './Login'

const MIN_PASSWORD = 10 // same rule as the server (member3_backend/auth.py)

/** Forgot password, in two steps: (1) the email address, to which a 6-digit code is sent;
 * (2) that code and the new password. A code from the administrator works in step 2 too. */
export default function ResetPassword() {
  const { resetPassword } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState<'email' | 'code'>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sentNote, setSentNote] = useState<string | null>(null)

  async function sendCode(e?: FormEvent) {
    e?.preventDefault()
    setError(null)
    setBusy(true)
    try {
      setSentNote(await forgotPassword(email))
      setStep('code')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not send the code. Try again.')
    } finally {
      setBusy(false)
    }
  }

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
      {step === 'email' ? (
        <>
          <p className="-mt-1 mb-4 text-[14px] text-muted">
            Enter the email address of your account. We will send you a 6-digit code to set a new password.
          </p>
          <form onSubmit={sendCode} className="space-y-4" noValidate>
            <FormError message={error} />
            <Field id="email" label="Email" type="email" autoComplete="email" required maxLength={254}
                   value={email} onChange={(e) => setEmail(e.target.value)} />
            <Button type="submit" className="w-full" disabled={busy || !email.trim()}>
              {busy ? 'Sending…' : 'Send code'}
            </Button>
          </form>
          <p className="mt-3 text-[13px] text-muted">
            Already have a code?{' '}
            <button type="button" className="text-navy underline underline-offset-4" onClick={() => { setError(null); setStep('code') }}>
              Enter it
            </button>
          </p>
        </>
      ) : (
        <>
          <p className="-mt-1 mb-4 text-[14px] text-muted">
            {sentNote ?? 'Enter the reset code you received.'} Check your spam folder if it has not arrived.
          </p>
          <form onSubmit={submit} className="space-y-4" noValidate>
            <FormError message={error} />
            <Field id="email" label="Email" type="email" autoComplete="email" required maxLength={254}
                   value={email} onChange={(e) => setEmail(e.target.value)} />
            <Field id="code" label="Reset code" autoComplete="one-time-code" inputMode="numeric" required maxLength={64}
                   placeholder="6-digit code"
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
          <p className="mt-3 text-[13px] text-muted">
            No code?{' '}
            <button type="button" className="text-navy underline underline-offset-4" disabled={busy || !email.trim()}
                    onClick={() => void sendCode()}>
              Send a new one
            </button>
          </p>
        </>
      )}
      <p className="mt-5 border-t border-rule pt-4 text-[14px] text-muted">
        Remembered it?{' '}
        <Link to="/login" className="text-navy underline underline-offset-4">
          Sign in
        </Link>
      </p>
    </AuthCard>
  )
}
