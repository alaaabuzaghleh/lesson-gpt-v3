import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { User } from '../types/api'
import { api, setAuthToken } from '../api/client'

interface AuthState {
  user: User | null
  token: string | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isSuperAdmin: boolean
}

const AuthContext = createContext<AuthState | null>(null)
const STORAGE_KEY = 'lessons_gpt_auth'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const applySession = useCallback((accessToken: string, nextUser: User) => {
    setToken(accessToken)
    setUser(nextUser)
    setAuthToken(accessToken)
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: accessToken, user: nextUser }))
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
    setAuthToken(null)
    localStorage.removeItem(STORAGE_KEY)
  }, [])

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      setLoading(false)
      return
    }
    try {
      const saved = JSON.parse(raw) as { token: string; user: User }
      setAuthToken(saved.token)
      api.me()
        .then((me) => applySession(saved.token, me))
        .catch(() => logout())
        .finally(() => setLoading(false))
    } catch {
      logout()
      setLoading(false)
    }
  }, [applySession, logout])

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password)
    applySession(res.access_token, res.user)
  }, [applySession])

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      login,
      logout,
      isSuperAdmin: user?.role === 'super_admin',
    }),
    [user, token, loading, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
