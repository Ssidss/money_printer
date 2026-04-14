"use client"

import { useState } from "react"
import Link from "next/link"
import { api, SSE_URL } from "@/lib/api"
import type { StrategyFull, BacktestV2Result, BacktestV2Trade, BacktestV2EquityPoint } from "@/lib/api"

// ── Tab 切換 ────────────────────────────────────────────────────────────────

type Tab = "params" | "backtest" | "trades"

export function StrategyDetail({
  strategy: initialStrategy,
  backtestResults: initialResults,
}: {
  strategy: StrategyFull
  backtestResults: BacktestV2Result[]
}) {
  const [strategy, setStrategy] = useState(initialStrategy)
  const [results, setResults] = useState(initialResults)
  const [tab, setTab] = useState<Tab>("backtest")
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState("")
  const [selectedResult, setSelectedResult] = useState<BacktestV2Result | null>(
    initialResults.find(r => r.status === "done") ?? null
  )
  const [trades, setTrades] = useState<BacktestV2Trade[]>([])
  const [equity, setEquity] = useState<BacktestV2EquityPoint[]>([])

  // ── Run Backtest ──
  async function handleRunBacktest() {
    setRunning(true)
    setProgress("啟動中...")

    try {
      await api.backtestV2Run({
        profile_id: strategy.id,
        start_date: "2024-01-01",
        end_date: new Date().toISOString().slice(0, 10),
      })

      // Listen SSE
      const es = new EventSource(SSE_URL)
      const onProgress = (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data)
          setProgress(data.message || `${data.pct}%`)
          if (data.phase === "done" || data.phase === "error") {
            es.close()
            setRunning(false)
            refreshResults()
          }
        } catch {}
      }
      es.addEventListener("progress", onProgress)
      es.onerror = () => {
        es.close()
        setRunning(false)
        refreshResults()
      }
    } catch (e) {
      setRunning(false)
      setProgress(`失敗: ${e}`)
    }
  }

  async function refreshResults() {
    const updated = await api.backtestV2Results(strategy.id)
    setResults(updated)
    const done = updated.find(r => r.status === "done")
    if (done) {
      setSelectedResult(done)
      loadTradesAndEquity(done.id)
    }
  }

  async function loadTradesAndEquity(resultId: number) {
    const [t, e] = await Promise.all([
      api.backtestV2Trades(resultId),
      api.backtestV2Equity(resultId),
    ])
    setTrades(t)
    setEquity(e)
  }

  async function selectResult(r: BacktestV2Result) {
    setSelectedResult(r)
    if (r.status === "done") {
      loadTradesAndEquity(r.id)
    } else {
      setTrades([])
      setEquity([])
    }
    setTab("backtest")
  }

  // ── Render ──
  const m = selectedResult?.metrics
  const d = selectedResult?.diagnosis

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-3">
            <Link href="/strategies" className="text-slate-400 hover:text-slate-600">&larr;</Link>
            <h1 className="text-2xl font-bold text-slate-800">{strategy.name}</h1>
            {strategy.is_active && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">啟用中</span>
            )}
          </div>
          {strategy.description && <p className="text-slate-400 text-sm mt-1">{strategy.description}</p>}
        </div>
        <button
          onClick={handleRunBacktest}
          disabled={running}
          className="px-5 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {running ? progress : "執行回測"}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-slate-200">
        {([
          ["params", "策略參數"],
          ["backtest", "回測結果"],
          ["trades", "交易明細"],
        ] as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === key
                ? "border-indigo-500 text-indigo-600"
                : "border-transparent text-slate-400 hover:text-slate-600"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Params tab */}
      {tab === "params" && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="font-semibold text-slate-800 mb-4">策略參數</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {Object.entries(strategy.params)
              .filter(([k]) => k !== "smc_config")
              .map(([k, v]) => (
                <div key={k} className="text-sm">
                  <span className="text-slate-400">{k}</span>
                  <span className="ml-2 font-mono text-slate-700">{JSON.stringify(v)}</span>
                </div>
              ))}
          </div>
          {Object.keys(strategy.overrides).length > 0 && (
            <div className="mt-6">
              <h4 className="font-medium text-slate-700 mb-2">群組覆蓋</h4>
              <pre className="bg-slate-50 rounded-lg p-3 text-xs overflow-x-auto">
                {JSON.stringify(strategy.overrides, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Backtest results tab */}
      {tab === "backtest" && (
        <div className="space-y-6">
          {/* Result selector */}
          {results.length > 1 && (
            <div className="flex gap-2 flex-wrap">
              {results.map(r => (
                <button
                  key={r.id}
                  onClick={() => selectResult(r)}
                  className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                    selectedResult?.id === r.id
                      ? "border-indigo-300 bg-indigo-50 text-indigo-700"
                      : "border-slate-200 text-slate-500 hover:bg-slate-50"
                  }`}
                >
                  #{r.id} · {r.start_date} → {r.end_date}
                  {r.status !== "done" && ` (${r.status})`}
                </button>
              ))}
            </div>
          )}

          {m && m.total_trades != null ? (
            <>
              {/* Metrics cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard label="總報酬" value={`${(m.total_return_pct ?? 0) > 0 ? "+" : ""}${m.total_return_pct ?? 0}%`}
                  color={(m.total_return_pct ?? 0) > 0 ? "text-green-600" : "text-red-500"} />
                <MetricCard label="年化報酬" value={`${(m.annual_return_pct ?? 0) > 0 ? "+" : ""}${m.annual_return_pct ?? 0}%`}
                  color={(m.annual_return_pct ?? 0) > 0 ? "text-green-600" : "text-red-500"} />
                <MetricCard label="最大回撤" value={`${m.max_drawdown_pct ?? 0}%`}
                  color={Math.abs(m.max_drawdown_pct ?? 0) > 15 ? "text-red-500" : "text-yellow-600"} />
                <MetricCard label="Sharpe" value={(m.sharpe_ratio ?? 0).toFixed(2)}
                  color={(m.sharpe_ratio ?? 0) > 1 ? "text-green-600" : "text-slate-700"} />
                <MetricCard label="勝率" value={`${m.win_rate ?? 0}%`} color="text-slate-700" />
                <MetricCard label="交易筆數" value={`${m.total_trades ?? 0}`} color="text-slate-700" />
                <MetricCard label="Profit Factor" value={(m.profit_factor ?? 0).toFixed(2)}
                  color={(m.profit_factor ?? 0) > 1.5 ? "text-green-600" : "text-slate-700"} />
                <MetricCard label="總成本" value={`$${(m.total_cost ?? 0).toLocaleString()}`} color="text-slate-500" />
              </div>

              {/* By exit reason / tier */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {m.by_exit_reason && (
                  <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                    <h4 className="font-semibold text-slate-700 mb-3">按出場原因</h4>
                    {Object.entries(m.by_exit_reason).map(([reason, data]) => (
                      <div key={reason} className="flex justify-between text-sm py-1">
                        <span className="text-slate-500">{reason}</span>
                        <span>
                          <span className="text-slate-700">{data.count} 筆</span>
                          <span className={`ml-2 font-medium ${data.avg_pnl_pct >= 0 ? "text-green-600" : "text-red-500"}`}>
                            {data.avg_pnl_pct > 0 ? "+" : ""}{data.avg_pnl_pct}%
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                {m.by_tier && (
                  <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                    <h4 className="font-semibold text-slate-700 mb-3">按倉位等級</h4>
                    {Object.entries(m.by_tier).map(([tier, data]) => (
                      <div key={tier} className="flex justify-between text-sm py-1">
                        <span className="text-slate-500">{tier}</span>
                        <span>
                          <span className="text-slate-700">{data.count} 筆</span>
                          <span className={`ml-2 font-medium ${data.avg_pnl_pct >= 0 ? "text-green-600" : "text-red-500"}`}>
                            {data.avg_pnl_pct > 0 ? "+" : ""}{data.avg_pnl_pct}%
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Diagnosis */}
              {d && (
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h4 className="font-semibold text-slate-700 mb-3">診斷報告</h4>
                  <div className="space-y-2 text-sm">
                    {d.highlights?.map((h, i) => (
                      <p key={i} className="text-green-600">&#x2705; {h}</p>
                    ))}
                    {d.warnings?.map((w, i) => (
                      <p key={i} className="text-amber-600">&#x26A0;&#xFE0F; {w}</p>
                    ))}
                    {d.suggestions?.map((s, i) => (
                      <p key={i} className="text-blue-600">&#x1F4A1; {s}</p>
                    ))}
                  </div>
                </div>
              )}

              {/* Equity curve (simple text for now, chart in Phase 2) */}
              {equity.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h4 className="font-semibold text-slate-700 mb-3">
                    權益曲線 ({equity.length} 天)
                  </h4>
                  <div className="flex gap-6 text-sm text-slate-500">
                    <span>起始: ${equity[0]?.equity.toLocaleString()}</span>
                    <span>結束: ${equity[equity.length - 1]?.equity.toLocaleString()}</span>
                    <span>
                      最低: ${Math.min(...equity.map(e => e.equity)).toLocaleString()}
                    </span>
                  </div>
                  {/* Mini bar chart */}
                  <div className="flex items-end gap-px mt-3 h-20">
                    {sampleEquity(equity, 100).map((e, i) => {
                      const min = Math.min(...equity.map(x => x.equity))
                      const max = Math.max(...equity.map(x => x.equity))
                      const pct = max > min ? (e.equity - min) / (max - min) : 0.5
                      return (
                        <div
                          key={i}
                          className={`flex-1 rounded-t ${e.equity >= (equity[0]?.equity ?? 0) ? "bg-green-400" : "bg-red-400"}`}
                          style={{ height: `${Math.max(pct * 100, 2)}%` }}
                          title={`${e.trade_date}: $${e.equity.toLocaleString()}`}
                        />
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Info */}
              {selectedResult && (
                <div className="text-xs text-slate-400 flex gap-4">
                  <span>回測時間: {selectedResult.duration_secs}s</span>
                  <span>股票: {selectedResult.stock_count} 支</span>
                  <span>交易日: {selectedResult.trading_days} 天</span>
                  <span>run_hash: {selectedResult.run_hash}</span>
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-12 text-slate-400">
              <p className="mb-2">尚無回測結果</p>
              <p className="text-xs">點擊「執行回測」開始</p>
            </div>
          )}
        </div>
      )}

      {/* Trades tab */}
      {tab === "trades" && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-x-auto">
          {trades.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              {selectedResult ? "此回測無交易記錄" : "請先選擇一個回測結果"}
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-slate-500 text-xs">
                  <th className="text-left px-4 py-3">股票</th>
                  <th className="text-left px-4 py-3">群組</th>
                  <th className="text-left px-4 py-3">進場</th>
                  <th className="text-right px-4 py-3">買入價</th>
                  <th className="text-left px-4 py-3">出場</th>
                  <th className="text-right px-4 py-3">賣出價</th>
                  <th className="text-left px-4 py-3">原因</th>
                  <th className="text-right px-4 py-3">損益%</th>
                  <th className="text-right px-4 py-3">R:R</th>
                  <th className="text-left px-4 py-3">等級</th>
                  <th className="text-right px-4 py-3">天數</th>
                </tr>
              </thead>
              <tbody>
                {trades.map(t => (
                  <tr key={t.id} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-2.5 font-medium text-slate-800">{t.ticker}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-400">{t.stock_group}</td>
                    <td className="px-4 py-2.5 text-slate-500">{t.fill_date}</td>
                    <td className="px-4 py-2.5 text-right font-mono">{t.fill_price.toFixed(2)}</td>
                    <td className="px-4 py-2.5 text-slate-500">{t.exit_date}</td>
                    <td className="px-4 py-2.5 text-right font-mono">{t.exit_price?.toFixed(2)}</td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        t.exit_reason === "停利" ? "bg-green-50 text-green-600" :
                        t.exit_reason === "停損" ? "bg-red-50 text-red-500" :
                        "bg-slate-50 text-slate-500"
                      }`}>
                        {t.exit_reason}
                      </span>
                    </td>
                    <td className={`px-4 py-2.5 text-right font-medium ${
                      (t.pnl_pct ?? 0) >= 0 ? "text-green-600" : "text-red-500"
                    }`}>
                      {t.pnl_pct != null ? `${(t.pnl_pct * 100).toFixed(1)}%` : "-"}
                    </td>
                    <td className="px-4 py-2.5 text-right text-slate-500">
                      {t.actual_rr != null ? t.actual_rr.toFixed(1) : "-"}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-400">{t.position_tier}</td>
                    <td className="px-4 py-2.5 text-right text-slate-400">{t.holding_days}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

function MetricCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
    </div>
  )
}

function sampleEquity(data: BacktestV2EquityPoint[], maxPoints: number): BacktestV2EquityPoint[] {
  if (data.length <= maxPoints) return data
  const step = data.length / maxPoints
  return Array.from({ length: maxPoints }, (_, i) => data[Math.min(Math.floor(i * step), data.length - 1)])
}
