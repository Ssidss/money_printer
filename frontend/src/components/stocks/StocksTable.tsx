"use client"

import { useState } from "react"
import Link from "next/link"
import type { TopPick, Stock, EntrySuggestion } from "@/lib/api"
import { RemoveStockButton } from "./RemoveStockButton"

type MergedStock = Stock & Partial<TopPick>

type Market = "ALL" | "US" | "TW"

const REC_BADGE: Record<string, string> = {
  "強力推薦": "bg-green-100 text-green-700",
  "推薦":     "bg-blue-100  text-blue-700",
  "觀察":     "bg-yellow-100 text-yellow-700",
  "不推薦":   "bg-slate-100 text-slate-500",
}

const TREND_STYLE: Record<string, string> = {
  "上升趨勢": "bg-green-100 text-green-700",
  "下降趨勢": "bg-red-100 text-red-500",
  "盤整":     "bg-yellow-100 text-yellow-700",
  "未知":     "bg-slate-100 text-slate-400",
}

function ScoreBar({ value }: { value: number }) {
  const color = value >= 65 ? "bg-green-500" : value >= 50 ? "bg-yellow-500" : "bg-red-400"
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className="text-xs text-slate-600 w-8 text-right">{value.toFixed(0)}</span>
    </div>
  )
}

function TrendBadge({ trend }: { trend?: string }) {
  const t = trend ?? "未知"
  const icon = t === "上升趨勢" ? "↑" : t === "下降趨勢" ? "↓" : "↔"
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs px-2 py-0.5 rounded font-medium ${TREND_STYLE[t] ?? TREND_STYLE["未知"]}`}>
      {icon} {t}
    </span>
  )
}

function EntryCell({ es, rec }: { es?: EntrySuggestion | null; rec?: string }) {
  if (!es) {
    return <span className="text-slate-300 text-xs">待分析</span>
  }
  if (rec === "不推薦") {
    return <span className="text-slate-300 text-xs">不建議</span>
  }
  return (
    <div className="text-xs space-y-0.5 text-right">
      <div>
        <span className="text-slate-400">買：</span>
        <span className="font-semibold text-indigo-600">{es.entry.toFixed(2)}</span>
      </div>
      <div>
        <span className="text-slate-400">停：</span>
        <span className="font-medium text-red-500">{es.stop.toFixed(2)}</span>
      </div>
      <div>
        <span className="text-slate-400">目：</span>
        <span className="font-medium text-green-600">{es.target.toFixed(2)}</span>
      </div>
      <div className="text-slate-400">R:R <span className="font-medium text-slate-600">{es.rr}x</span></div>
    </div>
  )
}

interface Props {
  stocks: MergedStock[]
  trends: Record<string, string>
  analysisDone: boolean
}

export function StocksTable({ stocks, trends, analysisDone }: Props) {
  const [market, setMarket] = useState<Market>("ALL")

  const us = stocks.filter(s => s.market === "US")
  const tw = stocks.filter(s => s.market === "TW")

  const groups: { label: string; key: Market; stocks: MergedStock[] }[] = [
    { label: `🇺🇸 美股`, key: "US",  stocks: us },
    { label: `🇹🇼 台股`, key: "TW",  stocks: tw },
  ]

  const visible = market === "ALL"
    ? groups.filter(g => g.stocks.length > 0)
    : groups.filter(g => g.key === market && g.stocks.length > 0)

  return (
    <div className="space-y-6">
      {/* 篩選 Tabs */}
      <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1 w-fit">
        {([
          { key: "ALL", label: `全部 (${stocks.length})` },
          { key: "US",  label: `🇺🇸 美股 (${us.length})` },
          { key: "TW",  label: `🇹🇼 台股 (${tw.length})` },
        ] as const).map(tab => (
          <button
            key={tab.key}
            onClick={() => setMarket(tab.key)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              market === tab.key
                ? "bg-white text-slate-800 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {stocks.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-16 text-center text-slate-400">
          <p className="text-4xl mb-3">📭</p>
          <p className="font-medium">尚未追蹤任何股票</p>
          <p className="text-sm mt-1">點擊右上角「新增追蹤」開始</p>
        </div>
      )}

      {visible.map(({ label, stocks: group }) => (
        <div key={label}>
          <h2 className="text-base font-semibold text-slate-700 mb-3">
            {label} <span className="text-slate-400 font-normal text-sm">({group.length})</span>
          </h2>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs uppercase tracking-wide">
                  <th className="text-left px-4 py-3">股票</th>
                  <th className="text-right px-4 py-3">最新價</th>
                  <th className="px-4 py-3 w-28">綜合分</th>
                  <th className="text-right px-4 py-3">RSI</th>
                  <th className="text-center px-4 py-3">SMC 趨勢</th>
                  <th className="text-center px-4 py-3">推薦</th>
                  <th className="text-right px-4 py-3 min-w-[110px]">
                    <span className="text-indigo-500">量化建議</span>
                    <div className="text-slate-300 font-normal normal-case">買 / 停 / 目標</div>
                  </th>
                  <th className="text-center px-4 py-3">操作</th>
                </tr>
              </thead>
              <tbody>
                {group.map((s) => {
                  const hasAnalysis = s.composite_score !== undefined
                  return (
                    <tr key={s.ticker} className="border-t border-slate-100 hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3">
                        <Link
                          href={`/stocks/${s.ticker}`}
                          className="font-semibold text-indigo-600 hover:text-indigo-800 hover:underline"
                        >
                          {s.ticker}
                        </Link>
                        {s.name && (
                          <span className="ml-2 text-xs text-slate-400">{s.name}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-slate-700">
                        {s.close_price
                          ? s.close_price.toFixed ? s.close_price.toFixed(2) : s.close_price
                          : <span className="text-slate-300">—</span>
                        }
                      </td>
                      <td className="px-4 py-3">
                        {hasAnalysis
                          ? <ScoreBar value={s.composite_score!} />
                          : <span className="text-slate-300 text-xs">待分析</span>
                        }
                      </td>
                      <td className={`px-4 py-3 text-right font-medium text-sm ${
                        s.rsi === undefined ? "text-slate-300"
                        : s.rsi < 35 ? "text-green-600"
                        : s.rsi > 65 ? "text-red-500"
                        : "text-slate-600"
                      }`}>
                        {s.rsi !== undefined ? s.rsi.toFixed(1) : "—"}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <TrendBadge trend={trends[s.ticker]} />
                      </td>
                      <td className="px-4 py-3 text-center">
                        {hasAnalysis ? (
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${REC_BADGE[s.recommendation!] ?? REC_BADGE["不推薦"]}`}>
                            {s.recommendation}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-300">待分析</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <EntryCell
                          es={s.entry_suggestion}
                          rec={s.recommendation}
                        />
                      </td>
                      <td className="px-4 py-3 text-center">
                        <RemoveStockButton ticker={s.ticker} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {!analysisDone && stocks.length > 0 && (
        <p className="text-center text-xs text-slate-400 py-2">
          💡 量化建議需先執行分析才會顯示，請在 Dashboard 點擊「立即分析」
        </p>
      )}
    </div>
  )
}
