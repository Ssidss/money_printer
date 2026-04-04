"use client"

import { useState } from "react"
import { api } from "@/lib/api"

export function StockActions({ ticker }: { ticker: string }) {
  const [loading, setLoading] = useState<"fetch" | "analyze" | null>(null)
  const [msg, setMsg] = useState("")

  const fetchPrices = async () => {
    setLoading("fetch")
    setMsg("")
    try {
      const res = await api.stockFetch(ticker)
      setMsg(`${res.rows_added > 0 ? `新增 ${res.rows_added} 筆股價` : "股價已是最新"}`)
      if (res.rows_added > 0) setTimeout(() => window.location.reload(), 1500)
    } catch {
      setMsg("更新失敗")
    } finally {
      setLoading(null)
    }
  }

  const analyze = async () => {
    setLoading("analyze")
    setMsg("")
    try {
      await api.stockAnalyze(ticker)
      setMsg("分析已啟動，稍後自動更新...")
      setTimeout(() => window.location.reload(), 8000)
    } catch {
      setMsg("分析啟動失敗")
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={fetchPrices}
        disabled={loading !== null}
        className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300 disabled:opacity-40 transition-colors"
      >
        {loading === "fetch" ? "更新中..." : "📥 更新股價"}
      </button>
      <button
        onClick={analyze}
        disabled={loading !== null}
        className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 transition-colors"
      >
        {loading === "analyze" ? "分析中..." : "🔄 重新分析"}
      </button>
      {msg && <span className="text-xs text-slate-500">{msg}</span>}
    </div>
  )
}
