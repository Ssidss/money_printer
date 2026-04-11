"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { api, SSE_URL } from "@/lib/api"
import type {
  BacktestV3RunReq, BacktestV3Status, BacktestV3Report,
  BacktestV3Summary, BacktestV3Metadata, BacktestV3Split,
  BacktestV3TierBreakdown,
} from "@/lib/api"

// ── Metric Card ─────────────────────────────────────────
function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="text-center">
      <div className={`text-lg font-bold ${color ?? "text-slate-800"}`}>{value}</div>
      <div className="text-xs text-slate-400 mt-0.5">{label}</div>
    </div>
  )
}

function pctColor(v: number) {
  return v > 0 ? "text-green-600" : v < 0 ? "text-red-500" : "text-slate-600"
}

// ── Main Panel ──────────────────────────────────────────
export function BacktestV3Panel() {
  const [splits, setSplits] = useState<BacktestV3Split[]>([])
  const [status, setStatus] = useState<BacktestV3Status | null>(null)
  const [report, setReport] = useState<BacktestV3Report | null>(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState("")
  const [progressPct, setProgressPct] = useState(0)

  // Form state
  const [split, setSplit] = useState("validation")
  const [capital, setCapital] = useState(100000)
  const [minConditions, setMinConditions] = useState(3)
  const [minRR, setMinRR] = useState(2.0)
  const [maxPositions, setMaxPositions] = useState(8)
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>(["smc_v2"])

  const AVAILABLE_STRATEGIES = [
    { value: "smc_v2", label: "SMC v2 (Trend)" },
    { value: "momentum_breakout", label: "Momentum Breakout" },
    { value: "explosion_scanner", label: "Explosion Scanner" },
  ]

  function toggleStrategy(name: string) {
    setSelectedStrategies(prev =>
      prev.includes(name) ? prev.filter(s => s !== name) : [...prev, name]
    )
  }

  // Load initial data
  useEffect(() => {
    api.backtestV3Splits().then(setSplits).catch(() => {})
    api.backtestV3Status().then(s => {
      setStatus(s)
      if (s.has_result && !s.running) {
        api.backtestV3Result().then(setReport).catch(() => {})
      }
    }).catch(() => {})
  }, [])

  // SSE progress listener with cleanup
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    return () => { esRef.current?.close() }
  }, [])

  const listenSSE = useCallback(() => {
    esRef.current?.close()
    const es = new EventSource(SSE_URL)
    esRef.current = es

    const timeout = setTimeout(() => {
      es.close()
      esRef.current = null
      setLoading(false)
      setProgress("逾時，請檢查後端狀態")
    }, 600_000) // 10 min timeout

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.status === "done" || data.status === "error") {
          clearTimeout(timeout)
          es.close()
          esRef.current = null
          setLoading(false)
          if (data.status === "done") {
            api.backtestV3Result().then(setReport).catch(() => {})
          }
          setProgress(data.message || "")
          setProgressPct(100)
        } else {
          setProgress(data.message || "")
          setProgressPct(data.current ?? 0)
        }
      } catch { /* ignore malformed SSE */ }
    }
    es.onerror = () => {
      clearTimeout(timeout)
      es.close()
      esRef.current = null
      setLoading(false)
    }
  }, [])

  async function handleRun() {
    setLoading(true)
    setReport(null)
    setProgress("啟動中...")
    setProgressPct(0)

    const req: BacktestV3RunReq = {
      split,
      initial_capital: capital,
      min_conditions: minConditions,
      min_rr: minRR,
      max_positions: maxPositions,
      strategies: selectedStrategies.length > 0 ? selectedStrategies : ["smc_v2"],
    }

    try {
      await api.backtestV3Run(req)
      listenSSE()
    } catch (e) {
      setLoading(false)
      setProgress(`啟動失敗: ${e}`)
    }
  }

  const s = report?.portfolio_summary
  const meta = report?.metadata
  const breakdown = report?.strategy_breakdown

  return (
    <div className="space-y-6">
      {/* ── Config Panel ─── */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-700 mb-4">V3 Multi-Strategy Engine</h3>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Data Split</label>
            <select
              value={split} onChange={e => setSplit(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              {splits.map(s => (
                <option key={s.name} value={s.name}>
                  {s.name} ({s.start_date} ~ {s.end_date})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">初始資金</label>
            <input type="number" value={capital} onChange={e => setCapital(+e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">最低條件數</label>
            <input type="number" value={minConditions} onChange={e => setMinConditions(+e.target.value)}
              min={1} max={4}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">最低 R:R</label>
            <input type="number" value={minRR} onChange={e => setMinRR(+e.target.value)}
              step={0.1} min={1.0}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">最大持倉數</label>
            <input type="number" value={maxPositions} onChange={e => setMaxPositions(+e.target.value)}
              min={1} max={20}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </div>
        </div>

        {/* Strategy selection */}
        <div className="mb-4">
          <label className="block text-xs text-slate-400 mb-2">策略選擇</label>
          <div className="flex gap-3">
            {AVAILABLE_STRATEGIES.map(st => (
              <label key={st.value} className="flex items-center gap-1.5 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedStrategies.includes(st.value)}
                  onChange={() => toggleStrategy(st.value)}
                  className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className={selectedStrategies.includes(st.value) ? "text-slate-700 font-medium" : "text-slate-400"}>
                  {st.label}
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={handleRun}
            disabled={loading || selectedStrategies.length === 0}
            className="px-6 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "回測中..." : "執行 V3 回測"}
          </button>

          {loading && (
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all duration-300"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
                <span className="text-xs text-slate-500 whitespace-nowrap">{Math.round(progressPct)}%</span>
              </div>
              <p className="text-xs text-slate-400 mt-1">{progress}</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Results ─── */}
      {s && meta && (
        <>
          {/* Summary Cards */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-700">
                Portfolio Summary — {meta.split.toUpperCase()}
              </h3>
              <span className="text-xs text-slate-400">
                {meta.start_date} ~ {meta.end_date} | {meta.trading_days} days | {meta.stock_count} stocks | {meta.duration_seconds}s
              </span>
            </div>

            <div className="grid grid-cols-4 md:grid-cols-7 gap-4">
              <Metric label="Total Return" value={`${s.total_return_pct > 0 ? "+" : ""}${s.total_return_pct.toFixed(2)}%`} color={pctColor(s.total_return_pct)} />
              <Metric label="CAGR" value={`${s.cagr_pct > 0 ? "+" : ""}${s.cagr_pct.toFixed(2)}%`} color={pctColor(s.cagr_pct)} />
              <Metric label="Max DD" value={`${s.max_drawdown_pct.toFixed(2)}%`} color="text-red-500" />
              <Metric label="Sharpe" value={s.sharpe_ratio.toFixed(3)} />
              <Metric label="Sortino" value={s.sortino_ratio.toFixed(3)} />
              <Metric label="Profit Factor" value={s.profit_factor.toFixed(2)} />
              <Metric label="Win Rate" value={`${s.win_rate_pct.toFixed(1)}%`} />
            </div>

            <div className="grid grid-cols-4 md:grid-cols-7 gap-4 mt-4 pt-4 border-t border-slate-100">
              <Metric label="Trades" value={`${s.total_trades}`} />
              <Metric label="Avg Hold" value={`${s.avg_holding_days.toFixed(1)}d`} />
              <Metric label="Expectancy" value={`${s.expectancy.toFixed(3)}`} color={pctColor(s.expectancy)} />
              <Metric label="Avg Win" value={`${s.avg_win_pct.toFixed(2)}%`} color="text-green-600" />
              <Metric label="Avg Loss" value={`${s.avg_loss_pct.toFixed(2)}%`} color="text-red-500" />
              <Metric label="CVaR 5%" value={`${s.tail_risk_cvar_5pct.toFixed(2)}%`} />
              <Metric label="Exposure" value={`${s.avg_exposure_pct.toFixed(1)}%`} />
            </div>
          </div>

          {/* Strategy / Tier / Exit Breakdown */}
          {breakdown && (
            <div className="grid md:grid-cols-3 gap-4">
              {/* By Strategy */}
              <BreakdownCard title="Strategy Breakdown" data={breakdown.by_strategy} type="strategy" />

              {/* By Tier */}
              <BreakdownCard title="Tier Breakdown" data={breakdown.by_tier} type="tier" />

              {/* By Exit Reason */}
              <BreakdownCard title="Exit Reasons" data={breakdown.by_exit_reason} type="exit" />
            </div>
          )}

          {/* Strategy Correlation */}
          {report && (report as any).strategy_correlation?.matrix && Object.keys((report as any).strategy_correlation.matrix).length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h4 className="text-sm font-semibold text-slate-700 mb-3">Strategy Correlation</h4>
              <div className="space-y-2">
                {Object.entries((report as any).strategy_correlation.matrix as Record<string, number>).map(([pair, val]) => (
                  <div key={pair} className="flex items-center justify-between text-sm">
                    <span className="text-slate-600">{pair}</span>
                    <span className={`font-mono font-semibold ${Math.abs(val) > 0.7 ? "text-red-500" : val > 0.3 ? "text-amber-500" : "text-green-600"}`}>
                      {val > 0 ? "+" : ""}{val.toFixed(3)}
                      {Math.abs(val) > 0.7 && " (high)"}
                    </span>
                  </div>
                ))}
              </div>
              {((report as any).strategy_correlation.warnings as string[])?.length > 0 && (
                <div className="mt-2 text-xs text-amber-600">
                  {((report as any).strategy_correlation.warnings as string[]).map((w, i) => (
                    <div key={i}>{w}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Kill Switch / Order Stats */}
          {report && (
            <div className="grid md:grid-cols-2 gap-4">
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <h4 className="text-sm font-semibold text-slate-700 mb-3">Order Stats</h4>
                <div className="flex gap-6 text-sm">
                  <div><span className="text-slate-400">Total:</span> {report.order_stats.total}</div>
                  <div><span className="text-slate-400">Filled:</span> <span className="text-green-600">{report.order_stats.filled}</span></div>
                  <div><span className="text-slate-400">Cancelled:</span> <span className="text-red-500">{report.order_stats.cancelled}</span></div>
                </div>
                {Object.keys(report.order_stats.cancel_reasons).length > 0 && (
                  <div className="mt-2 text-xs text-slate-400">
                    {Object.entries(report.order_stats.cancel_reasons).map(([k, v]) => (
                      <span key={k} className="mr-3">{k}: {v}</span>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <h4 className="text-sm font-semibold text-slate-700 mb-3">Kill Switch</h4>
                {report.kill_switch.triggered ? (
                  <div className="text-sm text-red-600">
                    Triggered on {report.kill_switch.date}: {report.kill_switch.reason}
                  </div>
                ) : (
                  <div className="text-sm text-green-600">Not triggered</div>
                )}
                {report.open_positions.length > 0 && (
                  <div className="mt-2 text-xs text-slate-400">
                    {report.open_positions.length} open positions at end
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Breakdown Card ──────────────────────────────────────
function BreakdownCard({ title, data, type }: {
  title: string
  data: Record<string, Record<string, number>>
  type: "strategy" | "tier" | "exit"
}) {
  const entries = Object.entries(data)
  if (entries.length === 0) return null

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h4 className="text-sm font-semibold text-slate-700 mb-3">{title}</h4>
      <div className="space-y-2">
        {entries.map(([name, stats]) => (
          <div key={name} className="flex items-center justify-between text-sm">
            <span className="text-slate-600 font-medium">{name}</span>
            <div className="flex gap-3 text-xs text-slate-500">
              {type === "exit" ? (
                <>
                  <span>{(stats as Record<string, number>).count ?? stats.total_trades} trades</span>
                  <span className={pctColor(stats.avg_pnl_pct)}>
                    avg {stats.avg_pnl_pct > 0 ? "+" : ""}{stats.avg_pnl_pct.toFixed(2)}%
                  </span>
                </>
              ) : (
                <>
                  <span>{stats.total_trades} trades</span>
                  <span>WR {stats.win_rate_pct?.toFixed(1) ?? "-"}%</span>
                  <span>PF {stats.profit_factor?.toFixed(2) ?? "-"}</span>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
