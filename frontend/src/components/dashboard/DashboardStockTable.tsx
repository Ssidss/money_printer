"use client"

import Link from "next/link"
import type { TopPick, SmcTrendMTF } from "@/lib/api"
import { useBatchSignals, SignalCell } from "./BatchSignals"
import { useStrategy } from "@/contexts/StrategyContext"

const REC_BADGE: Record<string, string> = {
  "強力推薦": "bg-green-100 text-green-700",
  "推薦":     "bg-blue-100  text-blue-700",
  "觀察":     "bg-yellow-100 text-yellow-700",
  "不推薦":   "bg-slate-100 text-slate-500",
}

const ACTION_BADGE: Record<string, string> = {
  "買入": "bg-green-100 text-green-700",
  "加碼": "bg-green-50 text-green-600",
  "持有": "bg-blue-50 text-blue-600",
  "減倉": "bg-orange-100 text-orange-600",
  "出場": "bg-red-100 text-red-600",
  "觀望": "bg-slate-100 text-slate-500",
  "等回調": "bg-amber-50 text-amber-600",
  "不操作": "bg-slate-100 text-slate-400",
}

const TREND_LABEL: Record<string, string> = {
  uptrend: "上升", weak_uptrend: "弱上升", downtrend: "下降",
  weak_downtrend: "弱下降", ranging: "盤整", range: "盤整",
  "上升趨勢": "上升", "下降趨勢": "下降", "盤整": "盤整",
}

const TREND_STYLE: Record<string, string> = {
  "上升": "bg-green-100 text-green-700",
  "弱上升": "bg-green-50 text-green-600",
  "下降": "bg-red-100 text-red-500",
  "弱下降": "bg-red-50 text-red-400",
  "盤整": "bg-yellow-100 text-yellow-700",
  "未知": "bg-slate-100 text-slate-400",
}

const TREND_ICON: Record<string, string> = {
  "上升": "↑", "弱上升": "↗", "下降": "↓", "弱下降": "↘", "盤整": "↔",
}

function ScorePill({ value }: { value: number }) {
  const color = value >= 65 ? "text-green-600" : value >= 50 ? "text-yellow-600" : "text-red-500"
  return <span className={`font-semibold ${color}`}>{value.toFixed(1)}</span>
}

function TrendBadge({ trend }: { trend?: string }) {
  const label = TREND_LABEL[trend ?? ""] ?? "未知"
  const icon = TREND_ICON[label] ?? "?"
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs px-2 py-0.5 rounded font-medium ${TREND_STYLE[label] ?? TREND_STYLE["未知"]}`}>
      {icon} {label}
    </span>
  )
}

/**
 * Dashboard 追蹤股票清單 — client component
 * 包含策略信號欄，batch signals 只 fetch 一次
 */
export function DashboardStockTable({
  stocks,
  trendsMTF,
}: {
  stocks: TopPick[]
  trendsMTF: Record<string, SmcTrendMTF>
}) {
  const { v3 } = useStrategy()
  const { signalMap: batchSignalMap, loading: batchLoading } = useBatchSignals()
  // When V3 is active, use V3 signals; otherwise use batch signals
  const signalMap = v3.active ? v3.signalMap : batchSignalMap
  const sigLoading = v3.active ? v3.loading : batchLoading

  if (stocks.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-400">
        尚無分析資料
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs uppercase tracking-wide">
            <th className="text-left px-4 py-3">股票</th>
            <th className="text-left px-4 py-3">市場</th>
            <th className="text-right px-4 py-3">最新價</th>
            <th className="text-right px-4 py-3">綜合分</th>
            <th className="text-right px-4 py-3">技術分</th>
            <th className="text-right px-4 py-3">情緒分</th>
            <th className="text-right px-4 py-3">RSI</th>
            <th className="text-center px-4 py-3">SMC 趨勢</th>
            <th className="text-center px-4 py-3">策略信號</th>
            <th className="text-center px-4 py-3">推薦</th>
            <th className="text-center px-4 py-3">建議操作</th>
          </tr>
        </thead>
        <tbody>
          {stocks.map((s, i) => {
            const mtf = trendsMTF[s.ticker]
            const v2rec = mtf?.recommendation ?? s.smc_v2?.recommendation
            const v2action = mtf?.action ?? s.smc_v2?.action
            const displayRec = v2rec ?? s.recommendation
            return (
              <tr key={s.ticker} className={`border-t border-slate-100 hover:bg-slate-50 transition-colors ${i < 3 ? "bg-amber-50/40" : ""}`}>
                <td className="px-4 py-3">
                  {i < 3 && <span className="mr-1">{["🥇","🥈","🥉"][i]}</span>}
                  <Link href={`/stocks/${s.ticker}`} className="font-semibold text-indigo-600 hover:text-indigo-800 hover:underline">
                    {s.ticker}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{s.market}</span>
                </td>
                <td className="px-4 py-3 text-right text-slate-700">{s.close_price}</td>
                <td className="px-4 py-3 text-right"><ScorePill value={s.composite_score} /></td>
                <td className="px-4 py-3 text-right text-slate-600">{s.technical_score.toFixed(1)}</td>
                <td className="px-4 py-3 text-right text-slate-600">{s.sentiment_score.toFixed(1)}</td>
                <td className={`px-4 py-3 text-right ${s.rsi < 35 ? "text-green-600" : s.rsi > 65 ? "text-red-500" : "text-slate-600"}`}>
                  {s.rsi?.toFixed(1)}
                </td>
                <td className="px-4 py-3 text-center">
                  <TrendBadge trend={mtf?.daily} />
                </td>
                <td className="px-4 py-3 text-center">
                  <SignalCell ticker={s.ticker} signalMap={signalMap} loading={sigLoading} />
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${REC_BADGE[displayRec] ?? REC_BADGE["不推薦"]}`}>
                    {displayRec}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  {v2action && (
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${ACTION_BADGE[v2action] ?? "bg-slate-100 text-slate-500"}`}>
                      {v2action}
                    </span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
