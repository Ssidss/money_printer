import { api } from "@/lib/api"
import type { TopPick, Stock, AiNoteLatest, SmcTrendMTF } from "@/lib/api"
import { AddStockModal } from "@/components/stocks/AddStockModal"
import { StocksTable } from "@/components/stocks/StocksTable"

export const revalidate = 0

type MergedStock = Stock & Partial<TopPick>

export default async function StocksPage() {
  const [stocksData, latestData, trendsData, aiNotesData] = await Promise.allSettled([
    api.stocks(),
    api.latestAnalysis(),
    api.smcTrendsMTF(),
    api.aiNotesLatest(),
  ])

  const allTracked: Stock[] = stocksData.status === "fulfilled" ? stocksData.value : []
  const latest = latestData.status === "fulfilled" ? latestData.value : { date: null, results: [] as TopPick[] }
  const trendsMTF: Record<string, SmcTrendMTF> = trendsData.status === "fulfilled" ? trendsData.value : {}
  const aiNotes: Record<string, AiNoteLatest> = aiNotesData.status === "fulfilled" ? aiNotesData.value : {}

  // 建立分析資料 map
  const analysisMap: Record<string, TopPick> = {}
  for (const s of latest.results) analysisMap[s.ticker] = s

  // 合併：以 allTracked 為主，補上分析 + entry_suggestion
  const merged: MergedStock[] = allTracked.map(s => ({
    ...s,
    ...(analysisMap[s.ticker] ?? {}),
  }))

  const analysisDone = latest.results.length > 0

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">股票清單</h1>
          <p className="text-slate-500 text-sm mt-1">
            共追蹤 {allTracked.length} 支
            {latest.date && <span className="ml-2 text-slate-400">· 最新分析：{latest.date}</span>}
          </p>
        </div>
        <AddStockModal />
      </div>

      <StocksTable stocks={merged} trendsMTF={trendsMTF} analysisDone={analysisDone} aiNotes={aiNotes} />
    </div>
  )
}
