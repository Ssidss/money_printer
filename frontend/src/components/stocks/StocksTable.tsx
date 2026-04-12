"use client"

import { useState, useMemo } from "react"
import Link from "next/link"
import type { TopPick, Stock, EntrySuggestion, AiNoteLatest, SmcTrendMTF } from "@/lib/api"
import { RemoveStockButton } from "./RemoveStockButton"
import { useBatchSignals, SignalCell } from "@/components/dashboard/BatchSignals"

type MergedStock = Stock & Partial<TopPick>

type Market = "ALL" | "US" | "TW"
type SortKey = "ticker" | "close_price" | "composite_score" | "rsi" | "recommendation"
type SortDir = "asc" | "desc"

const REC_BADGE: Record<string, string> = {
  "強力推薦": "bg-green-100 text-green-700",
  "推薦":     "bg-blue-100  text-blue-700",
  "觀察":     "bg-yellow-100 text-yellow-700",
  "不推薦":   "bg-slate-100 text-slate-500",
}

const REC_ORDER: Record<string, number> = {
  "強力推薦": 4, "推薦": 3, "觀察": 2, "不推薦": 1,
}

// v2 English → Chinese label
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
  const label = TREND_LABEL[trend ?? ""] ?? "未知"
  const icon = TREND_ICON[label] ?? "?"
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs px-2 py-0.5 rounded font-medium ${TREND_STYLE[label] ?? TREND_STYLE["未知"]}`}>
      {icon} {label}
    </span>
  )
}

function EntryCell({ es, rec, v2 }: { es?: EntrySuggestion | null; rec?: string; v2?: TopPick["smc_v2"] }) {
  // Prefer v2 entry data
  if (v2?.entry_price && v2?.stop_price && v2?.target_price) {
    return (
      <div className="text-xs space-y-0.5 text-right">
        <div>
          <span className="text-slate-400">買：</span>
          <span className="font-semibold text-indigo-600">{v2.entry_price.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-slate-400">停：</span>
          <span className="font-medium text-red-500">{v2.stop_price.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-slate-400">目：</span>
          <span className="font-medium text-green-600">{v2.target_price.toFixed(2)}</span>
        </div>
        {v2.rr_ratio && (
          <div className={`font-medium ${v2.rr_ratio >= 2 ? "text-green-600" : v2.rr_ratio >= 1.5 ? "text-yellow-600" : "text-slate-400"}`}>
            R:R {v2.rr_ratio.toFixed(2)}x
          </div>
        )}
        {v2.position_tier && (
          <div className={`font-bold ${
            v2.position_tier === "核心持倉" ? "text-green-600" :
            v2.position_tier === "標準倉位" ? "text-blue-600" :
            "text-yellow-600"
          }`}>{v2.position_tier === "核心持倉" ? "🟢 核心" : v2.position_tier === "標準倉位" ? "🔵 標準" : "🟡 探索"}</div>
        )}
      </div>
    )
  }

  // Fallback to v1
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
      <div className={`font-medium ${es.rr >= 2 ? "text-green-600" : es.rr >= 1.5 ? "text-yellow-600" : "text-slate-400"}`}>
        R:R {es.rr}x
      </div>
      {es.position_tier && (
        <div className={`font-bold ${
          es.position_tier === "核心持倉" ? "text-green-600" :
          es.position_tier === "標準倉位" ? "text-blue-600" :
          "text-yellow-600"
        }`}>{es.position_tier === "核心持倉" ? "🟢 核心" : es.position_tier === "標準倉位" ? "🔵 標準" : "🟡 探索"}</div>
      )}
    </div>
  )
}

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="text-slate-300 ml-0.5">↕</span>
  return <span className="text-indigo-500 ml-0.5">{dir === "asc" ? "↑" : "↓"}</span>
}

const ACTION_BADGE: Record<string, string> = {
  "買入": "bg-green-100 text-green-700",
  "加碼": "bg-green-50 text-green-600",
  "持有": "bg-blue-50 text-blue-600",
  "減倉": "bg-orange-100 text-orange-600",
  "出場": "bg-red-100 text-red-600",
  "觀望": "bg-slate-100 text-slate-500",
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  return `${days}d`
}

interface Props {
  stocks: MergedStock[]
  trendsMTF: Record<string, SmcTrendMTF>
  analysisDone: boolean
  aiNotes?: Record<string, AiNoteLatest>
}

export function StocksTable({ stocks, trendsMTF, analysisDone, aiNotes = {} }: Props) {
  const [market, setMarket] = useState<Market>("ALL")
  const [sortKey, setSortKey] = useState<SortKey>("composite_score")
  const [sortDir, setSortDir] = useState<SortDir>("desc")
  const { signalMap, loading: signalsLoading } = useBatchSignals()

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === "asc" ? "desc" : "asc")
    } else {
      setSortKey(key)
      setSortDir("desc")
    }
  }

  const sortFn = (a: MergedStock, b: MergedStock): number => {
    let av: number, bv: number
    switch (sortKey) {
      case "ticker":
        return sortDir === "asc"
          ? a.ticker.localeCompare(b.ticker)
          : b.ticker.localeCompare(a.ticker)
      case "close_price":
        av = a.close_price ?? -1; bv = b.close_price ?? -1; break
      case "composite_score":
        av = a.composite_score ?? -1; bv = b.composite_score ?? -1; break
      case "rsi":
        av = a.rsi ?? -1; bv = b.rsi ?? -1; break
      case "recommendation":
        av = REC_ORDER[a.recommendation ?? ""] ?? 0
        bv = REC_ORDER[b.recommendation ?? ""] ?? 0; break
      default:
        return 0
    }
    return sortDir === "asc" ? av - bv : bv - av
  }

  const us = useMemo(() => stocks.filter(s => s.market === "US"), [stocks])
  const tw = useMemo(() => stocks.filter(s => s.market === "TW"), [stocks])

  const groups: { label: string; key: Market; stocks: MergedStock[] }[] = [
    { label: `🇺🇸 美股`, key: "US",  stocks: us },
    { label: `🇹🇼 台股`, key: "TW",  stocks: tw },
  ]

  const visible = market === "ALL"
    ? groups.filter(g => g.stocks.length > 0)
    : groups.filter(g => g.key === market && g.stocks.length > 0)

  const thClass = "px-4 py-3 cursor-pointer select-none hover:text-indigo-600 transition-colors"

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

      {visible.map(({ label, stocks: group }) => {
        const sorted = [...group].sort(sortFn)
        return (
        <div key={label}>
          <h2 className="text-base font-semibold text-slate-700 mb-3">
            {label} <span className="text-slate-400 font-normal text-sm">({group.length})</span>
          </h2>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs uppercase tracking-wide">
                  <th className={`text-left ${thClass}`} onClick={() => toggleSort("ticker")}>
                    股票 <SortIcon active={sortKey === "ticker"} dir={sortDir} />
                  </th>
                  <th className={`text-right ${thClass}`} onClick={() => toggleSort("close_price")}>
                    最新價 <SortIcon active={sortKey === "close_price"} dir={sortDir} />
                  </th>
                  <th className={`${thClass} w-28`} onClick={() => toggleSort("composite_score")}>
                    綜合分 <SortIcon active={sortKey === "composite_score"} dir={sortDir} />
                  </th>
                  <th className={`text-right ${thClass}`} onClick={() => toggleSort("rsi")}>
                    RSI <SortIcon active={sortKey === "rsi"} dir={sortDir} />
                  </th>
                  <th className="text-center px-4 py-3">SMC 趨勢</th>
                  <th className={`text-center ${thClass}`} onClick={() => toggleSort("recommendation")}>
                    推薦 <SortIcon active={sortKey === "recommendation"} dir={sortDir} />
                  </th>
                  <th className="text-center px-4 py-3">建議操作</th>
                  <th className="text-center px-4 py-3 min-w-[80px]">
                    <span className="text-cyan-600">策略信號</span>
                  </th>
                  <th className="text-right px-4 py-3 min-w-[110px]">
                    <span className="text-indigo-500">進出場</span>
                    <div className="text-slate-300 font-normal normal-case">買 / 停 / 目標</div>
                  </th>
                  <th className="text-center px-4 py-3 min-w-[90px]">
                    <span className="text-violet-500">🤖 AI</span>
                    <div className="text-slate-300 font-normal normal-case">最新分析</div>
                  </th>
                  <th className="text-center px-4 py-3">操作</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((s) => {
                  const hasAnalysis = s.composite_score !== undefined
                  const mtf = trendsMTF[s.ticker]
                  const v2rec = mtf?.recommendation ?? s.smc_v2?.recommendation
                  const v2action = mtf?.action ?? s.smc_v2?.action
                  const displayRec = v2rec ?? s.recommendation
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
                        <TrendBadge trend={mtf?.daily} />
                      </td>
                      <td className="px-4 py-3 text-center">
                        {displayRec ? (
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${REC_BADGE[displayRec] ?? REC_BADGE["不推薦"]}`}>
                            {displayRec}
                          </span>
                        ) : hasAnalysis ? (
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${REC_BADGE[s.recommendation!] ?? REC_BADGE["不推薦"]}`}>
                            {s.recommendation}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-300">待分析</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {v2action ? (
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${ACTION_BADGE[v2action] ?? "bg-slate-100 text-slate-500"}`}>
                            {v2action}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <SignalCell ticker={s.ticker} signalMap={signalMap} loading={signalsLoading} />
                      </td>
                      <td className="px-4 py-3">
                        <EntryCell
                          es={s.entry_suggestion}
                          rec={s.recommendation}
                          v2={s.smc_v2}
                        />
                      </td>
                      <td className="px-4 py-3 text-center">
                        {aiNotes[s.ticker] ? (
                          <div className="text-xs space-y-0.5">
                            <div className="flex items-center justify-center gap-1 flex-wrap">
                              {aiNotes[s.ticker].action && (
                                <span className={`px-1.5 py-0.5 rounded font-medium ${ACTION_BADGE[aiNotes[s.ticker].action!] ?? "bg-slate-100 text-slate-500"}`}>
                                  {aiNotes[s.ticker].action}
                                </span>
                              )}
                            </div>
                            <div className="text-slate-400">{timeAgo(aiNotes[s.ticker].created_at)}</div>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-300">—</span>
                        )}
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
        )
      })}

      {!analysisDone && stocks.length > 0 && (
        <p className="text-center text-xs text-slate-400 py-2">
          💡 量化建議需先執行分析才會顯示，請在 Dashboard 點擊「立即分析」
        </p>
      )}
    </div>
  )
}
