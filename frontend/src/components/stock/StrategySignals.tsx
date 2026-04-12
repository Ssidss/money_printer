"use client"

import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import type { LiveSignalResponse, LiveSignal } from "@/lib/api"
import { useStrategy } from "@/contexts/StrategyContext"

// ── Signal Card ─────────────────────────────────────────

function SignalCard({ signal }: { signal: LiveSignal }) {
  const isActive = signal.action === "buy"
  const meta = signal.meta || {}

  return (
    <div
      className={`rounded-lg border p-4 ${
        isActive
          ? "border-emerald-300 bg-emerald-50/50"
          : "border-slate-200 bg-white"
      }`}
    >
      {/* Header: strategy + action */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-800">
            {signal.strategy_name === "explosion_scanner"
              ? "Explosion Scanner"
              : signal.strategy_name === "momentum_breakout"
              ? "Momentum Breakout"
              : signal.strategy_name === "smc_v2"
              ? "SMC v2"
              : signal.strategy_name}
          </span>
          <span
            className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
              signal.strategy_type === "breakout"
                ? "bg-amber-100 text-amber-700"
                : "bg-blue-100 text-blue-700"
            }`}
          >
            {signal.strategy_type}
          </span>
        </div>
        <span
          className={`rounded-md px-2 py-0.5 text-xs font-bold ${
            signal.action === "buy"
              ? "bg-emerald-100 text-emerald-700"
              : signal.action === "sell"
              ? "bg-red-100 text-red-700"
              : "bg-slate-100 text-slate-600"
          }`}
        >
          {signal.action.toUpperCase()}
        </span>
      </div>

      {/* Confidence + Tier */}
      <div className="flex items-center gap-3 mb-3">
        <div className="flex items-center gap-1.5">
          <div className="h-1.5 w-20 rounded-full bg-slate-200 overflow-hidden">
            <div
              className={`h-full rounded-full ${
                signal.confidence >= 0.8
                  ? "bg-emerald-500"
                  : signal.confidence >= 0.6
                  ? "bg-amber-500"
                  : "bg-slate-400"
              }`}
              style={{ width: `${signal.confidence * 100}%` }}
            />
          </div>
          <span className="text-xs text-slate-500">
            {(signal.confidence * 100).toFixed(0)}%
          </span>
        </div>
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
            signal.position_tier === "\u6838\u5fc3"
              ? "bg-purple-100 text-purple-700"
              : signal.position_tier === "\u6a19\u6e96"
              ? "bg-blue-100 text-blue-700"
              : "bg-slate-100 text-slate-600"
          }`}
        >
          {signal.position_tier}
        </span>
      </div>

      {/* Entry / Stop / Target */}
      {signal.entry && signal.stop && signal.target && (
        <div className="grid grid-cols-4 gap-2 text-xs mb-3">
          <div>
            <div className="text-slate-400">Entry</div>
            <div className="font-semibold text-slate-800">${signal.entry.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-slate-400">Stop</div>
            <div className="font-semibold text-red-500">${signal.stop.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-slate-400">Target</div>
            <div className="font-semibold text-emerald-600">${signal.target.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-slate-400">R:R</div>
            <div className="font-semibold text-slate-800">{signal.rr_ratio?.toFixed(2)}</div>
          </div>
        </div>
      )}

      {/* Meta factors */}
      <div className="flex flex-wrap gap-1.5">
        {signal.strategy_name === "explosion_scanner" && (
          <>
            {meta.explosion_score != null && (
              <MetaTag label="Score" value={String(meta.explosion_score)} />
            )}
            {meta.volume_ratio != null && (
              <MetaTag label="Vol" value={`${(meta.volume_ratio as number).toFixed(1)}x`} />
            )}
            {meta.change_pct != null && (
              <MetaTag label="Chg" value={`${(meta.change_pct as number) > 0 ? "+" : ""}${(meta.change_pct as number).toFixed(1)}%`} />
            )}
            {meta.consecutive_up_days != null && (
              <MetaTag label="Up" value={`${meta.consecutive_up_days}d`} />
            )}
          </>
        )}
        {signal.strategy_name === "momentum_breakout" && (
          <>
            {meta.breakout_pct != null && (
              <MetaTag label="Breakout" value={`+${(meta.breakout_pct as number).toFixed(1)}%`} />
            )}
            {meta.volume_ratio != null && (
              <MetaTag label="Vol" value={`${(meta.volume_ratio as number).toFixed(1)}x`} />
            )}
            {meta.rsi_14 != null && (
              <MetaTag label="RSI" value={(meta.rsi_14 as number).toFixed(1)} />
            )}
            {meta.atr_14 != null && (
              <MetaTag label="ATR" value={(meta.atr_14 as number).toFixed(2)} />
            )}
          </>
        )}
      </div>

      {/* Expiry */}
      <div className="mt-2 text-[10px] text-slate-400">
        expires {signal.expiry}
      </div>
    </div>
  )
}

function MetaTag({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
      {label}: <span className="font-medium">{value}</span>
    </span>
  )
}

// ── No Signal state ─────────────────────────────────────

function NoSignal({ strategyName, status }: { strategyName: string; status?: { status: string; message?: string } }) {
  const label =
    strategyName === "explosion_scanner" ? "Explosion Scanner"
    : strategyName === "momentum_breakout" ? "Momentum Breakout"
    : strategyName === "smc_v2" ? "SMC v2"
    : strategyName

  if (status?.status === "error") {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50/50 p-3">
        <span className="text-xs text-red-600">{label}: {status.message || "error"}</span>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-3">
      <span className="text-xs text-slate-400">{label}: no signal</span>
    </div>
  )
}

// ── Main component ──────────────────────────────────────

export function StrategySignals({ ticker }: { ticker: string }) {
  const { primaryStrategy, selectedStrategies, mode } = useStrategy()
  const [data, setData] = useState<LiveSignalResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Determine which strategies to query
  const strategiesToQuery = mode === "single"
    ? [primaryStrategy]
    : selectedStrategies

  // Only include fast strategies by default (exclude smc_v2 from auto-load)
  const fastStrategies = strategiesToQuery.filter(s => s !== "smc_v2")
  const queryStr = fastStrategies.length > 0 ? fastStrategies.join(",") : "explosion_scanner,momentum_breakout"

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    api.liveSignals(ticker, queryStr)
      .then(r => { if (!cancelled) setData(r) })
      .catch(e => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [ticker, queryStr])

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">V3 Strategy Signals</h3>
        <div className="animate-pulse space-y-2">
          <div className="h-20 rounded-lg bg-slate-100" />
          <div className="h-20 rounded-lg bg-slate-100" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-white p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-700 mb-2">V3 Strategy Signals</h3>
        <p className="text-xs text-red-500">{error}</p>
      </div>
    )
  }

  if (!data) return null

  // Build signal map by strategy
  const signalsByStrategy: Record<string, LiveSignal[]> = {}
  for (const s of data.signals) {
    signalsByStrategy[s.strategy_name] = signalsByStrategy[s.strategy_name] || []
    signalsByStrategy[s.strategy_name].push(s)
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-700">V3 Strategy Signals</h3>
        <div className="flex items-center gap-2 text-[10px] text-slate-400">
          <span>data: {data.data_date}</span>
          <span>{data.timing.compute_ms.toFixed(0)}ms</span>
        </div>
      </div>

      <div className="space-y-2">
        {fastStrategies.map(name => {
          const signals = signalsByStrategy[name]
          if (signals && signals.length > 0) {
            return signals.map(s => <SignalCard key={s.signal_id} signal={s} />)
          }
          return (
            <NoSignal
              key={name}
              strategyName={name}
              status={data.strategy_status[name]}
            />
          )
        })}
      </div>

      {data.signal_count === 0 && (
        <p className="mt-2 text-xs text-slate-400 text-center">
          {data.current_price ? `$${data.current_price.toFixed(2)}` : ""} — no active signals
        </p>
      )}
    </div>
  )
}
