"use client"

import { useState } from "react"
import Link from "next/link"
import { api } from "@/lib/api"
import type { StrategyListItem } from "@/lib/api"

const METRIC_FMT: Record<string, (v: number) => string> = {
  total_return_pct: v => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`,
  max_drawdown_pct: v => `${v.toFixed(1)}%`,
  sharpe_ratio: v => v.toFixed(2),
  win_rate: v => `${v.toFixed(0)}%`,
}

export function StrategyList({ initialStrategies }: { initialStrategies: StrategyListItem[] }) {
  const [strategies, setStrategies] = useState(initialStrategies)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState("")

  async function handleCreate() {
    if (!newName.trim()) return
    setCreating(true)
    try {
      await api.createStrategy({ name: newName.trim() })
      const updated = await api.strategies()
      setStrategies(updated)
      setNewName("")
    } catch (e) {
      alert(`建立失敗: ${e}`)
    } finally {
      setCreating(false)
    }
  }

  async function handleActivate(id: number) {
    await api.activateStrategy(id)
    const updated = await api.strategies()
    setStrategies(updated)
  }

  async function handleClone(id: number) {
    await api.cloneStrategy(id)
    const updated = await api.strategies()
    setStrategies(updated)
  }

  async function handleDelete(id: number) {
    if (!confirm("確定刪除此策略？")) return
    await api.deleteStrategy(id)
    setStrategies(s => s.filter(x => x.id !== id))
  }

  return (
    <div className="space-y-4">
      {/* Create */}
      <div className="flex gap-3 items-center">
        <input
          value={newName}
          onChange={e => setNewName(e.target.value)}
          placeholder="新策略名稱..."
          className="flex-1 rounded-lg border border-slate-200 px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-400"
          onKeyDown={e => e.key === "Enter" && handleCreate()}
        />
        <button
          onClick={handleCreate}
          disabled={creating || !newName.trim()}
          className="px-5 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {creating ? "建立中..." : "+ 建立策略"}
        </button>
      </div>

      {/* List */}
      {strategies.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <p className="text-lg mb-2">尚無策略檔案</p>
          <p className="text-sm">建立第一個策略開始回測</p>
        </div>
      ) : (
        <div className="space-y-3">
          {strategies.map(s => (
            <div key={s.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-indigo-200 transition-colors">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <Link href={`/strategies/${s.id}`} className="text-lg font-bold text-slate-800 hover:text-indigo-600 transition-colors">
                    {s.name}
                  </Link>
                  {s.is_active && (
                    <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">
                      啟用中
                    </span>
                  )}
                  {s.description && (
                    <p className="text-sm text-slate-400 mt-0.5">{s.description}</p>
                  )}
                </div>
                <div className="flex gap-2">
                  {!s.is_active && (
                    <button onClick={() => handleActivate(s.id)} className="text-xs px-3 py-1.5 rounded-lg bg-green-50 text-green-600 hover:bg-green-100">
                      啟用
                    </button>
                  )}
                  <button onClick={() => handleClone(s.id)} className="text-xs px-3 py-1.5 rounded-lg bg-slate-50 text-slate-500 hover:bg-slate-100">
                    複製
                  </button>
                  <button onClick={() => handleDelete(s.id)} className="text-xs px-3 py-1.5 rounded-lg bg-red-50 text-red-500 hover:bg-red-100">
                    刪除
                  </button>
                </div>
              </div>

              {/* Metrics summary */}
              {s.latest_metrics ? (
                <div className="flex gap-6 text-sm">
                  <MetricBadge label="報酬" value={s.latest_metrics.total_return_pct} fmt={METRIC_FMT.total_return_pct} positive />
                  <MetricBadge label="回撤" value={s.latest_metrics.max_drawdown_pct} fmt={METRIC_FMT.max_drawdown_pct} />
                  <MetricBadge label="Sharpe" value={s.latest_metrics.sharpe_ratio} fmt={METRIC_FMT.sharpe_ratio} />
                  <MetricBadge label="勝率" value={s.latest_metrics.win_rate} fmt={METRIC_FMT.win_rate} />
                  <MetricBadge label="交易" value={s.latest_metrics.total_trades} fmt={v => `${v}`} />
                </div>
              ) : (
                <p className="text-xs text-slate-400">尚未回測</p>
              )}

              <div className="flex items-center gap-4 mt-3 text-xs text-slate-400">
                <span>建立於 {new Date(s.created_at).toLocaleDateString("zh-TW")}</span>
                <Link href={`/strategies/${s.id}`} className="text-indigo-500 hover:underline">
                  查看詳情 &rarr;
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function MetricBadge({ label, value, fmt, positive }: {
  label: string; value: number; fmt: (v: number) => string; positive?: boolean
}) {
  const color = positive
    ? value > 0 ? "text-green-600" : value < 0 ? "text-red-500" : "text-slate-600"
    : "text-slate-700"
  return (
    <div>
      <span className="text-slate-400">{label}</span>{" "}
      <span className={`font-semibold ${color}`}>{fmt(value)}</span>
    </div>
  )
}
