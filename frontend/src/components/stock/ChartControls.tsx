"use client"

import { useState, useEffect, useCallback } from "react"
import { api } from "@/lib/api"
import { StockChart } from "./StockChart"
import type { PriceBar, SmcData } from "@/lib/api"

type Timeframe = "daily" | "weekly" | "monthly"

const TF_OPTIONS: { value: Timeframe; label: string }[] = [
  { value: "daily", label: "日線" },
  { value: "weekly", label: "週線" },
  { value: "monthly", label: "月線" },
]

const PERIOD_OPTIONS = [
  { label: "3M", days: 60 },
  { label: "6M", days: 120 },
  { label: "1Y", days: 250 },
  { label: "2Y", days: 500 },
  { label: "5Y", days: 1260 },
  { label: "全部", days: 9999 },
]

export function ChartControls({
  ticker,
  initialBars,
  initialSmc,
}: {
  ticker: string
  initialBars: PriceBar[]
  initialSmc: SmcData | null
}) {
  const [timeframe, setTimeframe] = useState<Timeframe>("daily")
  const [period, setPeriod] = useState(120)
  const [bars, setBars] = useState(initialBars)
  const [smc, setSmc] = useState(initialSmc)
  const [loading, setLoading] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)

  useEffect(() => {
    if (timeframe === "daily" && period === 120) {
      setBars(initialBars)
      setSmc(initialSmc)
      return
    }

    let cancelled = false
    setLoading(true)

    const load = async () => {
      try {
        const [newBars, newSmc] = await Promise.allSettled([
          api.stockPrices(ticker, period, timeframe),
          api.stockSmc(ticker, period, timeframe),
        ])
        if (cancelled) return
        setBars(newBars.status === "fulfilled" ? newBars.value : [])
        setSmc(newSmc.status === "fulfilled" ? newSmc.value : null)
      } catch {
        // keep existing data
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [ticker, timeframe, period, initialBars, initialSmc])

  // ESC to exit fullscreen
  useEffect(() => {
    if (!fullscreen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFullscreen(false)
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [fullscreen])

  // Lock body scroll when fullscreen
  useEffect(() => {
    if (fullscreen) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = ""
    }
    return () => { document.body.style.overflow = "" }
  }, [fullscreen])

  const tfLabel = timeframe === "daily" ? "日線" : timeframe === "weekly" ? "週線" : "月線"

  const controlBar = (
    <div className="px-4 pt-3 pb-2 border-b border-slate-100 flex items-center gap-3 flex-wrap">
      {/* Timeframe tabs */}
      <div className="flex rounded-lg border border-slate-200 overflow-hidden">
        {TF_OPTIONS.map((tf) => (
          <button
            key={tf.value}
            onClick={() => setTimeframe(tf.value)}
            className={`px-3 py-1 text-xs font-medium transition-colors ${
              timeframe === tf.value
                ? "bg-indigo-600 text-white"
                : "bg-white text-slate-500 hover:bg-slate-50"
            }`}
          >
            {tf.label}
          </button>
        ))}
      </div>

      {/* Period tabs */}
      <div className="flex gap-1">
        {PERIOD_OPTIONS.map((p) => (
          <button
            key={p.days}
            onClick={() => setPeriod(p.days)}
            className={`px-2 py-1 text-xs rounded font-medium transition-colors ${
              period === p.days
                ? "bg-slate-700 text-white"
                : "text-slate-400 hover:text-slate-600 hover:bg-slate-100"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {loading && (
        <span className="text-xs text-slate-400 animate-pulse">載入中...</span>
      )}

      {/* SMC legend */}
      {smc && (
        <div className="ml-auto flex items-center gap-3 text-xs text-slate-400">
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-green-500 inline-block" /> OB多</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-red-500 inline-block" /> OB空</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-indigo-500 border-dashed border-t border-indigo-500 inline-block" /> FVG</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-amber-400 inline-block" /> POC</span>
          <span className="text-slate-300 mx-1">|</span>
          <span>{tfLabel} · {bars.length} 根</span>
        </div>
      )}

      {!smc && (
        <span className="ml-auto text-xs text-slate-400">
          {tfLabel} · {bars.length} 根 K 棒
        </span>
      )}

      {/* Fullscreen button */}
      <button
        onClick={() => setFullscreen(!fullscreen)}
        className="text-xs px-2 py-1 rounded border border-slate-200 text-slate-500 hover:bg-slate-50 hover:border-slate-300 transition-colors"
        title={fullscreen ? "退出全螢幕 (ESC)" : "全螢幕"}
      >
        {fullscreen ? "✕ 退出" : "⛶ 放大"}
      </button>
    </div>
  )

  // Fullscreen overlay
  if (fullscreen) {
    return (
      <>
        {/* Normal placeholder to keep layout */}
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden" style={{ height: 540 }}>
          <div className="flex items-center justify-center h-full text-slate-400 text-sm">
            圖表已放大顯示中... 按 ESC 退出
          </div>
        </div>

        {/* Fullscreen overlay */}
        <div className="fixed inset-0 z-50 bg-white flex flex-col">
          {controlBar}
          <div className="flex-1 min-h-0">
            <StockChart
              bars={bars}
              smc={smc}
              height="100%"
            />
          </div>
        </div>
      </>
    )
  }

  // Normal mode
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {controlBar}
      <StockChart
        bars={bars}
        smc={smc}
        height={400}
      />
    </div>
  )
}
