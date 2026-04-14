"use client"

import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import type { StrategyMemoryResponse } from "@/lib/api"
import Link from "next/link"

const RISK_BADGE: Record<string, string> = {
  "low": "bg-green-100 text-green-700",
  "medium": "bg-yellow-100 text-yellow-700",
  "high": "bg-red-100 text-red-700",
}

export default function StrategyMemoryPage() {
  const [data, setData] = useState<StrategyMemoryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.strategyMemory()
      .then(setData)
      .catch((err) => {
        console.error("Failed to fetch strategy memory:", err)
        setError(err.message)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto space-y-6 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-10 bg-slate-200 rounded w-1/3"></div>
          <div className="h-6 bg-slate-100 rounded w-2/3"></div>
          <div className="grid grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-32 bg-slate-100 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto py-8">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">錯誤: {error}</p>
        </div>
      </div>
    )
  }

  const hasData = data && data.total_analyzed > 0

  return (
    <div className="max-w-6xl mx-auto space-y-6 py-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Link
            href="/strategies"
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            策略
          </Link>
          <span className="text-slate-300">/</span>
          <span className="text-sm text-slate-600">學習記錄</span>
        </div>
        <h1 className="text-3xl font-bold text-slate-800">策略學習記錄</h1>
        <p className="text-slate-600 mt-2">
          系統從歷史交易中學習失敗模式和策略效果
        </p>
      </div>

      {!hasData ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-center">
          <p className="text-sm text-amber-700">
            尚無足夠歷史資料，請持續記錄 AI 分析筆記
          </p>
        </div>
      ) : (
        <>
          {/* Top Failure Patterns */}
          {data.top_failure_patterns.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold text-slate-800 mb-3">
                ⚠️ 高失敗率模式
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {data.top_failure_patterns.map((pattern, idx) => (
                  <div
                    key={idx}
                    className={`rounded-lg border-2 p-4 ${
                      pattern.failure_rate > 0.7
                        ? "border-red-300 bg-red-50"
                        : "border-orange-300 bg-orange-50"
                    }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <p className="text-sm font-semibold text-slate-800">
                          {pattern.condition}
                        </p>
                      </div>
                      <span
                        className={`text-lg font-bold ${
                          pattern.failure_rate > 0.7
                            ? "text-red-600"
                            : "text-orange-600"
                        }`}
                      >
                        {(pattern.failure_rate * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 mb-2">
                      平均損失: <span className="font-medium">{pattern.avg_loss_pct.toFixed(2)}%</span>
                    </p>
                    <p className="text-xs font-medium text-slate-700 italic">
                      "{pattern.warning}"
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Strategy Patterns Table */}
          {data.patterns.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold text-slate-800 mb-3">
                📊 策略模式分析
              </h2>
              <div className="rounded-lg border border-slate-200 overflow-x-auto shadow-sm">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50">
                      <th className="px-4 py-3 text-left font-semibold text-slate-700">
                        市場條件
                      </th>
                      <th className="px-4 py-3 text-left font-semibold text-slate-700">
                        推薦等級
                      </th>
                      <th className="px-4 py-3 text-center font-semibold text-slate-700">
                        樣本數
                      </th>
                      <th className="px-4 py-3 text-center font-semibold text-slate-700">
                        勝率
                      </th>
                      <th className="px-4 py-3 text-center font-semibold text-slate-700">
                        平均回報
                      </th>
                      <th className="px-4 py-3 text-center font-semibold text-slate-700">
                        風險等級
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.patterns.map((pattern, idx) => (
                      <tr
                        key={idx}
                        className="border-b border-slate-100 hover:bg-slate-50 transition-colors"
                      >
                        <td className="px-4 py-3 text-slate-700">
                          {pattern.smc_trend}
                        </td>
                        <td className="px-4 py-3 text-slate-700">
                          {pattern.recommendation}
                        </td>
                        <td className="px-4 py-3 text-center text-slate-600">
                          {pattern.sample_count}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span
                            className={`inline-block font-bold px-2 py-1 rounded ${
                              pattern.win_rate > 0.6
                                ? "bg-green-100 text-green-700"
                                : pattern.win_rate > 0.4
                                ? "bg-yellow-100 text-yellow-700"
                                : "bg-red-100 text-red-700"
                            }`}
                          >
                            {(pattern.win_rate * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span
                            className={`font-medium ${
                              pattern.avg_return_pct >= 0
                                ? "text-green-600"
                                : "text-red-600"
                            }`}
                          >
                            {pattern.avg_return_pct >= 0 ? "+" : ""}
                            {pattern.avg_return_pct.toFixed(2)}%
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span
                            className={`inline-block text-xs px-2 py-1 rounded font-medium ${
                              RISK_BADGE[pattern.risk_level] ||
                              "bg-slate-100 text-slate-600"
                            }`}
                          >
                            {pattern.risk_level}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                已分析 {data.total_analyzed} 筆 AI 分析記錄
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
