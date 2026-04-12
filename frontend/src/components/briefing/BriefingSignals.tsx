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

const TIER_BADGE: Record<string, string> = {
  "核心": "bg-purple-100 text-purple-700 font-bold",
  "標準": "bg-blue-100 text-blue-700 font-semibold",
  "探索": "bg-slate-100 text-slate-600",
}

/**
 * Briefing 頁面的策略信號速覽 — client component
 * 載入 batch signals 後，只顯示 BUY 信號，按 confidence 排序
 * 分為「高信心」和「觀察」兩組
 */
export function BriefingSignals() {
  const { selectedStrategies } = useStrategy()
  const [signals, setSignals] = useState<BatchSignalResult[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      try {
        const strategies = ["explosion_scanner", "momentum_breakout"].filter(
          s => selectedStrategies.includes(s)
        )
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
  }, [selectedStrategies])

  const buySignals = useMemo(() => {
    return signals
      .filter(s => s.action === "buy")
      .sort((a, b) => b.confidence - a.confidence)
  }, [signals])

  // 高信心 = confidence >= 0.6 且 R:R >= 1.5
  const highConf = buySignals.filter(s => s.confidence >= 0.6 && (s.rr_ratio ?? 0) >= 1.5)
  const others = buySignals.filter(s => s.confidence < 0.6 || (s.rr_ratio ?? 0) < 1.5)

  if (loading) {
    return (
      <div className="rounded-xl border-2 border-cyan-200 bg-white p-5 shadow-sm">
        <h2 className="text-base font-bold text-cyan-700 mb-3 flex items-center gap-2">
          <span>🎯</span> 策略信號
        </h2>
        <div className="animate-pulse space-y-2">
          <div className="h-16 rounded bg-slate-100" />
          <div className="h-16 rounded bg-slate-100" />
        </div>
      </div>
    )
  }

  if (buySignals.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-slate-600 mb-1 flex items-center gap-2">
          <span>🎯</span> 策略信號
        </h2>
        <p className="text-xs text-slate-400">目前無活躍買入信號 (Explosion + Momentum)</p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border-2 border-cyan-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-base font-bold text-cyan-700 flex items-center gap-2">
          <span>🎯</span> 策略信號
          <span className="text-xs font-normal px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
            {buySignals.length} BUY
          </span>
        </h2>
        <span className="text-[10px] text-slate-400">Explosion + Momentum (US+TW 即時)</span>
      </div>
      <p className="text-xs text-slate-400 mb-4">多策略引擎即時掃描的買入信號，按信心度排序</p>

      {/* 高信心信號 */}
      {highConf.length > 0 && (
        <div className="mb-4">
          <div className="text-[10px] font-bold text-emerald-600 uppercase tracking-wider mb-2">
            高信心信號 ({highConf.length})
          </div>
          <div className="space-y-2">
            {highConf.slice(0, 8).map(sig => (
              <SignalCard key={sig.signal_id} sig={sig} highlight />
            ))}
          </div>
        </div>
      )}

      {/* 其他信號 */}
      {others.length > 0 && (
        <div>
          <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-2">
            觀察信號 ({others.length})
          </div>
          <div className="space-y-2">
            {others.slice(0, 6).map(sig => (
              <SignalCard key={sig.signal_id} sig={sig} />
            ))}
            {others.length > 6 && (
              <p className="text-[10px] text-slate-400 text-center pt-1">
                還有 {others.length - 6} 個觀察信號...
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function SignalCard({ sig, highlight }: { sig: BatchSignalResult; highlight?: boolean }) {
  const meta = sig.meta ?? {}

  return (
    <div className={`rounded-lg border p-3 ${highlight ? "border-emerald-200 bg-emerald-50/30" : "border-slate-100 bg-white"}`}>
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <Link href={`/stocks/${sig.ticker}`} className="font-bold text-indigo-600 hover:text-indigo-800 hover:underline text-sm">
            {sig.ticker}
          </Link>
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${STRATEGY_COLOR[sig.strategy_name] ?? "bg-slate-100 text-slate-500"}`}>
            {STRATEGY_LABEL[sig.strategy_name] ?? sig.strategy_name}
          </span>
          <span className={`rounded px-1.5 py-0.5 text-[10px] ${TIER_BADGE[sig.position_tier] ?? "bg-slate-100 text-slate-500"}`}>
            {sig.position_tier}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold px-2 py-0.5 rounded ${
            sig.confidence >= 0.7 ? "bg-emerald-100 text-emerald-700"
            : sig.confidence >= 0.5 ? "bg-blue-100 text-blue-700"
            : "bg-slate-100 text-slate-500"
          }`}>
            {(sig.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-3 text-xs">
        <div>
          <span className="text-slate-400">現價</span>
          <p className="font-medium text-slate-700">${sig.current_price?.toFixed(2) ?? "—"}</p>
        </div>
        <div>
          <span className="text-slate-400">進場</span>
          <p className="font-bold text-indigo-600">${sig.entry?.toFixed(2) ?? "—"}</p>
        </div>
        <div>
          <span className="text-slate-400">停損</span>
          <p className="font-medium text-red-500">${sig.stop?.toFixed(2) ?? "—"}</p>
        </div>
        <div>
          <span className="text-slate-400">目標</span>
          <p className="font-medium text-emerald-600">${sig.target?.toFixed(2) ?? "—"}</p>
        </div>
        <div>
          <span className="text-slate-400">R:R</span>
          <p className={`font-bold ${(sig.rr_ratio ?? 0) >= 2 ? "text-emerald-600" : (sig.rr_ratio ?? 0) >= 1.5 ? "text-blue-600" : "text-slate-500"}`}>
            {sig.rr_ratio?.toFixed(1) ?? "—"}x
          </p>
        </div>
      </div>

      {/* Strategy-specific meta tags */}
      {Object.keys(meta).length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {sig.strategy_name === "explosion_scanner" && (
            <>
              {meta.explosion_score != null && (
                <span className="text-[10px] bg-cyan-50 text-cyan-600 px-1.5 py-0.5 rounded">
                  Score: {String(meta.explosion_score)}
                </span>
              )}
              {meta.volume_ratio != null && (
                <span className="text-[10px] bg-cyan-50 text-cyan-600 px-1.5 py-0.5 rounded">
                  Vol: {Number(meta.volume_ratio).toFixed(1)}x
                </span>
              )}
              {meta.is_52w_high && (
                <span className="text-[10px] bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded font-medium">
                  52W High
                </span>
              )}
            </>
          )}
          {sig.strategy_name === "momentum_breakout" && (
            <>
              {meta.breakout_pct != null && (
                <span className="text-[10px] bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded">
                  Breakout: +{Number(meta.breakout_pct).toFixed(1)}%
                </span>
              )}
              {meta.volume_ratio != null && (
                <span className="text-[10px] bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded">
                  Vol: {Number(meta.volume_ratio).toFixed(1)}x
                </span>
              )}
              {meta.rsi_14 != null && (
                <span className="text-[10px] bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded">
                  RSI: {Number(meta.rsi_14).toFixed(0)}
                </span>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
