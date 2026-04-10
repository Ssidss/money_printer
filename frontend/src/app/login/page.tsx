"use client"
import { useState } from "react"
import { useAuth } from "@/contexts/AuthContext"
import { useRouter } from "next/navigation"

export default function LoginPage() {
  const { login, register } = useAuth()
  const router = useRouter()
  const [mode, setMode] = useState<"login" | "register">("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      if (mode === "login") {
        await login(email, password)
      } else {
        if (!displayName.trim()) { setError("請輸入顯示名稱"); setLoading(false); return }
        await register(email, password, displayName)
      }
      router.push("/")
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "發生錯誤"
      if (msg.includes("401") || msg.includes("錯誤")) {
        setError("Email 或密碼錯誤")
      } else if (msg.includes("400")) {
        setError("此 Email 已被註冊")
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-8">
          {/* Logo */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-slate-800">Money Printer</h1>
            <p className="text-slate-500 text-sm mt-2">SMC + 趨勢動量分析系統</p>
          </div>

          {/* Tab */}
          <div className="flex mb-6 bg-slate-100 rounded-lg p-1">
            <button
              onClick={() => { setMode("login"); setError("") }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === "login" ? "bg-white text-slate-800 shadow-sm" : "text-slate-500"
              }`}
            >
              登入
            </button>
            <button
              onClick={() => { setMode("register"); setError("") }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === "register" ? "bg-white text-slate-800 shadow-sm" : "text-slate-500"
              }`}
            >
              註冊
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">顯示名稱</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={e => setDisplayName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  placeholder="你的名字"
                />
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">密碼</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="至少 6 個字元"
              />
            </div>

            {error && (
              <div className="text-red-500 text-sm bg-red-50 rounded-lg px-3 py-2">{error}</div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {loading ? "處理中..." : mode === "login" ? "登入" : "註冊"}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
