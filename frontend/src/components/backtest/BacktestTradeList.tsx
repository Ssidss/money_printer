"use client"
import { useState } from "react"
import type { BacktestV3Trade } from "@/lib/api"

interface BacktestTradeListProps {
  trades: BacktestV3Trade[]
}

export function BacktestTradeList({ trades }: BacktestTradeListProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null)

  // 篩選已平倉的交易
  const closedTrades = trades.filter(t => t.exit_date && t.exit_price !== null)

  if (closedTrades.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-400 shadow-sm">
        無交易紀錄
      </div>
    )
  }

  // 限制顯示前 20 筆
  const displayTrades = closedTrades.slice(0, 20)

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="p-4 border-b border-slate-200">
        <h3 className="text-sm font-semibold text-slate-800">交易清單 (顯示前 {displayTrades.length} 筆，共 {closedTrades.length} 筆)</h3>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs uppercase tracking-wide">
              <th className="text-left px-4 py-3">股票</th>
              <th className="text-left px-4 py-3">策略</th>
              <th className="text-left px-4 py-3">入場日期</th>
              <th className="text-right px-4 py-3">入場價</th>
              <th className="text-left px-4 py-3">出場日期</th>
              <th className="text-right px-4 py-3">出場價</th>
              <th className="text-right px-4 py-3">報酬率</th>
              <th className="text-right px-4 py-3">持有天數</th>
            </tr>
          </thead>
          <tbody>
            {displayTrades.map((trade, idx) => {
              const returnPct = trade.pnl_pct !== null ? trade.pnl_pct : 0
              const isProfit = returnPct >= 0
              const entryDate = new Date(trade.entry_date)
              const exitDate = trade.exit_date ? new Date(trade.exit_date) : null

              return (
                <tr
                  key={idx}
                  className={`border-t border-slate-100 hover:bg-slate-50 transition-colors cursor-pointer`}
                  onClick={() => setExpandedId(expandedId === idx ? null : idx)}
                >
                  <td className="px-4 py-3 font-medium text-slate-800">{trade.ticker}</td>
                  <td className="px-4 py-3 text-slate-600 text-xs">{trade.strategy_name}</td>
                  <td className="px-4 py-3 text-slate-600">{entryDate.toLocaleDateString("zh-TW")}</td>
                  <td className="px-4 py-3 text-right text-slate-600">${trade.entry_price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-slate-600">{exitDate ? exitDate.toLocaleDateString("zh-TW") : "—"}</td>
                  <td className="px-4 py-3 text-right text-slate-600">${trade.exit_price ? trade.exit_price.toFixed(2) : "—"}</td>
                  <td className={`px-4 py-3 text-right font-semibold ${isProfit ? "text-green-600" : "text-red-500"}`}>
                    {isProfit ? "+" : ""}{returnPct.toFixed(2)}%
                  </td>
                  <td className="px-4 py-3 text-right text-slate-500">{trade.holding_days} 天</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {closedTrades.length > 20 && (
        <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 text-center text-xs text-slate-500">
          顯示 {displayTrades.length} / {closedTrades.length} 筆交易
        </div>
      )}
    </div>
  )
}
