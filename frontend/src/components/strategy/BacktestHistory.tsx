"use client"

import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import type {
  BacktestV3HistoryItem, BacktestV3HistoryResponse,
  BacktestV3CompareResponse, BacktestV3Report,
} from "@/lib/api"

// ── Metric helpers ──────────────────────────────────────

function pctColor(v: number | null) {
  if (v == null) return "text-slate-400"
  return v > 0 ? "text-emerald-600" : v < 0 ? "text-red-500" : "text-slate-600"
}

function fmt(v: number | null | undefined, decimals = 2, suffix = ""): string {
  if (v == null) return "—"
  return `${v > 0 ? "+" : ""}${v.toFixed(decimals)}${suffix}`
}

function fmtAbs(v: number | null | undefined, decimals = 2, suffix = ""): string {
  if (v == null) return "—"
  return `${v.toFixed(decimals)}${suffix}`
}

// ── Strategy label helper ───────────────────────────────

function strategyLabels(strategies: string[]): string {
  return strategies.map(s =>
    s === "smc_v2" ? "SMC"
    : s === "momentum_breakout" ? "Momentum"
    : s === "explosion_scanner" ? "Explosion"
    : s
  ).join(" + ")
}

// ── Main Component ──────────────────────────────────────

export function BacktestHistory() {
  const [items, setItems] = useState<BacktestV3HistoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  // Compare state
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [comparing, setComparing] = useState(false)
  const [compareData, setCompareData] = useState<BacktestV3CompareResponse | null>(null)

  // Detail state
  const [detailId, setDetailId] = useState<number | null>(null)
  const [detailReport, setDetailReport] = useState<BacktestV3Report | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    loadHistory()
  }, [])

  async function loadHistory() {
    setLoading(true)
    try {
      const res = await api.backtestV3History(50)
      setItems(res.items)
      setTotal(res.total)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  function toggleSelect(id: number) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else if (next.size < 2) {
        next.add(id)
      }
      return next
    })
  }

  async function handleCompare() {
    const ids = Array.from(selected)
    if (ids.length !== 2) return
    setComparing(true)
    setCompareData(null)
    try {
      const res = await api.backtestV3Compare(ids[0], ids[1])
      setCompareData(res)
    } catch {
      // ignore
    } finally {
      setComparing(false)
    }
  }

  async function handleDelete(id: number) {
    try {
      await api.backtestV3HistoryDelete(id)
      setItems(prev => prev.filter(i => i.id !== id))
      setTotal(prev => prev - 1)
      setSelected(prev => { const n = new Set(prev); n.delete(id); return n })
      if (detailId === id) { setDetailId(null); setDetailReport(null) }
      if (compareData && (compareData.a.id === id || compareData.b.id === id)) setCompareData(null)
    } catch {
      // ignore
    }
  }

  async function handleViewDetail(id: number) {
    if (detailId === id) { setDetailId(null); setDetailReport(null); return }
    setDetailId(id)
    setDetailLoading(true)
    try {
      const report = await api.backtestV3HistoryDetail(id)
      setDetailReport(report)
    } catch {
      setDetailReport(null)
    } finally {
      setDetailLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Backtest History</h3>
        <div className="animate-pulse space-y-2">
          <div className="h-10 rounded bg-slate-100" />
          <div className="h-10 rounded bg-slate-100" />
          <div className="h-10 rounded bg-slate-100" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* History List */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-700">
            Backtest History <span className="text-slate-400 font-normal">({total})</span>
          </h3>
          <div className="flex items-center gap-2">
            {selected.size === 2 && (
              <button
                onClick={handleCompare}
                disabled={comparing}
                className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 disabled:opacity-50"
              >
                {comparing ? "比較中..." : "比較選取"}
              </button>
            )}
            {selected.size > 0 && selected.size < 2 && (
              <span className="text-xs text-slate-400">再選 1 筆即可比較</span>
            )}
          </div>
        </div>

        {items.length === 0 ? (
          <p className="text-xs text-slate-400 text-center py-4">尚無歷史回測記錄</p>
        ) : (
          <div className="space-y-1">
            {/* Header */}
            <div className="grid grid-cols-[32px_1fr_100px_80px_80px_80px_80px_70px_80px_60px] gap-1 text-[10px] font-medium text-slate-400 uppercase tracking-wider border-b border-slate-100 pb-1.5">
              <div></div>
              <div>Strategies</div>
              <div>Split</div>
              <div className="text-right">Return</div>
              <div className="text-right">CAGR</div>
              <div className="text-right">MDD</div>
              <div className="text-right">Sharpe</div>
              <div className="text-right">WR</div>
              <div className="text-right">Trades</div>
              <div></div>
            </div>

            {items.map(item => (
              <HistoryRow
                key={item.id}
                item={item}
                isSelected={selected.has(item.id)}
                isDetailOpen={detailId === item.id}
                onToggleSelect={() => toggleSelect(item.id)}
                onViewDetail={() => handleViewDetail(item.id)}
                onDelete={() => handleDelete(item.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Detail Panel */}
      {detailId != null && (
        <DetailPanel
          item={items.find(i => i.id === detailId) ?? null}
          report={detailReport}
          loading={detailLoading}
        />
      )}

      {/* Compare Panel */}
      {compareData && <ComparePanel data={compareData} />}
    </div>
  )
}

// ── History Row ─────────────────────────────────────────

function HistoryRow({
  item, isSelected, isDetailOpen, onToggleSelect, onViewDetail, onDelete,
}: {
  item: BacktestV3HistoryItem
  isSelected: boolean
  isDetailOpen: boolean
  onToggleSelect: () => void
  onViewDetail: () => void
  onDelete: () => void
}) {
  return (
    <div className={`rounded-lg transition-colors ${isSelected ? "bg-indigo-50" : isDetailOpen ? "bg-slate-50" : "hover:bg-slate-50/50"}`}>
      <div className="grid grid-cols-[32px_1fr_100px_80px_80px_80px_80px_70px_80px_60px] gap-1 items-center text-xs py-1.5 px-1">
        <div>
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onToggleSelect}
            className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
          />
        </div>
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-1.5">
            <span className="font-semibold text-slate-800 cursor-pointer hover:text-indigo-600" onClick={onViewDetail}>
              {item.name || strategyLabels(item.strategies)}
            </span>
            {item.strategies.map(s => (
              <span key={s} className={`rounded px-1 py-0.5 text-[9px] font-medium ${
                s === "smc_v2" ? "bg-indigo-100 text-indigo-700"
                : s === "momentum_breakout" ? "bg-amber-100 text-amber-700"
                : "bg-cyan-100 text-cyan-700"
              }`}>
                {s === "smc_v2" ? "SMC" : s === "momentum_breakout" ? "MOM" : "EXP"}
              </span>
            ))}
          </div>
          <span className="text-[10px] text-slate-400">
            {item.created_at ? new Date(item.created_at).toLocaleDateString("zh-TW", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}
          </span>
        </div>
        <div className="text-slate-500">{item.split} ({item.start_date.slice(2)}~{item.end_date.slice(5)})</div>
        <div className={`text-right font-mono font-semibold ${pctColor(item.total_return_pct)}`}>
          {fmt(item.total_return_pct, 1, "%")}
        </div>
        <div className={`text-right font-mono font-semibold ${pctColor(item.cagr_pct)}`}>
          {fmt(item.cagr_pct, 1, "%")}
        </div>
        <div className="text-right font-mono text-red-500">{fmtAbs(item.max_drawdown_pct, 1, "%")}</div>
        <div className="text-right font-mono text-slate-700">{fmtAbs(item.sharpe_ratio, 3)}</div>
        <div className="text-right font-mono text-slate-700">{fmtAbs(item.win_rate_pct, 1, "%")}</div>
        <div className="text-right text-slate-500">{item.total_trades ?? "—"}</div>
        <div className="text-center">
          <button
            onClick={onDelete}
            className="text-slate-300 hover:text-red-500 transition-colors text-xs"
            title="刪除"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Detail Panel ────────────────────────────────────────

function DetailPanel({
  item, report, loading,
}: {
  item: BacktestV3HistoryItem | null
  report: BacktestV3Report | null
  loading: boolean
}) {
  if (!item) return null

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h4 className="text-sm font-semibold text-slate-700 mb-2">載入中...</h4>
        <div className="animate-pulse h-20 rounded bg-slate-100" />
      </div>
    )
  }

  if (!report) return null
  const s = report.portfolio_summary
  const bd = report.strategy_breakdown

  return (
    <div className="rounded-xl border border-indigo-200 bg-white p-5 shadow-sm">
      <h4 className="text-sm font-semibold text-slate-700 mb-3">
        #{item.id} — {item.name || strategyLabels(item.strategies)}
        <span className="text-slate-400 font-normal ml-2">{item.start_date} ~ {item.end_date}</span>
      </h4>

      {/* Key metrics */}
      <div className="grid grid-cols-4 md:grid-cols-7 gap-3 text-center mb-4">
        <MetricCell label="Total Return" value={fmt(s.total_return_pct, 2, "%")} color={pctColor(s.total_return_pct)} />
        <MetricCell label="CAGR" value={fmt(s.cagr_pct, 2, "%")} color={pctColor(s.cagr_pct)} />
        <MetricCell label="Max DD" value={fmtAbs(s.max_drawdown_pct, 2, "%")} color="text-red-500" />
        <MetricCell label="Sharpe" value={fmtAbs(s.sharpe_ratio, 3)} />
        <MetricCell label="Win Rate" value={fmtAbs(s.win_rate_pct, 1, "%")} />
        <MetricCell label="Profit Factor" value={fmtAbs(s.profit_factor, 2)} />
        <MetricCell label="Trades" value={`${s.total_trades}`} />
      </div>

      {/* Strategy breakdown */}
      {bd?.by_strategy && Object.keys(bd.by_strategy).length > 0 && (
        <div className="border-t border-slate-100 pt-3">
          <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-2">By Strategy</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {Object.entries(bd.by_strategy).map(([name, stats]) => (
              <div key={name} className="rounded-lg bg-slate-50 p-2.5 text-xs">
                <div className="font-semibold text-slate-700 mb-1">{name}</div>
                <div className="flex gap-3 text-slate-500">
                  <span>{stats.total_trades} trades</span>
                  <span>WR {stats.win_rate_pct?.toFixed(1)}%</span>
                  <span>PF {stats.profit_factor?.toFixed(2)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Params */}
      <div className="border-t border-slate-100 pt-3 mt-3">
        <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-1.5">Parameters</div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(item.params).map(([k, v]) => (
            <span key={k} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
              {k}: <span className="font-medium">{String(v)}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Compare Panel ───────────────────────────────────────

function ComparePanel({ data }: { data: BacktestV3CompareResponse }) {
  const { a, b, params_diff } = data

  const METRICS: { key: keyof typeof a.metrics; label: string; fmt: (v: number | null) => string; better: "higher" | "lower" }[] = [
    { key: "total_return_pct", label: "Total Return", fmt: v => fmt(v, 2, "%"), better: "higher" },
    { key: "cagr_pct", label: "CAGR", fmt: v => fmt(v, 2, "%"), better: "higher" },
    { key: "max_drawdown_pct", label: "Max DD", fmt: v => fmtAbs(v, 2, "%"), better: "lower" },
    { key: "sharpe_ratio", label: "Sharpe", fmt: v => fmtAbs(v, 3), better: "higher" },
    { key: "sortino_ratio", label: "Sortino", fmt: v => fmtAbs(v, 3), better: "higher" },
    { key: "win_rate_pct", label: "Win Rate", fmt: v => fmtAbs(v, 1, "%"), better: "higher" },
    { key: "profit_factor", label: "Profit Factor", fmt: v => fmtAbs(v, 2), better: "higher" },
    { key: "total_trades", label: "Trades", fmt: v => v != null ? `${v}` : "—", better: "higher" },
    { key: "avg_holding_days", label: "Avg Hold", fmt: v => v != null ? `${v.toFixed(1)}d` : "—", better: "lower" },
    { key: "expectancy", label: "Expectancy", fmt: v => fmtAbs(v, 3), better: "higher" },
    { key: "avg_win_pct", label: "Avg Win", fmt: v => fmt(v, 2, "%"), better: "higher" },
    { key: "avg_loss_pct", label: "Avg Loss", fmt: v => fmtAbs(v, 2, "%"), better: "lower" },
    { key: "tail_risk_cvar_5pct", label: "CVaR 5%", fmt: v => fmtAbs(v, 2, "%"), better: "lower" },
    { key: "avg_exposure_pct", label: "Exposure", fmt: v => fmtAbs(v, 1, "%"), better: "higher" },
  ]

  function betterSide(key: keyof typeof a.metrics, better: "higher" | "lower"): "a" | "b" | "tie" {
    const va = a.metrics[key]
    const vb = b.metrics[key]
    if (va == null || vb == null) return "tie"
    if (va === vb) return "tie"
    if (better === "higher") return va > vb ? "a" : "b"
    return va < vb ? "a" : "b"
  }

  return (
    <div className="rounded-xl border border-indigo-200 bg-white p-5 shadow-sm">
      <h4 className="text-sm font-semibold text-slate-700 mb-4">Strategy Comparison</h4>

      {/* Header */}
      <div className="grid grid-cols-[1fr_1fr_1fr] gap-2 mb-3 text-xs">
        <div className="text-slate-400 font-medium">Metric</div>
        <div className="text-center">
          <div className="font-semibold text-indigo-700">A: #{a.id}</div>
          <div className="text-[10px] text-slate-400">{a.name || strategyLabels(a.strategies)}</div>
        </div>
        <div className="text-center">
          <div className="font-semibold text-amber-700">B: #{b.id}</div>
          <div className="text-[10px] text-slate-400">{b.name || strategyLabels(b.strategies)}</div>
        </div>
      </div>

      {/* Metrics rows */}
      <div className="space-y-0.5">
        {METRICS.map(({ key, label, fmt: fmtFn, better }) => {
          const winner = betterSide(key, better)
          return (
            <div key={key} className="grid grid-cols-[1fr_1fr_1fr] gap-2 text-xs py-1 border-b border-slate-50">
              <div className="text-slate-500">{label}</div>
              <div className={`text-center font-mono ${winner === "a" ? "font-bold text-emerald-600" : "text-slate-700"}`}>
                {fmtFn(a.metrics[key])}
              </div>
              <div className={`text-center font-mono ${winner === "b" ? "font-bold text-emerald-600" : "text-slate-700"}`}>
                {fmtFn(b.metrics[key])}
              </div>
            </div>
          )
        })}
      </div>

      {/* Params diff */}
      {Object.keys(params_diff).length > 0 && (
        <div className="mt-4 pt-3 border-t border-slate-100">
          <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-2">Parameter Differences</div>
          <div className="space-y-1">
            {Object.entries(params_diff).map(([key, diff]) => (
              <div key={key} className="grid grid-cols-[1fr_1fr_1fr] gap-2 text-xs">
                <div className="text-slate-500">{key}</div>
                <div className="text-center font-mono text-indigo-700">{String(diff.a)}</div>
                <div className="text-center font-mono text-amber-700">{String(diff.b)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Small helpers ───────────────────────────────────────

function MetricCell({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div className={`text-sm font-bold ${color ?? "text-slate-800"}`}>{value}</div>
      <div className="text-[10px] text-slate-400 mt-0.5">{label}</div>
    </div>
  )
}
