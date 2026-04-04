"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"

const nav = [
  { href: "/", label: "Dashboard", icon: "📊" },
  { href: "/stocks", label: "股票清單", icon: "📈" },
  { href: "/analysis", label: "分析報告", icon: "🔍" },
  { href: "/portfolio", label: "投資組合", icon: "💼" },
  { href: "/backtest", label: "回測", icon: "⏪" },
]

export function Sidebar() {
  const path = usePathname()
  return (
    <aside className="sticky top-0 h-screen w-56 flex-shrink-0 flex flex-col border-r border-slate-200 bg-white">
      <div className="p-5 border-b border-slate-200">
        <span className="text-lg font-bold text-slate-800">💰 Money Printer</span>
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
      <div className="p-4 text-xs text-slate-400 border-t border-slate-200">
        API: localhost:8000
      </div>
    </aside>
  )
}
