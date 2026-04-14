"use client"
import { useEffect, useState } from "react"
import Link from "next/link"
import { api } from "@/lib/api"
import { useAuth } from "@/contexts/AuthContext"
import type { Holding, SmcTrendMTF } from "@/lib/api"

const TREND_LABEL: Record<string, string> = {
  uptrend: "上升", weak_uptrend: "弱上升", downtrend: "下降",
  weak_downtrend: "弱下降", ranging: "盤整", range: "盤整",
  "上升趨勢": "上升", "下降趨勢": "下降", "盤整": "盤整",
}
const TREND_STYLE: Record<string, string> = {
  "上升": "bg-green-100 text-green-700", "弱上升": "bg-green-50 text-green-600",
  "下降": "bg-red-100 text-red-500", "弱下降": "bg-red-50 text-red-400",
  "盤整": "bg-yellow-100 text-yellow-700", "未知": "bg-slate-100 text-slate-400",
}
const TREND_ICON: Record<string, string> = {
  "上升": "↑", "弱上升": "↗", "下降": "↓", "弱下降": "↘", "盤整": "↔",
}
const ACTION_BADGE: Record<string, string> = {
  "買入": "bg-green-100 text-green-700", "加碼": "bg-green-50 text-green-600",
  "持有": "bg-blue-50 text-blue-600", "減倉": "bg-orange-100 text-orange-600",
  "出場": "bg-red-100 text-red-600", "觀望": "bg-slate-100 text-slate-500",
  "等回調": "bg-amber-50 text-amber-600", "不操作": "bg-slate-100 text-slate-400",
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

function MTFMini({ mtf }: { mtf: SmcTrendMTF }) {
  const frames = [
    { label: "月", trend: mtf.monthly },
    { label: "週", trend: mtf.weekly },
    { label: "日", trend: mtf.daily },
  ]
  return (
    <div className="flex items-center gap-1">
      {frames.map(f => {
        const lbl = TREND_LABEL[f.trend] ?? "未知"
        const icon = TREND_ICON[lbl] ?? "?"
        const color = lbl.includes("上升") || lbl === "弱上升" ? "text-green-600"
          : lbl.includes("下降") || lbl === "弱下降" ? "text-red-500"
          : "text-yellow-600"
        return (
          <span key={f.label} className={`text-xs ${color}`} title={`${f.label}線: ${lbl}`}>
            {f.label}{icon}
          </span>
        )
      })}
    </div>
  )
}

type MarketStatus = {
  now_et: string
  market_closed: boolean
  expected_latest_date: string
  is_weekend: boolean
} | null

type Props = {
  priceMap: Record<string, number>
  priceDateMap: Record<string, string>
  marketStatus: MarketStatus
  trendsMTF: Record<string, SmcTrendMTF>
}

export function HoldingsSection({ priceMap, priceDateMap, marketStatus, trendsMTF }: Props) {
  const { user } = useAuth()
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!user) return
    let cancelled = false
    queueMicrotask(() => {
      if (!cancelled) setLoading(true)
    })
    api.holdings()
      .then((rows) => {
        if (!cancelled) setHoldings(rows)
      })
      .catch(() => {
        if (!cancelled) setHoldings([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [user])

  if (!user) return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 text-center text-slate-400">
      請先<Link href="/login" className="text-indigo-600 hover:underline mx-1">登入</Link>以查看持倉
    </div>
  )
  if (loading) return null
  if (holdings.length === 0) return null

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-800 mb-4">
        持倉速覽
        <span className="ml-2 text-sm font-normal text-slate-400">（點股票名稱進入 SMC 分析）</span>
        {marketStatus && (
          <span className={`ml-2 text-xs px-2 py-0.5 rounded ${marketStatus.market_closed ? "bg-slate-100 text-slate-500" : "bg-green-100 text-green-700"}`}>
            {marketStatus.market_closed ? (marketStatus.is_weekend ? "週末休市" : "已收盤") : "盤中"}
          </span>
        )}
      </h2>
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs uppercase tracking-wide">
              <th className="text-left px-4 py-3">股票</th>
              <th className="text-right px-4 py-3">當前價</th>
              <th className="text-right px-4 py-3">均成本</th>
              <th className="text-right px-4 py-3">損益</th>
              <th className="text-right px-4 py-3">停損</th>
              <th className="text-right px-4 py-3">停利</th>
              <th className="text-center px-4 py-3">SMC 趨勢</th>
              <th className="text-center px-4 py-3">MTF</th>
              <th className="text-center px-4 py-3">建議</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => {
              const curr = priceMap[h.ticker]
              const priceDate = priceDateMap[h.ticker]
              const pnlPct = curr ? ((curr - h.avg_cost) / h.avg_cost * 100) : null
              const mtf = trendsMTF[h.ticker]
              const isNearStop = curr != null && curr <= h.stop_loss_price * 1.03
              return (
                <tr key={h.ticker} className={`border-t border-slate-100 hover:bg-slate-50 ${isNearStop ? "bg-red-50/50" : ""}`}>
                  <td className="px-4 py-3">
                    <Link href={`/stocks/${h.ticker}`} className="font-semibold text-indigo-600 hover:underline">
                      {h.ticker}
                    </Link>
                    <span className="ml-2 text-xs bg-slate-100 text-slate-400 px-1.5 py-0.5 rounded">{h.market}</span>
                    {isNearStop && <span className="ml-2 text-xs text-red-500 font-medium">⚠ 接近停損</span>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="font-medium text-slate-800">{curr ? curr.toFixed(2) : "—"}</div>
                    {priceDate && (
                      <div className="text-[10px] text-slate-400">{priceDate.slice(5)} 收盤</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-500">{h.avg_cost.toFixed(2)}</td>
                  <td className={`px-4 py-3 text-right font-semibold ${pnlPct === null ? "text-slate-400" : pnlPct >= 0 ? "text-green-600" : "text-red-500"}`}>
                    {pnlPct === null ? "—" : `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%`}
                  </td>
                  <td className="px-4 py-3 text-right text-red-500">{h.stop_loss_price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right text-green-600">{h.take_profit_price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-center">
                    <TrendBadge trend={mtf?.daily} />
                  </td>
                  <td className="px-4 py-3 text-center">
                    {mtf && <MTFMini mtf={mtf} />}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {mtf?.action && (
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${ACTION_BADGE[mtf.action] ?? "bg-slate-100 text-slate-500"}`}>
                        {mtf.action}
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
