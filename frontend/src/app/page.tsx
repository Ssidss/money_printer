import { api } from "@/lib/api"
import { AnalyzeButton } from "@/components/dashboard/AnalyzeButton"
import { BatchFetchButton } from "@/components/dashboard/BatchFetchButton"
import { TopPickCard } from "@/components/dashboard/TopPickCard"
import { HoldingsSection } from "@/components/dashboard/HoldingsSection"
import { StrategySignalsSummary } from "@/components/dashboard/StrategySignalsSummary"
import { DashboardStockTable } from "@/components/dashboard/DashboardStockTable"
import type { TopPick, SmcTrendMTF } from "@/lib/api"

export const revalidate = 60

export default async function Dashboard() {
  const [picks, latest, statusRes, trendsRes, pricesRes] = await Promise.allSettled([
    api.topPicks(3),
    api.latestAnalysis(),
    api.analysisStatus(),
    api.smcTrendsMTF(),
    api.latestPrices(),
  ])

  const topPicks     = picks.status === "fulfilled" ? picks.value : []
  const latestRes    = latest.status === "fulfilled" ? latest.value : null
  const isRunning    = statusRes.status === "fulfilled" ? statusRes.value.running : false
  const trendsMTF    = trendsRes.status === "fulfilled" ? trendsRes.value : {} as Record<string, SmcTrendMTF>
  const latestPrices = pricesRes.status === "fulfilled" ? pricesRes.value : null
  const allStocks: TopPick[] = latestRes?.results ?? []

  // 建立 ticker → close_price 的映射（優先用 price_history 最新收盤價）
  const priceMap: Record<string, number> = {}
  const priceDateMap: Record<string, string> = {}
  for (const s of allStocks) priceMap[s.ticker] = s.close_price
  // 用 latest-prices 覆蓋（更即時）
  if (latestPrices?.prices) {
    for (const [ticker, p] of Object.entries(latestPrices.prices)) {
      if (p.close != null) {
        priceMap[ticker] = p.close
        priceDateMap[ticker] = p.date
      }
    }
  }

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
      <HoldingsSection
        priceMap={priceMap}
        priceDateMap={priceDateMap}
        marketStatus={latestPrices?.market_status ?? null}
        trendsMTF={trendsMTF}
      />

      {/* 策略信號總覽 — client component，即時載入 batch signals */}
      <StrategySignalsSummary />

      {/* All Tracked Stocks */}
      <div>
        <h2 className="text-lg font-semibold text-slate-800 mb-4">
          追蹤股票清單
          <span className="ml-2 text-sm font-normal text-slate-400">({allStocks.length} 支)</span>
        </h2>
        <DashboardStockTable stocks={allStocks} trendsMTF={trendsMTF} />
      </div>
    </div>
  )
}
