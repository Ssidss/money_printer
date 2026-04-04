import Link from "next/link"
import { api } from "@/lib/api"
import { BuyModal } from "@/components/portfolio/BuyModal"
import { SellModal } from "@/components/portfolio/SellModal"
import type { TopPick } from "@/lib/api"

export const revalidate = 0

const TREND_STYLE: Record<string, string> = {
  "上升趨勢": "bg-green-100 text-green-700",
  "下降趨勢": "bg-red-100 text-red-500",
  "盤整":     "bg-yellow-100 text-yellow-700",
  "未知":     "bg-slate-100 text-slate-400",
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

export default async function PortfolioPage() {
  const [holdings, txns, latestRes, trendsRes] = await Promise.allSettled([
    api.holdings(),
    api.transactions(),
    api.latestAnalysis(),
    api.smcTrends(),
  ])
  const holdingsList = holdings.status === "fulfilled" ? holdings.value : []
  const txnList      = txns.status === "fulfilled" ? txns.value : []
  const allStocks: TopPick[] = latestRes.status === "fulfilled" ? latestRes.value.results ?? [] : []
  const trends       = trendsRes.status === "fulfilled" ? trendsRes.value : {} as Record<string, string>

  // 建立 ticker → close_price 映射
  const priceMap: Record<string, number> = {}
  for (const s of allStocks) priceMap[s.ticker] = s.close_price

  const totalCost   = holdingsList.reduce((s, h) => s + h.cost_basis, 0)

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">投資組合</h1>
          <p className="text-slate-500 text-sm mt-1">持倉管理 · 買賣紀錄</p>
        </div>
        <BuyModal />
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "持倉檔數",   value: `${holdingsList.length} 支` },
          { label: "總投入成本", value: totalCost > 0 ? `$${totalCost.toLocaleString()}` : "—" },
          { label: "交易筆數",   value: `${txnList.length} 筆` },
        ].map((s) => (
          <div key={s.label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-slate-500 text-xs uppercase tracking-wide">{s.label}</p>
            <p className="text-2xl font-bold text-slate-800 mt-1">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Holdings */}
      <div>
        <h2 className="text-lg font-semibold text-slate-800 mb-4">目前持倉</h2>
        {holdingsList.length === 0 ? (
          <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-slate-400">
            尚無持倉，點擊右上角「買入」建立第一筆
          </div>
        ) : (
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs uppercase tracking-wide">
                  <th className="text-left px-4 py-3">股票</th>
                  <th className="text-right px-4 py-3">持股</th>
                  <th className="text-right px-4 py-3">當前價</th>
                  <th className="text-right px-4 py-3">均成本</th>
                  <th className="text-right px-4 py-3">損益</th>
                  <th className="text-right px-4 py-3">投入金額</th>
                  <th className="text-right px-4 py-3">停損價</th>
                  <th className="text-right px-4 py-3">停利價</th>
                  <th className="text-center px-4 py-3">SMC 趨勢</th>
                  <th className="text-center px-4 py-3">操作</th>
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
                      <Link href={`/stocks/${h.ticker}`} className="font-semibold text-indigo-600 hover:text-indigo-800 hover:underline">
                        {h.ticker}
                      </Link>
                      <span className="ml-2 text-xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">{h.market}</span>
                      {isNearStop && <span className="ml-2 text-xs text-red-500 font-medium">⚠ 接近停損</span>}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">{h.shares}</td>
                    <td className="px-4 py-3 text-right font-medium text-slate-800">
                      {curr ? curr.toFixed(2) : "—"}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-500">{h.avg_cost.toFixed(2)}</td>
                    <td className={`px-4 py-3 text-right font-semibold ${pnlPct === null ? "text-slate-400" : pnlPct >= 0 ? "text-green-600" : "text-red-500"}`}>
                      {pnlPct === null ? "—" : `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%`}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">${h.cost_basis.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-red-500 font-medium">{h.stop_loss_price.toFixed(2)}</td>
                    <td className="px-4 py-3 text-right text-green-600 font-medium">{h.take_profit_price.toFixed(2)}</td>
                    <td className="px-4 py-3 text-center">
                      <TrendBadge trend={trend} />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <SellModal ticker={h.ticker} shares={h.shares} />
                    </td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Transaction History */}
      {txnList.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-slate-800 mb-4">交易紀錄</h2>
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs uppercase tracking-wide">
                  <th className="text-left px-4 py-3">日期</th>
                  <th className="text-left px-4 py-3">股票</th>
                  <th className="text-center px-4 py-3">動作</th>
                  <th className="text-right px-4 py-3">股數</th>
                  <th className="text-right px-4 py-3">價格</th>
                  <th className="text-right px-4 py-3">金額</th>
                  <th className="text-left px-4 py-3">備註</th>
                </tr>
              </thead>
              <tbody>
                {txnList.slice(0, 50).map((t) => (
                  <tr key={t.id} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-500">{t.date}</td>
                    <td className="px-4 py-3 font-medium text-slate-800">{t.ticker}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${t.action === "buy" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                        {t.action === "buy" ? "買入" : "賣出"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">{t.shares}</td>
                    <td className="px-4 py-3 text-right text-slate-700">{t.price.toFixed(2)}</td>
                    <td className="px-4 py-3 text-right text-slate-700">${t.total.toLocaleString()}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{t.note || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
