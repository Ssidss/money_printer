import Link from "next/link"
import { api } from "@/lib/api"
import { AnalyzeButton } from "@/components/dashboard/AnalyzeButton"
import { TopPickCard } from "@/components/dashboard/TopPickCard"
import type { TopPick } from "@/lib/api"

export const revalidate = 60

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

function ScorePill({ value }: { value: number }) {
  const color = value >= 65 ? "text-green-600" : value >= 50 ? "text-yellow-600" : "text-red-500"
  return <span className={`font-semibold ${color}`}>{value.toFixed(1)}</span>
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

export default async function Dashboard() {
  const [picks, latest, holdings, statusRes, trendsRes] = await Promise.allSettled([
    api.topPicks(3),
    api.latestAnalysis(),
    api.holdings(),
    api.analysisStatus(),
    api.smcTrends(),
  ])

  const topPicks     = picks.status === "fulfilled" ? picks.value : []
  const latestRes    = latest.status === "fulfilled" ? latest.value : null
  const holdingsList = holdings.status === "fulfilled" ? holdings.value : []
  const isRunning    = statusRes.status === "fulfilled" ? statusRes.value.running : false
  const trends       = trendsRes.status === "fulfilled" ? trendsRes.value : {} as Record<string, string>
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
        <AnalyzeButton initialRunning={isRunning} />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "追蹤股票", value: allStocks.length || 0 },
          { label: "目前持倉", value: holdingsList.length },
          { label: "分析日期", value: latestRes?.date ?? "—" },
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

      {/* 持倉速覽 */}
      {holdingsList.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-slate-800 mb-4">
            持倉速覽
            <span className="ml-2 text-sm font-normal text-slate-400">（點股票名稱進入 SMC 分析）</span>
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
                </tr>
              </thead>
              <tbody>
                {holdingsList.map((h) => {
                  const curr = priceMap[h.ticker]
                  const pnlPct = curr ? ((curr - h.avg_cost) / h.avg_cost * 100) : null
                  const trend = trends[h.ticker]
                  const isNearStop = curr && curr <= h.stop_loss_price * 1.03
                  return (
                    <tr key={h.ticker} className={`border-t border-slate-100 hover:bg-slate-50 ${isNearStop ? "bg-red-50/50" : ""}`}>
                      <td className="px-4 py-3">
                        <Link href={`/stocks/${h.ticker}`} className="font-semibold text-indigo-600 hover:underline">
                          {h.ticker}
                        </Link>
                        <span className="ml-2 text-xs bg-slate-100 text-slate-400 px-1.5 py-0.5 rounded">{h.market}</span>
                        {isNearStop && <span className="ml-2 text-xs text-red-500 font-medium">⚠ 接近停損</span>}
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-slate-800">
                        {curr ? curr.toFixed(2) : "—"}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-500">{h.avg_cost.toFixed(2)}</td>
                      <td className={`px-4 py-3 text-right font-semibold ${pnlPct === null ? "text-slate-400" : pnlPct >= 0 ? "text-green-600" : "text-red-500"}`}>
                        {pnlPct === null ? "—" : `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%`}
                      </td>
                      <td className="px-4 py-3 text-right text-red-500">{h.stop_loss_price.toFixed(2)}</td>
                      <td className="px-4 py-3 text-right text-green-600">{h.take_profit_price.toFixed(2)}</td>
                      <td className="px-4 py-3 text-center">
                        <TrendBadge trend={trend} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

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
                </tr>
              </thead>
              <tbody>
                {allStocks.map((s, i) => (
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
                      <TrendBadge trend={trends[s.ticker]} />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${REC_BADGE[s.recommendation] ?? REC_BADGE["不推薦"]}`}>
                        {s.recommendation}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
