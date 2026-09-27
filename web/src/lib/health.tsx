import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getHealth } from './api'

export type HealthStatus = 'checking' | 'online' | 'offline'

interface HealthState {
  status: HealthStatus
  indexSize: number | null // evidence passages, always from /health, never hardcoded
}

interface HealthContextValue extends HealthState {
  check: () => Promise<boolean>
}

const HealthContext = createContext<HealthContextValue | null>(null)

const RECHECK_MS = 30_000

export function HealthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<HealthState>({ status: 'checking', indexSize: null })

  const check = useCallback(async () => {
    const h = await getHealth()
    if (h) {
      setState({ status: 'online', indexSize: h.index_size })
      return true
    }
    setState((s) => ({ status: 'offline', indexSize: s.indexSize }))
    return false
  }, [])

  // Keep the header pill honest while the app is open.
  useEffect(() => {
    void check()
    const t = setInterval(() => void check(), RECHECK_MS)
    return () => clearInterval(t)
  }, [check])

  const value = useMemo(() => ({ ...state, check }), [state, check])
  return <HealthContext.Provider value={value}>{children}</HealthContext.Provider>
}

export function useHealth(): HealthContextValue {
  const ctx = useContext(HealthContext)
  if (!ctx) throw new Error('useHealth must be used inside HealthProvider')
  return ctx
}
