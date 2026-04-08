"use client"

import { useState, useEffect } from "react"
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

  useEffect(() => {
    // Skip initial load (already have data)
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
          timeframe === "daily" ? api.stockSmc(ticker, period) : Promise.resolve(null),
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

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Header with controls */}
      <div className="px-4 pt-4 pb-2 border-b border-slate-100 flex items-center gap-3 flex-wrap">
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

        {/* SMC legend (only for daily) */}
        {smc && timeframe === "daily" && (
          <div className="ml-auto flex items-center gap-3 text-xs text-slate-400">
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-green-500 inline-block" /> OB多</span>
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-red-500 inline-block" /> OB空</span>
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-indigo-500 border-dashed border-t border-indigo-500 inline-block" /> FVG</span>
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-amber-400 inline-block" /> POC</span>
          </div>
        )}

        {timeframe !== "daily" && (
          <span className="ml-auto text-xs text-slate-400">
            {timeframe === "weekly" ? "週線" : "月線"} · {bars.length} 根 K 棒
          </span>
        )}
      </div>

      {/* Chart */}
      <StockChart
        bars={bars}
        smc={timeframe === "daily" ? smc : null}
        height={480}
      />
    </div>
  )
}
