"use client"
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import { api, setToken, clearToken, type AuthUser } from "@/lib/api"

type AuthState = {
  user: AuthUser | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  // 啟動時檢查 localStorage 有沒有 token
  useEffect(() => {
    const token = localStorage.getItem("mp_token")
    if (!token) {
      Promise.resolve().then(() => setLoading(false))
      return
    }
    api.me()
      .then(setUser)
      .catch(() => {
        clearToken()
      })
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password)
    setToken(res.access_token)
    setUser(res.user)
  }, [])

  const register = useCallback(async (email: string, password: string, displayName: string) => {
    const res = await api.register(email, password, displayName)
    setToken(res.access_token)
    setUser(res.user)
  }, [])

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider")
  return ctx
}
