"use client"

import { useState, useEffect, useMemo } from "react"
import { api } from "@/lib/api"
import type { BatchSignalResult } from "@/lib/api"

// ── Compact signal badge for tables ─────────────────────

export type SignalSummary = {
  count: number
  bestAction: string | null   // "buy" | "watch" | null
  bestConfidence: number
  bestTier: string | null
  bestStrategy: string | null
  bestRR: number | null
}

function summarize(signals: BatchSignalResult[]): SignalSummary {
  if (signals.length === 0) {
    return { count: 0, bestAction: null, bestConfidence: 0, bestTier: null, bestStrategy: null, bestRR: null }
  }
  // Prioritize buy signals, then by confidence
  const buys = signals.filter(s => s.action === "buy")
  const best = buys.length > 0
    ? buys.reduce((a, b) => a.confidence > b.confidence ? a : b)
    : signals.reduce((a, b) => a.confidence > b.confidence ? a : b)

  return {
    count: buys.length,
    bestAction: best.action,
    bestConfidence: best.confidence,
    bestTier: best.position_tier,
    bestStrategy: best.strategy_name,
    bestRR: best.rr_ratio,
  }
}

const STRATEGY_SHORT: Record<string, string> = {
  explosion_scanner: "EXP",
  momentum_breakout: "MOM",
  smc_v2: "SMC",
}

const STRATEGY_COLOR: Record<string, string> = {
  explosion_scanner: "bg-cyan-100 text-cyan-700",
  momentum_breakout: "bg-amber-100 text-amber-700",
  smc_v2: "bg-indigo-100 text-indigo-700",
}

// ── Provider: fetches batch signals once, provides lookup ─

type SignalMap = Record<string, BatchSignalResult[]>

export function useBatchSignals() {
  const [signalMap, setSignalMap] = useState<SignalMap>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        // Fetch explosion + momentum for US + TW in parallel (skip SMC — too slow)
        const [expUS, momUS, expTW, momTW] = await Promise.allSettled([
          api.batchSignals("explosion_scanner", "US"),
          api.batchSignals("momentum_breakout", "US"),
          api.batchSignals("explosion_scanner", "TW"),
          api.batchSignals("momentum_breakout", "TW"),
        ])

        if (cancelled) return

        const map: SignalMap = {}
        const allResults: BatchSignalResult[] = []

        if (expUS.status === "fulfilled") allResults.push(...expUS.value.results)
        if (momUS.status === "fulfilled") allResults.push(...momUS.value.results)
        if (expTW.status === "fulfilled") allResults.push(...expTW.value.results)
        if (momTW.status === "fulfilled") allResults.push(...momTW.value.results)

        for (const sig of allResults) {
          if (!map[sig.ticker]) map[sig.ticker] = []
          map[sig.ticker].push(sig)
        }

        setSignalMap(map)
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [])

  return { signalMap, loading }
}

// ── Inline signal cell for table rows ───────────────────

export function SignalCell({ ticker, signalMap, loading }: {
  ticker: string
  signalMap: SignalMap
  loading: boolean
}) {
  const summary = useMemo(() => {
    const signals = signalMap[ticker] ?? []
    return summarize(signals)
  }, [ticker, signalMap])

  if (loading) {
    return <span className="inline-block w-12 h-4 rounded bg-slate-100 animate-pulse" />
  }

  if (summary.count === 0) {
    return <span className="text-xs text-slate-300">—</span>
  }

  return (
    <div className="flex items-center gap-1 justify-center flex-wrap">
      {/* Buy count */}
      <span className="inline-flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700">
        BUY {summary.count}
      </span>
      {/* Best strategy */}
      {summary.bestStrategy && (
        <span className={`text-[9px] font-medium px-1 py-0.5 rounded ${STRATEGY_COLOR[summary.bestStrategy] ?? "bg-slate-100 text-slate-500"}`}>
          {STRATEGY_SHORT[summary.bestStrategy] ?? summary.bestStrategy}
        </span>
      )}
      {/* R:R if available */}
      {summary.bestRR != null && summary.bestRR > 0 && (
        <span className={`text-[9px] px-1 py-0.5 rounded ${summary.bestRR >= 2 ? "bg-green-50 text-green-600" : "bg-slate-50 text-slate-500"}`}>
          {summary.bestRR.toFixed(1)}x
        </span>
      )}
    </div>
  )
}
