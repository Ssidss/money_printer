"use client"

import { useState } from "react"
import { api } from "@/lib/api"
import type { RealtimePrice } from "@/lib/api"

const PERIOD_OPTIONS = [
  { label: "7 天", days: 7 },
  { label: "1 個月", days: 30 },
  { label: "3 個月", days: 90 },
  { label: "6 個月", days: 180 },
  { label: "1 年", days: 365 },
  { label: "2 年", days: 730 },
  { label: "5 年", days: 1825 },
]

export function StockActions({ ticker }: { ticker: string }) {
  const [loading, setLoading] = useState<"fetch" | "analyze" | "realtime" | null>(null)
  const [msg, setMsg] = useState("")
  const [showPeriod, setShowPeriod] = useState(false)
  const [realtime, setRealtime] = useState<RealtimePrice | null>(null)

  const fetchPrices = async (days: number) => {
    setLoading("fetch")
    setMsg("")
    setShowPeriod(false)
    try {
      const res = await api.stockFetch(ticker, days)
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

  const fetchRealtime = async () => {
    setLoading("realtime")
    setMsg("")
    setRealtime(null)
    try {
      const data = await api.realtimePrice(ticker)
      setRealtime(data)
    } catch {
      setMsg("即時報價取得失敗")
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 relative">
        {/* 即時報價 */}
        <button
          onClick={fetchRealtime}
          disabled={loading !== null}
          className="text-xs px-3 py-1.5 rounded-lg border border-amber-200 text-amber-700 bg-amber-50 hover:bg-amber-100 hover:border-amber-300 disabled:opacity-40 transition-colors font-medium"
        >
          {loading === "realtime" ? "查詢中..." : "⚡ 即時報價"}
        </button>

        {/* 更新股價（預設 7 天） */}
        <button
          onClick={() => fetchPrices(7)}
          disabled={loading !== null}
          className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300 disabled:opacity-40 transition-colors"
        >
          {loading === "fetch" ? "更新中..." : "📥 更新股價"}
        </button>

        {/* 自訂時間回補 */}
        <div className="relative">
          <button
            onClick={() => setShowPeriod(!showPeriod)}
            disabled={loading !== null}
            className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 hover:border-slate-300 disabled:opacity-40 transition-colors"
            title="自訂回補時間"
          >
            📅
          </button>
          {showPeriod && (
            <div className="absolute top-full left-0 mt-1 z-50 bg-white border border-slate-200 rounded-xl shadow-lg py-1 min-w-[140px]">
              <div className="px-3 py-1.5 text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                回補歷史股價
              </div>
              {PERIOD_OPTIONS.map((opt) => (
                <button
                  key={opt.days}
                  onClick={() => fetchPrices(opt.days)}
                  className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 transition-colors"
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 重新分析 */}
        <button
          onClick={analyze}
          disabled={loading !== null}
          className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 transition-colors"
        >
          {loading === "analyze" ? "分析中..." : "🔄 重新分析"}
        </button>

        {msg && <span className="text-xs text-slate-500">{msg}</span>}
      </div>

      {/* 即時報價顯示 */}
      {realtime && (
        <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-sm">
          <span className="font-bold text-slate-800">{realtime.price}</span>
          {realtime.change !== null && (
            <span className={`font-medium ${realtime.change >= 0 ? "text-green-600" : "text-red-500"}`}>
              {realtime.change >= 0 ? "+" : ""}{realtime.change}
              ({realtime.change_pct >= 0 ? "+" : ""}{realtime.change_pct}%)
            </span>
          )}
          {realtime.open !== null && (
            <span className="text-xs text-slate-400">開 {realtime.open}</span>
          )}
          {realtime.high !== null && realtime.low !== null && (
            <span className="text-xs text-slate-400">高 {realtime.high} / 低 {realtime.low}</span>
          )}
          {realtime.volume !== null && (
            <span className="text-xs text-slate-400">量 {(realtime.volume / 1e6).toFixed(1)}M</span>
          )}
        </div>
      )}
    </div>
  )
}
