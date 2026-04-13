"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { api, SSE_URL } from "@/lib/api"
import type {
  BacktestV3RunReq, BacktestV3Status, BacktestV3Report,
  BacktestV3Summary, BacktestV3Metadata, BacktestV3Split,
  BacktestV3TierBreakdown, BacktestV3Trade,
} from "@/lib/api"
import { useStrategy } from "@/contexts/StrategyContext"

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
// Sync backtest results to StrategyContext
function syncMetricsToContext(
  report: BacktestV3Report,
  updateFn: (id: string, m: { cagr: number; sharpe: number; mdd: number; trades: number; winRate: number; profitFactor: number }) => void
) {
  const s = report.portfolio_summary
  const byStrategy = report.strategy_breakdown?.by_strategy
  const strategies = report.metadata?.strategies

  // If single strategy, use portfolio summary
  if (strategies?.length === 1) {
    updateFn(strategies[0], {
      cagr: s.cagr_pct,
      sharpe: s.sharpe_ratio,
      mdd: s.max_drawdown_pct,
      trades: s.total_trades,
      winRate: s.win_rate_pct,
      profitFactor: s.profit_factor,
    })
    return
  }

  // Multi-strategy: only sync trades/WR/PF from per-strategy breakdown.
  // CAGR/Sharpe/MDD are portfolio-level and would be misleading per-strategy.
  // Don't overwrite existing single-strategy metrics with inaccurate data.
  // Users should run single-strategy backtests for accurate per-strategy metrics.
}

export function BacktestV3Panel() {
  const { updateStrategyMetrics, activateV3, deactivateV3, v3 } = useStrategy()
  const [splits, setSplits] = useState<BacktestV3Split[]>([])
  const [status, setStatus] = useState<BacktestV3Status | null>(null)
  const [report, setReport] = useState<BacktestV3Report | null>(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState("")
  const [progressPct, setProgressPct] = useState(0)

  // History selector state
  const [historyItems, setHistoryItems] = useState<{ id: number; label: string; strategies: string[]; params: Record<string, unknown> }[]>([])
  const [selectedHistoryId, setSelectedHistoryId] = useState<number | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [activating, setActivating] = useState(false)

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

  // Load initial data + history list
  useEffect(() => {
    api.backtestV3Splits().then(setSplits).catch(() => {})
    api.backtestV3Status().then(s => {
      setStatus(s)
      if (s.has_result && !s.running) {
        api.backtestV3Result().then(r => {
          setReport(r)
          syncMetricsToContext(r, updateStrategyMetrics)
        }).catch(() => {})
      }
    }).catch(() => {})
    // Load history for selector
    api.backtestV3History(50).then(res => {
      setHistoryItems(res.items.map(i => ({
        id: i.id,
        label: `#${i.id} ${i.name || i.strategies.map(s => s === "smc_v2" ? "SMC" : s === "explosion_scanner" ? "Explosion" : s === "momentum_breakout" ? "Momentum" : s).join("+")} — ${i.split} (${i.total_return_pct != null ? (i.total_return_pct > 0 ? "+" : "") + i.total_return_pct.toFixed(1) + "%" : "—"})`,
        strategies: i.strategies,
        params: i.params,
      })))
    }).catch(() => {})
  }, [])

  // Load history report when selected
  async function handleHistorySelect(id: number) {
    if (id === selectedHistoryId) return
    setSelectedHistoryId(id)
    setHistoryLoading(true)
    try {
      const r = await api.backtestV3HistoryDetail(id)
      setReport(r)
      syncMetricsToContext(r, updateStrategyMetrics)
    } catch { /* ignore */ }
    finally { setHistoryLoading(false) }
  }

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
            api.backtestV3Result().then(r => {
              setReport(r)
              setSelectedHistoryId(null)
              syncMetricsToContext(r, updateStrategyMetrics)
            }).catch(() => {})
            // Refresh history list
            api.backtestV3History(50).then(res => {
              setHistoryItems(res.items.map(i => ({
                id: i.id,
                label: `#${i.id} ${i.name || i.strategies.map(s => s === "smc_v2" ? "SMC" : s === "explosion_scanner" ? "Explosion" : s === "momentum_breakout" ? "Momentum" : s).join("+")} — ${i.split} (${i.total_return_pct != null ? (i.total_return_pct > 0 ? "+" : "") + i.total_return_pct.toFixed(1) + "%" : "—"})`,
                strategies: i.strategies,
                params: i.params,
              })))
            }).catch(() => {})
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

  async function handleActivate() {
    setActivating(true)
    try {
      if (selectedHistoryId) {
        // Activate from history result
        await activateV3(selectedHistoryId)
      } else if (meta) {
        // Activate from current report's params
        await activateV3(undefined, {
          strategies: meta.strategies,
          min_conditions: meta.min_conditions,
          min_rr: meta.min_rr,
          market_filter: "US",
        })
      } else {
        // Activate from form params
        await activateV3(undefined, {
          strategies: selectedStrategies.length > 0 ? selectedStrategies : ["smc_v2"],
          min_conditions: minConditions,
          min_rr: minRR,
          market_filter: "US",
        })
      }
    } catch (e) {
      console.error("Activation failed:", e)
    } finally {
      setActivating(false)
    }
  }

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

        {/* History selector */}
        {historyItems.length > 0 && (
          <div className="mb-4 p-3 bg-slate-50 rounded-lg border border-slate-100">
            <label className="block text-xs text-slate-400 mb-1.5">載入歷史回測結果</label>
            <div className="flex items-center gap-3">
              <select
                value={selectedHistoryId ?? ""}
                onChange={e => {
                  const v = e.target.value
                  if (v) handleHistorySelect(Number(v))
                }}
                className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm bg-white"
              >
                <option value="">— 選擇歷史結果 ({historyItems.length} 筆) —</option>
                {historyItems.map(h => (
                  <option key={h.id} value={h.id}>{h.label}</option>
                ))}
              </select>
              {historyLoading && <span className="text-xs text-slate-400 animate-pulse">載入中...</span>}
              {selectedHistoryId && !historyLoading && (
                <button
                  onClick={() => { setSelectedHistoryId(null); setReport(null) }}
                  className="text-xs text-slate-400 hover:text-red-500"
                >
                  清除
                </button>
              )}
            </div>
          </div>
        )}

        {/* V3 Active Status Banner */}
        {v3.active && (
          <div className="mb-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-sm font-medium text-emerald-700">
                V3 配置已啟動
              </span>
              {v3.config && (
                <span className="text-xs text-emerald-600">
                  {v3.config.strategies.map(s => s === "smc_v2" ? "SMC" : s === "explosion_scanner" ? "Explosion" : s === "momentum_breakout" ? "Momentum" : s).join("+")}
                  {" | "}min_cond={v3.config.params.min_conditions}, min_rr={v3.config.params.min_rr}
                  {v3.config.backtest_name && ` | ${v3.config.backtest_name}`}
                  {" | "}{v3.buyCount} BUY signals
                </span>
              )}
            </div>
            <button
              onClick={deactivateV3}
              className="text-xs text-red-500 hover:text-red-700 font-medium"
            >
              停用
            </button>
          </div>
        )}

        <div className="flex items-center gap-4">
          <button
            onClick={handleRun}
            disabled={loading || selectedStrategies.length === 0}
            className="px-6 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "回測中..." : "執行 V3 回測"}
          </button>

          <button
            onClick={handleActivate}
            disabled={activating || loading}
            className="px-5 py-2.5 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors"
          >
            {activating ? "啟動中..." : v3.active ? "重新啟動配置" : "啟動此配置"}
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

          {/* Trade Log with expandable details */}
          {report && report.trade_log.length > 0 && (
            <TradeLog trades={report.trade_log} />
          )}
        </>
      )}
    </div>
  )
}

// ── Trade Log ──────────────────────────────────────────
function TradeLog({ trades }: { trades: BacktestV3Trade[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [filter, setFilter] = useState<{ strategy: string; result: string }>({
    strategy: "all",
    result: "all",
  })
  const [sortBy, setSortBy] = useState<"date" | "pnl" | "holding">("date")
  const [sortAsc, setSortAsc] = useState(false)
  const [showCount, setShowCount] = useState(20)

  const toggle = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // Get unique strategies for filter
  const strategies = Array.from(new Set(trades.map(t => t.strategy_name)))

  // Filter
  let filtered = trades
  if (filter.strategy !== "all") filtered = filtered.filter(t => t.strategy_name === filter.strategy)
  if (filter.result === "win") filtered = filtered.filter(t => (t.net_pnl ?? 0) > 0)
  if (filter.result === "loss") filtered = filtered.filter(t => (t.net_pnl ?? 0) <= 0)

  // Sort
  filtered = [...filtered].sort((a, b) => {
    let cmp = 0
    if (sortBy === "date") cmp = a.entry_date.localeCompare(b.entry_date)
    else if (sortBy === "pnl") cmp = (a.pnl_pct ?? 0) - (b.pnl_pct ?? 0)
    else if (sortBy === "holding") cmp = a.holding_days - b.holding_days
    return sortAsc ? cmp : -cmp
  })

  const visible = filtered.slice(0, showCount)

  function handleSort(col: "date" | "pnl" | "holding") {
    if (sortBy === col) setSortAsc(!sortAsc)
    else { setSortBy(col); setSortAsc(false) }
  }

  const sortIcon = (col: string) =>
    sortBy === col ? (sortAsc ? " ↑" : " ↓") : ""

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-slate-700">
          Trade Log <span className="text-slate-400 font-normal">({filtered.length} trades)</span>
        </h4>
        <div className="flex items-center gap-2">
          <select
            value={filter.strategy}
            onChange={e => setFilter(prev => ({ ...prev, strategy: e.target.value }))}
            className="rounded border border-slate-200 px-2 py-1 text-xs"
          >
            <option value="all">All Strategies</option>
            {strategies.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select
            value={filter.result}
            onChange={e => setFilter(prev => ({ ...prev, result: e.target.value }))}
            className="rounded border border-slate-200 px-2 py-1 text-xs"
          >
            <option value="all">All Results</option>
            <option value="win">Wins</option>
            <option value="loss">Losses</option>
          </select>
        </div>
      </div>

      {/* Table header */}
      <div className="grid grid-cols-[1fr_80px_80px_80px_70px_80px_70px_32px] gap-1 text-[10px] font-medium text-slate-400 uppercase tracking-wider border-b border-slate-100 pb-1.5 mb-1">
        <div>Ticker</div>
        <div className="cursor-pointer hover:text-slate-600" onClick={() => handleSort("date")}>
          Entry{sortIcon("date")}
        </div>
        <div>Exit</div>
        <div>Strategy</div>
        <div>Tier</div>
        <div className="cursor-pointer hover:text-slate-600 text-right" onClick={() => handleSort("pnl")}>
          P&L{sortIcon("pnl")}
        </div>
        <div className="cursor-pointer hover:text-slate-600 text-right" onClick={() => handleSort("holding")}>
          Days{sortIcon("holding")}
        </div>
        <div></div>
      </div>

      {/* Trade rows */}
      <div className="space-y-0.5">
        {visible.map(t => (
          <TradeRow key={t.position_id} trade={t} isOpen={expanded.has(t.position_id)} onToggle={() => toggle(t.position_id)} />
        ))}
      </div>

      {/* Show more */}
      {showCount < filtered.length && (
        <button
          onClick={() => setShowCount(prev => prev + 20)}
          className="mt-3 w-full text-center text-xs text-indigo-600 hover:text-indigo-800 py-1.5"
        >
          Show more ({filtered.length - showCount} remaining)
        </button>
      )}
    </div>
  )
}

function TradeRow({ trade: t, isOpen, onToggle }: { trade: BacktestV3Trade; isOpen: boolean; onToggle: () => void }) {
  const pnlColor = (t.net_pnl ?? 0) > 0 ? "text-emerald-600" : (t.net_pnl ?? 0) < 0 ? "text-red-500" : "text-slate-500"
  const meta = t.signal_meta?.meta ?? {}
  const ph = t.signal_meta?.price_hint

  const strategyLabel =
    t.strategy_name === "explosion_scanner" ? "Explosion"
    : t.strategy_name === "momentum_breakout" ? "Momentum"
    : t.strategy_name === "smc_v2" ? "SMC"
    : t.strategy_name

  const tierColor =
    t.position_tier === "核心" ? "bg-purple-100 text-purple-700"
    : t.position_tier === "標準" ? "bg-blue-100 text-blue-700"
    : "bg-slate-100 text-slate-600"

  const exitLabel =
    t.exit_reason === "stop_loss" ? "止損"
    : t.exit_reason === "take_profit" ? "止盈"
    : t.exit_reason === "trailing_stop" ? "追蹤止損"
    : t.exit_reason === "time_exit" ? "時間到期"
    : t.exit_reason === "signal_reversal" ? "反轉信號"
    : t.exit_reason ?? "open"

  return (
    <div className={`rounded-lg transition-colors ${isOpen ? "bg-slate-50" : "hover:bg-slate-50/50"}`}>
      {/* Summary row */}
      <div
        className="grid grid-cols-[1fr_80px_80px_80px_70px_80px_70px_32px] gap-1 items-center text-xs py-1.5 px-1 cursor-pointer"
        onClick={onToggle}
      >
        <div className="font-semibold text-slate-800">{t.ticker}</div>
        <div className="text-slate-500">{t.entry_date.slice(5)}</div>
        <div className="text-slate-500">{t.exit_date?.slice(5) ?? "—"}</div>
        <div>
          <span className={`rounded px-1 py-0.5 text-[10px] font-medium ${
            t.strategy_name === "smc_v2" ? "bg-indigo-100 text-indigo-700"
            : t.strategy_name === "momentum_breakout" ? "bg-amber-100 text-amber-700"
            : "bg-cyan-100 text-cyan-700"
          }`}>
            {strategyLabel}
          </span>
        </div>
        <div>
          <span className={`rounded px-1 py-0.5 text-[10px] font-medium ${tierColor}`}>
            {t.position_tier}
          </span>
        </div>
        <div className={`text-right font-mono font-semibold ${pnlColor}`}>
          {(t.pnl_pct ?? 0) > 0 ? "+" : ""}{(t.pnl_pct ?? 0).toFixed(2)}%
        </div>
        <div className="text-right text-slate-500">{t.holding_days}d</div>
        <div className="text-center text-slate-400">
          {isOpen ? "▲" : "▼"}
        </div>
      </div>

      {/* Expanded detail */}
      {isOpen && (
        <div className="px-2 pb-3 pt-1 border-t border-slate-100">
          {/* Price grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            <DetailCell label="Entry" value={`$${t.entry_price.toFixed(2)}`} />
            <DetailCell label="Exit" value={t.exit_price ? `$${t.exit_price.toFixed(2)}` : "—"} />
            <DetailCell label="Stop" value={t.stop_price ? `$${t.stop_price.toFixed(2)}` : ph?.stop ? `$${ph.stop.toFixed(2)}` : "—"} color="text-red-500" />
            <DetailCell label="Target" value={t.target_price ? `$${t.target_price.toFixed(2)}` : ph?.target ? `$${ph.target.toFixed(2)}` : "—"} color="text-emerald-600" />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3">
            <DetailCell label="Shares" value={`${t.size}`} />
            <DetailCell label="Net P&L" value={`$${(t.net_pnl ?? 0).toFixed(2)}`} color={pnlColor} />
            <DetailCell label="R:R" value={ph?.rr_ratio ? ph.rr_ratio.toFixed(2) : "—"} />
            <DetailCell label="MAE" value={`$${t.mae.toFixed(2)}`} color="text-red-500" />
            <DetailCell label="MFE" value={`$${t.mfe.toFixed(2)}`} color="text-emerald-600" />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            <DetailCell label="Exit Reason" value={exitLabel} />
            <DetailCell label="Confidence" value={`${((t.signal_meta?.confidence ?? t.confidence) * 100).toFixed(0)}%`} />
            <DetailCell label="Costs" value={`$${(t.commission + t.slippage_cost).toFixed(2)}`} />
            <DetailCell label="Signal Date" value={t.signal_meta?.timestamp?.slice(5) ?? "—"} />
          </div>

          {/* Strategy-specific explanation */}
          {Object.keys(meta).length > 0 && (
            <div className="mt-2 pt-2 border-t border-slate-100">
              <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-1.5">
                Signal Explanation
              </div>
              <div className="flex flex-wrap gap-1.5">
                {/* SMC-specific */}
                {t.strategy_name === "smc_v2" && (
                  <>
                    {meta.daily_trend && <MetaBadge label="Trend" value={String(meta.daily_trend)} />}
                    {meta.conditions_met != null && <MetaBadge label="Conditions" value={`${meta.conditions_met}/4`} />}
                    {meta.recommendation && <MetaBadge label="Rec" value={String(meta.recommendation)} />}
                    {meta.entry_source && <MetaBadge label="Entry Source" value={String(meta.entry_source)} />}
                    {meta.stop_source && <MetaBadge label="Stop Source" value={String(meta.stop_source)} />}
                    {meta.target_source && <MetaBadge label="Target Source" value={String(meta.target_source)} />}
                    {meta.conditions_detail && (
                      <div className="w-full mt-1 text-[10px] text-slate-500">
                        {Array.isArray(meta.conditions_detail) ? (
                          meta.conditions_detail.map((c: string, i: number) => (
                            <span key={i} className="inline-block mr-2 mb-0.5">
                              <span className="text-emerald-500">✓</span> {c}
                            </span>
                          ))
                        ) : typeof meta.conditions_detail === "string" ? (
                          <span>{meta.conditions_detail}</span>
                        ) : null}
                      </div>
                    )}
                  </>
                )}
                {/* Momentum Breakout */}
                {t.strategy_name === "momentum_breakout" && (
                  <>
                    {meta.breakout_pct != null && <MetaBadge label="Breakout" value={`+${Number(meta.breakout_pct).toFixed(1)}%`} />}
                    {meta.n_day_high != null && <MetaBadge label="N-Day High" value={`$${Number(meta.n_day_high).toFixed(2)}`} />}
                    {meta.volume_ratio != null && <MetaBadge label="Vol Ratio" value={`${Number(meta.volume_ratio).toFixed(1)}x`} />}
                    {meta.rsi_14 != null && <MetaBadge label="RSI(14)" value={Number(meta.rsi_14).toFixed(1)} />}
                    {meta.atr_14 != null && <MetaBadge label="ATR(14)" value={`$${Number(meta.atr_14).toFixed(2)}`} />}
                  </>
                )}
                {/* Explosion Scanner */}
                {t.strategy_name === "explosion_scanner" && (
                  <>
                    {meta.explosion_score != null && <MetaBadge label="Score" value={String(meta.explosion_score)} />}
                    {meta.change_pct != null && <MetaBadge label="Change" value={`${Number(meta.change_pct) > 0 ? "+" : ""}${Number(meta.change_pct).toFixed(1)}%`} />}
                    {meta.volume_ratio != null && <MetaBadge label="Vol Ratio" value={`${Number(meta.volume_ratio).toFixed(1)}x`} />}
                    {meta.consecutive_up_days != null && <MetaBadge label="Up Days" value={`${meta.consecutive_up_days}d`} />}
                    {meta.is_52w_high && <MetaBadge label="52W High" value="✓" highlight />}
                    {meta.is_20d_high && <MetaBadge label="20D High" value="✓" highlight />}
                    {meta.vol_acceleration != null && <MetaBadge label="Vol Accel" value={`${Number(meta.vol_acceleration).toFixed(1)}x`} />}
                  </>
                )}
                {/* Fallback: show raw meta for unknown strategies */}
                {!["smc_v2", "momentum_breakout", "explosion_scanner"].includes(t.strategy_name) && (
                  Object.entries(meta).map(([k, v]) => (
                    <MetaBadge key={k} label={k} value={String(v)} />
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DetailCell({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div className="text-[10px] text-slate-400">{label}</div>
      <div className={`text-xs font-semibold ${color ?? "text-slate-800"}`}>{value}</div>
    </div>
  )
}

function MetaBadge({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] ${
      highlight ? "bg-emerald-100 text-emerald-700 font-medium" : "bg-slate-100 text-slate-600"
    }`}>
      {label}: <span className="font-medium">{value}</span>
    </span>
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
