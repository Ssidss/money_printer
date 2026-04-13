"use client"

import { useState, useEffect, useCallback } from "react"
import Link from "next/link"
import { api } from "@/lib/api"
import type { Holding, Transaction, TopPick } from "@/lib/api"
import { BuyModal } from "./BuyModal"
import { SellModal } from "./SellModal"

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

/** 根據 SMC 趨勢 + 分析分數 + 當前損益 計算建議操作 */
function computeAction(
  ticker: string,
  pnlPct: number | null,
  trend: string | undefined,
  analysis: TopPick | undefined,
  stopLossPrice: number,
  currentPrice: number | undefined,
): { label: string; color: string; detail: string } {
  if (!currentPrice) return { label: "無資料", color: "text-slate-400", detail: "無法取得當前價格" }

  const t = trend ?? "未知"
  const score = analysis?.composite_score
  const rec = analysis?.recommendation
  const pnl = pnlPct ?? 0

  // 優先：接近或跌破停損 → 停損出場
  if (currentPrice <= stopLossPrice) {
    return { label: "停損出場", color: "text-red-600 font-bold", detail: "已觸及停損價位" }
  }
  if (currentPrice <= stopLossPrice * 1.03) {
    return { label: "考慮停損", color: "text-red-500", detail: "接近停損價位" }
  }

  // SMC 下降趨勢 + 有獲利 → 獲利了結
  if (t === "下降趨勢" && pnl > 0) {
    return { label: "獲利了結", color: "text-orange-600", detail: "SMC 轉下降趨勢，建議保住獲利" }
  }
  // SMC 下降趨勢 + 虧損 → 減倉
  if (t === "下降趨勢" && pnl <= 0) {
    return { label: "減倉", color: "text-orange-500", detail: "SMC 下降趨勢且虧損中" }
  }

  // 高分 + 上升趨勢 → 加碼
  if (score && score >= 65 && t === "上升趨勢" && (rec === "強力推薦" || rec === "推薦")) {
    return { label: "加碼", color: "text-green-600", detail: `綜合分 ${score.toFixed(0)}，趨勢向上` }
  }

  // 盤整 + 有獲利 → 持有觀察
  if (t === "盤整" && pnl > 5) {
    return { label: "持有觀察", color: "text-yellow-600", detail: "盤整中，注意是否轉向" }
  }

  // 上升趨勢 → 持有
  if (t === "上升趨勢") {
    return { label: "持有", color: "text-green-500", detail: "趨勢向上，繼續持有" }
  }

  // 預設
  return { label: "持有觀察", color: "text-slate-600", detail: score ? `綜合分 ${score.toFixed(0)}` : "等待分析資料" }
}

export function PortfolioClient() {
  const [holdingsList, setHoldings] = useState<Holding[]>([])
  const [txnList, setTxns] = useState<Transaction[]>([])
  const [allStocks, setAllStocks] = useState<TopPick[]>([])
  const [trends, setTrends] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)

  const [latestPriceMap, setLatestPriceMap] = useState<Record<string, number>>({})
  const [priceDateMap, setPriceDateMap] = useState<Record<string, string>>({})

  const fetchAll = useCallback(async () => {
    try {
      const [h, t, a, tr, lp] = await Promise.allSettled([
        api.holdings(),
        api.transactions(),
        api.latestAnalysis(),
        api.smcTrends(),
        api.latestPrices(),
      ])
      if (h.status === "fulfilled") setHoldings(h.value)
      if (t.status === "fulfilled") setTxns(t.value)
      if (a.status === "fulfilled") setAllStocks(a.value.results ?? [])
      if (tr.status === "fulfilled") setTrends(tr.value)
      if (lp.status === "fulfilled" && lp.value.prices) {
        const pm: Record<string, number> = {}
        const dm: Record<string, string> = {}
        for (const [ticker, p] of Object.entries(lp.value.prices)) {
          if (p.close != null) { pm[ticker] = p.close; dm[ticker] = p.date }
        }
        setLatestPriceMap(pm)
        setPriceDateMap(dm)
      }
      setLastRefresh(new Date())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const iv = setInterval(fetchAll, 30_000) // 每 30 秒自動刷新
    return () => clearInterval(iv)
  }, [fetchAll])

  // 建立 ticker → analysis 映射
  const analysisMap: Record<string, TopPick> = {}
  const priceMap: Record<string, number> = {}
  for (const s of allStocks) {
    analysisMap[s.ticker] = s
    priceMap[s.ticker] = s.close_price
  }
  // 用 latest-prices 覆蓋（更即時）
  for (const [ticker, price] of Object.entries(latestPriceMap)) {
    priceMap[ticker] = price
  }

  const totalCost = holdingsList.reduce((s, h) => s + h.cost_basis, 0)
  const totalValue = holdingsList.reduce((s, h) => {
    const p = priceMap[h.ticker]
    return s + (p ? p * h.shares : h.cost_basis)
  }, 0)
  const totalPnl = totalCost > 0 ? ((totalValue - totalCost) / totalCost * 100) : 0

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto flex items-center justify-center py-24">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-3" />
          <p className="text-slate-400 text-sm">載入投資組合...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">投資組合</h1>
          <p className="text-slate-500 text-sm mt-1">
            持倉管理 · 買賣紀錄
            {lastRefresh && (
              <span className="ml-3 text-slate-400">
                最後更新: {lastRefresh.toLocaleTimeString("zh-TW")}
                <button onClick={fetchAll} className="ml-2 text-indigo-500 hover:text-indigo-700 underline">刷新</button>
              </span>
            )}
          </p>
        </div>
        <BuyModal />
      </div>

      {/* Summary */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "持倉檔數",   value: `${holdingsList.length} 支` },
          { label: "總投入成本", value: totalCost > 0 ? `$${totalCost.toLocaleString()}` : "—" },
          { label: "總市值",     value: totalValue > 0 ? `$${Math.round(totalValue).toLocaleString()}` : "—" },
          { label: "總損益",     value: totalCost > 0 ? `${totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}%` : "—",
            color: totalPnl >= 0 ? "text-green-600" : "text-red-500" },
        ].map((s) => (
          <div key={s.label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-slate-500 text-xs uppercase tracking-wide">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${"color" in s ? s.color : "text-slate-800"}`}>{s.value}</p>
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
                  <th className="text-center px-4 py-3">SMC 趨勢</th>
                  <th className="text-center px-4 py-3">建議操作</th>
                  <th className="text-center px-4 py-3">操作</th>
                </tr>
              </thead>
              <tbody>
                {holdingsList.map((h) => {
                  const curr = priceMap[h.ticker]
                  const pnlPct = curr ? ((curr - h.avg_cost) / h.avg_cost * 100) : null
                  const trend = trends[h.ticker]
                  const isNearStop = curr != null && curr <= h.stop_loss_price * 1.03
                  const action = computeAction(
                    h.ticker, pnlPct, trend, analysisMap[h.ticker],
                    h.stop_loss_price, curr,
                  )
                  return (
                  <tr key={h.ticker} className={`border-t border-slate-100 hover:bg-slate-50 ${isNearStop ? "bg-red-50/50" : ""}`}>
                    <td className="px-4 py-3">
                      <Link href={`/stocks/${h.ticker}`} className="font-semibold text-indigo-600 hover:text-indigo-800 hover:underline">
                        {h.ticker}
                      </Link>
                      {h.name && <span className="ml-1.5 text-xs text-slate-400">{h.name}</span>}
                      <span className="ml-2 text-xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">{h.market}</span>
                      {isNearStop && <span className="ml-2 text-xs text-red-500 font-medium animate-pulse">⚠ 接近停損</span>}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">{h.shares}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="font-medium text-slate-800">{curr ? curr.toFixed(2) : "—"}</div>
                      {priceDateMap[h.ticker] && (
                        <div className="text-[10px] text-slate-400">{priceDateMap[h.ticker].slice(5)} 收盤</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-500">{h.avg_cost.toFixed(2)}</td>
                    <td className={`px-4 py-3 text-right font-semibold ${pnlPct === null ? "text-slate-400" : pnlPct >= 0 ? "text-green-600" : "text-red-500"}`}>
                      {pnlPct === null ? "—" : `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%`}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">${h.cost_basis.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-red-500 font-medium">{h.stop_loss_price.toFixed(2)}</td>
                    <td className="px-4 py-3 text-center">
                      <TrendBadge trend={trend} />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="group relative">
                        <span className={`text-xs font-semibold ${action.color}`}>
                          {action.label}
                        </span>
                        <div className="hidden group-hover:block absolute z-10 bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-slate-800 text-white text-xs rounded whitespace-nowrap">
                          {action.detail}
                        </div>
                      </div>
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
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${t.action === "buy" || t.action === "BUY" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                        {t.action === "buy" || t.action === "BUY" ? "買入" : "賣出"}
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
