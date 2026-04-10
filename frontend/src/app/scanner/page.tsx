"use client"

import { useEffect, useState, useCallback } from "react"
import Link from "next/link"
import { api, SSE_URL } from "@/lib/api"
import type { ScanResult, ScanResponse } from "@/lib/api"

const SCORE_COLOR = (s: number) =>
  s >= 60 ? "text-red-600 bg-red-50" :
  s >= 40 ? "text-orange-600 bg-orange-50" :
  s >= 25 ? "text-yellow-600 bg-yellow-50" :
  "text-slate-500 bg-slate-50"

export default function ScannerPage() {
  const [data, setData] = useState<ScanResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [progress, setProgress] = useState("")
  const [filter, setFilter] = useState<"all" | "tracked" | "external">("all")
  const [minScore, setMinScore] = useState(15)

  // 載入最新掃描結果
  const loadLatest = useCallback(async () => {
    try {
      const res = await api.scannerLatest()
      setData(res)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadLatest() }, [loadLatest])

  // SSE 進度監聽
  useEffect(() => {
    if (!scanning) return
    const es = new EventSource(SSE_URL)
    es.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        setProgress(msg.message || "")
        if (msg.phase === "done" || msg.phase === "error") {
          setScanning(false)
          loadLatest()
        }
      } catch { /* ignore */ }
    }
    return () => es.close()
  }, [scanning, loadLatest])

  const handleScan = async (includeExternal: boolean) => {
    setScanning(true)
    setProgress("啟動掃描...")
    try {
      await api.scannerRun(includeExternal, minScore)
    } catch {
      setScanning(false)
      setProgress("啟動失敗")
    }
  }

  const handleQuickScan = async () => {
    setLoading(true)
    try {
      const res = await api.scannerTracked(minScore)
      setData(res)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const results = data?.results ?? []
  const filtered = filter === "all" ? results
    : filter === "tracked" ? results.filter(r => r.market === "US" || r.market === "TW")
    : results

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <span>🔥</span> 量價異常掃描器
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            {data?.scan_date ? `最新掃描：${data.scan_date}（${data.total_count} 支異常）` : "尚未掃描"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleQuickScan}
            disabled={scanning}
            className="px-4 py-2 rounded-lg border border-slate-200 bg-white text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50 transition-colors"
          >
            快速掃描
          </button>
          <button
            onClick={() => handleScan(false)}
            disabled={scanning}
            className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium disabled:opacity-50 transition-colors"
          >
            掃描追蹤股
          </button>
          <button
            onClick={() => handleScan(true)}
            disabled={scanning}
            className="px-4 py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white text-sm font-medium disabled:opacity-50 transition-colors"
          >
            🚀 全市場掃描
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      {scanning && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-center gap-3">
            <div className="animate-spin w-5 h-5 border-2 border-amber-500 border-t-transparent rounded-full" />
            <span className="text-sm text-amber-700">{progress}</span>
          </div>
        </div>
      )}

      {/* Score Legend & Filters */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 text-xs">
          <span className="text-slate-400">爆擊分數：</span>
          <span className="px-2 py-0.5 rounded bg-red-50 text-red-600 font-medium">60+ 極高</span>
          <span className="px-2 py-0.5 rounded bg-orange-50 text-orange-600 font-medium">40-59 高</span>
          <span className="px-2 py-0.5 rounded bg-yellow-50 text-yellow-600 font-medium">25-39 中</span>
          <span className="px-2 py-0.5 rounded bg-slate-50 text-slate-500 font-medium">15-24 低</span>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400">最低分數：</label>
          <input
            type="number"
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-16 px-2 py-1 text-xs border border-slate-200 rounded"
          />
        </div>
      </div>

      {/* Results */}
      {loading ? (
        <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-400">
          載入中...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-400">
          <p className="text-4xl mb-3">🔍</p>
          <p>尚無掃描結果，點擊右上角按鈕開始掃描</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((r, i) => (
            <ScanCard key={r.ticker} result={r} rank={i + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

function ScanCard({ result: r, rank }: { result: ScanResult; rank: number }) {
  const scoreClass = SCORE_COLOR(r.explosion_score)

  return (
    <div className={`rounded-xl border bg-white shadow-sm overflow-hidden transition-all hover:shadow-md ${
      r.explosion_score >= 60 ? "border-red-200 bg-red-50/30" :
      r.explosion_score >= 40 ? "border-orange-200 bg-orange-50/20" :
      "border-slate-200"
    }`}>
      <div className="flex items-stretch">
        {/* Rank + Score */}
        <div className={`flex flex-col items-center justify-center px-5 py-4 ${
          r.explosion_score >= 60 ? "bg-red-100" :
          r.explosion_score >= 40 ? "bg-orange-100" :
          "bg-slate-50"
        }`}>
          <span className="text-xs text-slate-400 font-medium">#{rank}</span>
          <span className={`text-2xl font-bold ${scoreClass.split(" ")[0]}`}>
            {r.explosion_score.toFixed(0)}
          </span>
          <span className="text-[10px] text-slate-400">爆擊分</span>
        </div>

        {/* Main Info */}
        <div className="flex-1 p-4">
          <div className="flex items-center gap-3 mb-2">
            <Link href={`/stocks/${r.ticker}`} className="text-lg font-bold text-indigo-600 hover:text-indigo-800 hover:underline">
              {r.ticker}
            </Link>
            {r.name && <span className="text-sm text-slate-400">{r.name}</span>}
            <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded">{r.market}</span>
            {r.is_52w_high && <span className="text-xs bg-red-500 text-white px-2 py-0.5 rounded font-medium">52W HIGH</span>}
            {r.is_20d_high && !r.is_52w_high && <span className="text-xs bg-amber-500 text-white px-2 py-0.5 rounded font-medium">20D HIGH</span>}
          </div>

          {/* Key Metrics */}
          <div className="grid grid-cols-6 gap-4 mb-3">
            <MetricCell label="收盤" value={`$${r.close_price}`} />
            <MetricCell
              label="漲幅"
              value={`${r.change_pct >= 0 ? "+" : ""}${r.change_pct.toFixed(1)}%`}
              color={r.change_pct >= 5 ? "text-green-600" : r.change_pct >= 0 ? "text-green-500" : "text-red-500"}
            />
            <MetricCell
              label="量比"
              value={`${r.volume_ratio.toFixed(1)}x`}
              color={r.volume_ratio >= 5 ? "text-red-600" : r.volume_ratio >= 3 ? "text-orange-600" : "text-slate-700"}
            />
            <MetricCell label="成交量" value={formatVolume(r.volume)} />
            <MetricCell label="連漲" value={r.consecutive_up_days > 0 ? `${r.consecutive_up_days} 天` : "—"} />
            <MetricCell
              label="累計漲幅"
              value={r.cumulative_gain_pct > 0 ? `+${r.cumulative_gain_pct.toFixed(1)}%` : "—"}
              color={r.cumulative_gain_pct >= 20 ? "text-green-600" : "text-slate-700"}
            />
          </div>

          {/* Signals */}
          {r.signals.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {r.signals.map((s, i) => (
                <span key={i} className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                  {s}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function MetricCell({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <p className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</p>
      <p className={`text-sm font-semibold ${color ?? "text-slate-700"}`}>{value}</p>
    </div>
  )
}

function formatVolume(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`
  return String(v)
}
