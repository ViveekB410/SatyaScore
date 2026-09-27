import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getMe, signIn, signOut, signUp } from './api'
import type { User } from './types'

interface AuthValue {
  user: User | null
  loading: boolean // true until the first /auth/me answer
  signIn: (email: string, password: string) => Promise<User>
  signUp: (name: string, email: string, password: string) => Promise<User>
  signOut: () => Promise<void>
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

  const value = useMemo(
    () => ({ user, loading, signIn: doSignIn, signUp: doSignUp, signOut: doSignOut }),
    [user, loading, doSignIn, doSignUp, doSignOut],
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
