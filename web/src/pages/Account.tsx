import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { AuthCard, Field, FormError } from './Login'

const MIN_PASSWORD = 10 // same rule as the server (member3_backend/auth.py)

/** Change password (signed in). The server signs out every other device. */
export default function Account() {
  const { user, loading, changePassword } = useAuth()
  const [current, setCurrent] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!loading && !user) return <Navigate to="/login?next=/account" replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (password.length < MIN_PASSWORD) return setError(`Use a password of at least ${MIN_PASSWORD} characters.`)
    if (password !== confirm) return setError('The two new passwords do not match.')
    setBusy(true)
    try {
      await changePassword(current, password)
      toast.success('Password changed. Other devices have been signed out.')
      setCurrent('')
      setPassword('')
      setConfirm('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not change the password. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title="Change password">
      {user && (
        <p className="-mt-1 mb-4 text-[14px] text-muted">
          Signed in as <span className="text-ink">{user.email}</span>
        </p>
      )}
      <form onSubmit={submit} className="space-y-4" noValidate>
        <FormError message={error} />
        <Field id="current" label="Current password" type="password" autoComplete="current-password" required
               value={current} onChange={(e) => setCurrent(e.target.value)} />
        <Field id="password" label="New password" type="password" autoComplete="new-password" required
               minLength={MIN_PASSWORD} maxLength={128}
               hint={`At least ${MIN_PASSWORD} characters.`}
               value={password} onChange={(e) => setPassword(e.target.value)} />
        <Field id="confirm" label="Confirm new password" type="password" autoComplete="new-password" required
               value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        <Button type="submit" className="w-full" disabled={busy || !current || !password || !confirm}>
          {busy ? 'Changing…' : 'Change password'}
        </Button>
      </form>
    </AuthCard>
  )
}
