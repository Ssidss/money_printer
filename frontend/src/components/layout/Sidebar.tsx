"use client"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useAuth } from "@/contexts/AuthContext"

const nav = [
  { href: "/", label: "Dashboard", icon: "📊" },
  { href: "/briefing", label: "開盤簡報", icon: "🔔" },
  { href: "/stocks", label: "股票清單", icon: "📈" },
  { href: "/analysis", label: "系統說明", icon: "📖" },
  { href: "/portfolio", label: "投資組合", icon: "💼" },
  { href: "/backtest", label: "回測 v1", icon: "⏪" },
  { href: "/strategies", label: "策略回測", icon: "🧪" },
  { href: "/scanner", label: "爆擊掃描", icon: "🔥" },
]

export function Sidebar() {
  const path = usePathname()
  const router = useRouter()
  const { user, logout, loading } = useAuth()

  const handleLogout = () => {
    logout()
    router.push("/login")
  }

  // 登入頁不顯示 sidebar
  if (path === "/login") return null

  return (
    <aside className="sticky top-0 h-screen w-56 flex-shrink-0 flex flex-col border-r border-slate-200 bg-white">
      <div className="p-5 border-b border-slate-200">
        <span className="text-lg font-bold text-slate-800">Money Printer</span>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {nav.map((item) => {
          const active = path === item.href
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-indigo-50 text-indigo-600 font-medium"
                  : "text-slate-500 hover:text-slate-800 hover:bg-slate-100"
              }`}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          )
        })}
      </nav>

      {/* User info + Logout */}
      <div className="p-4 border-t border-slate-200">
        {loading ? (
          <div className="text-xs text-slate-400">載入中...</div>
        ) : user ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-xs font-bold">
                {user.display_name[0]}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-700 truncate">{user.display_name}</p>
                <p className="text-xs text-slate-400 truncate">{user.email}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="w-full text-xs text-slate-400 hover:text-red-500 transition-colors text-left"
            >
              登出
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className="block text-sm text-indigo-600 hover:text-indigo-800 font-medium"
          >
            登入
          </Link>
        )}
      </div>
    </aside>
  )
}
