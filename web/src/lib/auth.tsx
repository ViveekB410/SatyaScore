import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { changePassword, getMe, resetPassword, signIn, signOut, signUp } from './api'
import type { User } from './types'

interface AuthValue {
  user: User | null
  loading: boolean // true until the first /auth/me answer
  signIn: (email: string, password: string) => Promise<User>
  signUp: (name: string, email: string, password: string) => Promise<User>
  signOut: () => Promise<void>
  changePassword: (currentPassword: string, newPassword: string) => Promise<User>
  resetPassword: (email: string, code: string, newPassword: string) => Promise<User>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    getMe()
      .then((u) => !cancelled && setUser(u))
      .catch(() => !cancelled && setUser(null)) // server down: treat as signed out
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  const doSignIn = useCallback(async (email: string, password: string) => {
    const u = await signIn(email, password)
    setUser(u)
    return u
  }, [])

  const doSignUp = useCallback(async (name: string, email: string, password: string) => {
    const u = await signUp(name, email, password)
    setUser(u)
    return u
  }, [])

  const doSignOut = useCallback(async () => {
    try {
      await signOut()
    } finally {
      setUser(null)
    }
  }, [])

  // both sign the user in with a fresh session (the server revokes every other session)
  const doChange = useCallback(async (currentPassword: string, newPassword: string) => {
    const u = await changePassword(currentPassword, newPassword)
    setUser(u)
    return u
  }, [])

  const doReset = useCallback(async (email: string, code: string, newPassword: string) => {
    const u = await resetPassword(email, code, newPassword)
    setUser(u)
    return u
  }, [])

  const value = useMemo(
    () => ({ user, loading, signIn: doSignIn, signUp: doSignUp, signOut: doSignOut,
             changePassword: doChange, resetPassword: doReset }),
    [user, loading, doSignIn, doSignUp, doSignOut, doChange, doReset],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}

/** Only same-app paths are accepted as a post-sign-in destination (no open redirect). */
export function safeNext(next: string | null): string {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/analyse'
}
