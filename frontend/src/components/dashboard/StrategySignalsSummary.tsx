"use client"

import { useState, useEffect, useMemo } from "react"
import Link from "next/link"
import { api } from "@/lib/api"
import type { BatchSignalResult } from "@/lib/api"
import { useStrategy } from "@/contexts/StrategyContext"

const STRATEGY_LABEL: Record<string, string> = {
  explosion_scanner: "Explosion",
  momentum_breakout: "Momentum",
  smc_v2: "SMC",
}

const STRATEGY_COLOR: Record<string, string> = {
  explosion_scanner: "bg-cyan-100 text-cyan-700",
  momentum_breakout: "bg-amber-100 text-amber-700",
  smc_v2: "bg-indigo-100 text-indigo-700",
}

const TIER_COLOR: Record<string, string> = {
  "核心": "text-purple-600 font-bold",
  "標準": "text-blue-600 font-semibold",
  "探索": "text-slate-500",
}

export function StrategySignalsSummary() {
  const { selectedStrategies, v3 } = useStrategy()
  const [signals, setSignals] = useState<BatchSignalResult[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // If V3 is active, use V3 signals directly
    if (v3.active) {
      setSignals(v3.signals)
      setLoading(v3.loading)
      return
    }

    let cancelled = false

    async function load() {
      setLoading(true)
      try {
        // 只跑 explosion + momentum（SMC 太慢不適合 batch）
        const strategies = ["explosion_scanner", "momentum_breakout"].filter(
          s => selectedStrategies.includes(s)
        )
        // 如果策略面板只選了 SMC，還是跑 explosion 作為預設
        if (strategies.length === 0) strategies.push("explosion_scanner")

        const results = await Promise.allSettled(
          strategies.flatMap(s => [
            api.batchSignals(s, "US"),
            api.batchSignals(s, "TW"),
          ])
        )

        if (cancelled) return

        const all: BatchSignalResult[] = []
        for (const r of results) {
          if (r.status === "fulfilled") all.push(...r.value.results)
        }
        setSignals(all)
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [selectedStrategies, v3.active, v3.signals, v3.loading])

  // Only show buy signals, sorted by confidence desc
  const buySignals = useMemo(() => {
    return signals
      .filter(s => s.action === "buy")
      .sort((a, b) => b.confidence - a.confidence)
  }, [signals])

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">策略信號</h3>
        <div className="animate-pulse space-y-2">
          <div className="h-8 rounded bg-slate-100" />
          <div className="h-8 rounded bg-slate-100" />
          <div className="h-8 rounded bg-slate-100" />
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-700">
          策略信號
          {buySignals.length > 0 && (
            <span className="ml-2 text-xs font-normal px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
              {buySignals.length} BUY
            </span>
          )}
        </h3>
        <span className="text-[10px] text-slate-400">
          {v3.active ? (
            <>
              <span className="inline-flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                V3 {v3.config?.strategies.map(s => s === "smc_v2" ? "SMC" : s === "explosion_scanner" ? "EXP" : "MOM").join("+")}
                {v3.dataDate && ` (${v3.dataDate})`}
              </span>
            </>
          ) : (
            "Explosion + Momentum (US+TW 即時)"
          )}
        </span>
      </div>

      {buySignals.length === 0 ? (
        <p className="text-xs text-slate-400 text-center py-4">目前無活躍買入信號</p>
      ) : (
        <div className="space-y-0.5">
          {/* Header */}
          <div className="grid grid-cols-[1fr_70px_60px_70px_70px_60px_60px] gap-1 text-[10px] font-medium text-slate-400 uppercase tracking-wider border-b border-slate-100 pb-1.5 mb-0.5">
            <div>Ticker</div>
            <div>Strategy</div>
            <div className="text-right">Conf</div>
            <div className="text-right">Entry</div>
            <div className="text-right">Target</div>
            <div className="text-right">R:R</div>
            <div className="text-center">Tier</div>
          </div>

          {buySignals.slice(0, 15).map(sig => (
            <div key={sig.signal_id} className="grid grid-cols-[1fr_70px_60px_70px_70px_60px_60px] gap-1 items-center text-xs py-1 hover:bg-slate-50 rounded transition-colors">
              <div>
                <Link
                  href={`/stocks/${sig.ticker}`}
                  className="font-semibold text-indigo-600 hover:text-indigo-800 hover:underline"
                >
                  {sig.ticker}
                </Link>
                {sig.current_price && (
                  <span className="ml-1 text-[10px] text-slate-400">${sig.current_price.toFixed(2)}</span>
                )}
              </div>
              <div>
                <span className={`rounded px-1 py-0.5 text-[9px] font-medium ${STRATEGY_COLOR[sig.strategy_name] ?? "bg-slate-100 text-slate-500"}`}>
                  {STRATEGY_LABEL[sig.strategy_name] ?? sig.strategy_name}
                </span>
              </div>
              <div className="text-right font-mono text-slate-700">
                {(sig.confidence * 100).toFixed(0)}%
              </div>
              <div className="text-right font-mono text-indigo-600">
                {sig.entry ? `$${sig.entry.toFixed(2)}` : "—"}
              </div>
              <div className="text-right font-mono text-emerald-600">
                {sig.target ? `$${sig.target.toFixed(2)}` : "—"}
              </div>
              <div className={`text-right font-mono ${(sig.rr_ratio ?? 0) >= 2 ? "text-emerald-600 font-semibold" : "text-slate-500"}`}>
                {sig.rr_ratio ? `${sig.rr_ratio.toFixed(1)}x` : "—"}
              </div>
              <div className={`text-center text-[10px] ${TIER_COLOR[sig.position_tier] ?? "text-slate-500"}`}>
                {sig.position_tier}
              </div>
            </div>
          ))}

          {buySignals.length > 15 && (
            <p className="text-[10px] text-slate-400 text-center pt-1">
              還有 {buySignals.length - 15} 個信號...
            </p>
          )}
        </div>
      )}
    </div>
  )
}
