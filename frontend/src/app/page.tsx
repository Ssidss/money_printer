import Link from "next/link"
import { api } from "@/lib/api"
import { AnalyzeButton } from "@/components/dashboard/AnalyzeButton"
import { BatchFetchButton } from "@/components/dashboard/BatchFetchButton"
import { TopPickCard } from "@/components/dashboard/TopPickCard"
import { HoldingsSection } from "@/components/dashboard/HoldingsSection"
import { StrategySignalsSummary } from "@/components/dashboard/StrategySignalsSummary"
import type { TopPick, SmcTrendMTF } from "@/lib/api"

export const revalidate = 60

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

// v2 English → Chinese label mapping
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

export default async function Dashboard() {
  const [picks, latest, statusRes, trendsRes] = await Promise.allSettled([
    api.topPicks(3),
    api.latestAnalysis(),
    api.analysisStatus(),
    api.smcTrendsMTF(),
  ])

  const topPicks     = picks.status === "fulfilled" ? picks.value : []
  const latestRes    = latest.status === "fulfilled" ? latest.value : null
  const isRunning    = statusRes.status === "fulfilled" ? statusRes.value.running : false
  const trendsMTF    = trendsRes.status === "fulfilled" ? trendsRes.value : {} as Record<string, SmcTrendMTF>
  const allStocks: TopPick[] = latestRes?.results ?? []

  // 建立 ticker → close_price 的映射
  const priceMap: Record<string, number> = {}
  for (const s of allStocks) priceMap[s.ticker] = s.close_price

  return (
    <div className="max-w-7xl mx-auto space-y-8">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
          <p className="text-slate-500 text-sm mt-1">
            {latestRes?.date ? `最新分析：${latestRes.date}` : "尚無分析資料"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <BatchFetchButton />
          <AnalyzeButton initialRunning={isRunning} />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "追蹤股票", value: allStocks.length || 0 },
          { label: "分析日期", value: latestRes?.date ?? "—" },
          { label: "股票數", value: `US ${allStocks.filter(s => s.market === "US").length} / TW ${allStocks.filter(s => s.market === "TW").length}` },
        ].map((s) => (
          <div key={s.label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-slate-500 text-xs uppercase tracking-wide">{s.label}</p>
            <p className="text-2xl font-bold text-slate-800 mt-1">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Top 3 */}
      <div>
        <h2 className="text-lg font-semibold text-slate-800 mb-4">今日推薦 Top 3</h2>
        {topPicks.length === 0 ? (
          <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-400">
            尚無推薦，點擊右上角「立即分析」開始
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {topPicks.map((pick, i) => (
              <TopPickCard key={pick.ticker} pick={pick} rank={i + 1} />
            ))}
          </div>
        )}
      </div>

      {/* 持倉速覽 — client component，需要登入才看得到 */}
      <HoldingsSection priceMap={priceMap} trendsMTF={trendsMTF} />

      {/* 策略信號總覽 — client component，即時載入 batch signals */}
      <StrategySignalsSummary />

      {/* All Tracked Stocks */}
      <div>
        <h2 className="text-lg font-semibold text-slate-800 mb-4">
          追蹤股票清單
          <span className="ml-2 text-sm font-normal text-slate-400">({allStocks.length} 支)</span>
        </h2>
        {allStocks.length === 0 ? (
          <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-400">
            尚無分析資料
          </div>
        ) : (
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
                  <th className="text-center px-4 py-3">推薦</th>
                  <th className="text-center px-4 py-3">建議操作</th>
                </tr>
              </thead>
              <tbody>
                {allStocks.map((s, i) => {
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
        )}
      </div>
    </div>
  )
}
