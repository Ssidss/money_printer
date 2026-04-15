"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"

interface MemorySummary {
  total_count: number
  weekly_new: number
  by_timeframe: Record<string, number>
}

interface CrossStat {
  scenario: string
  category: string
  win_rate: number
  sample_count: number
}

const getWinRateColor = (winRate: number): string => {
  if (winRate >= 0.6) return "#10b981"  // green-500
  if (winRate >= 0.5) return "#eab308"  // yellow-500
  return "#ef4444"  // red-500
}

export default function MemoryDashboard() {
  const [summary, setSummary] = useState<MemorySummary | null>(null)
  const [crossStats, setCrossStats] = useState<CrossStat[]>([])
  const [activeTab, setActiveTab] = useState("1d")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hoveredCell, setHoveredCell] = useState<{ scenario: string; category: string } | null>(null)

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true)
        const [summary, cross] = await Promise.all([
          api.getMemoryStats(),
          api.getCrossStats(activeTab),
        ])
        setSummary(summary)
        setCrossStats(cross.data || [])
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load memory data")
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [activeTab])

  if (loading) return <div className="p-8">加載中...</div>
  if (error) return <div className="p-8 text-red-500">錯誤: {error}</div>

  // Get unique scenarios and categories for heatmap layout
  const scenarios = Array.from(new Set(crossStats.map(s => s.scenario)))
  const categories = Array.from(new Set(crossStats.map(s => s.category)))

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">記憶儀表板</h1>

      {/* 統計卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-blue-50 p-6 rounded-lg">
          <div className="text-sm text-gray-600">總記憶數</div>
          <div className="text-3xl font-bold text-blue-600">{summary?.total_count || 0}</div>
        </div>
        <div className="bg-green-50 p-6 rounded-lg">
          <div className="text-sm text-gray-600">本週新增</div>
          <div className="text-3xl font-bold text-green-600">{summary?.weekly_new || 0}</div>
        </div>
        <div className="bg-purple-50 p-6 rounded-lg">
          <div className="text-sm text-gray-600">時間框架</div>
          <div className="text-sm mt-2 space-y-1">
            {summary?.by_timeframe && Object.entries(summary.by_timeframe).map(([tf, count]) => (
              <div key={tf} className="flex justify-between">
                <span>{tf}</span>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 mb-6">
        {["1d", "4h", "1h"].map((tf) => (
          <button
            key={tf}
            onClick={() => setActiveTab(tf)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              activeTab === tf
                ? "bg-blue-600 text-white"
                : "bg-gray-200 text-gray-800 hover:bg-gray-300"
            }`}
          >
            {tf}
          </button>
        ))}
      </div>

      {/* 勝率熱力圖（互動版） */}
      <div className="bg-white p-6 rounded-lg shadow mb-8">
        <h2 className="text-xl font-bold mb-4">勝率熱力圖（場景 × 類別）</h2>
        {crossStats.length === 0 ? (
          <div className="text-gray-500 py-8">暫無資料</div>
        ) : (
          <div className="overflow-x-auto">
            <div className="inline-block min-w-full">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr>
                    <th className="p-2 text-left font-semibold border">場景</th>
                    {categories.map((cat) => (
                      <th key={cat} className="p-2 text-center font-semibold border bg-gray-50">
                        {cat}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {scenarios.map((scenario) => (
                    <tr key={scenario}>
                      <td className="p-2 font-medium border bg-gray-50">{scenario}</td>
                      {categories.map((category) => {
                        const stat = crossStats.find(s => s.scenario === scenario && s.category === category)
                        const isHovered = hoveredCell?.scenario === scenario && hoveredCell?.category === category
                        return (
                          <td
                            key={`${scenario}-${category}`}
                            className={`p-2 text-center border cursor-pointer transition-all ${
                              isHovered ? "ring-2 ring-blue-500" : ""
                            }`}
                            style={{ backgroundColor: stat ? `${getWinRateColor(stat.win_rate)}20` : "transparent" }}
                            onMouseEnter={() => setHoveredCell({ scenario, category })}
                            onMouseLeave={() => setHoveredCell(null)}
                            title={stat ? `勝率: ${(stat.win_rate * 100).toFixed(1)}%, 樣本: ${stat.sample_count}` : "無資料"}
                          >
                            {stat ? (
                              <div>
                                <div className="font-semibold text-xs" style={{ color: getWinRateColor(stat.win_rate) }}>
                                  {(stat.win_rate * 100).toFixed(1)}%
                                </div>
                                <div className="text-xs text-gray-600">
                                  ({stat.sample_count})
                                </div>
                              </div>
                            ) : (
                              <span className="text-gray-400">-</span>
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* 詳細規則列表 */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-bold mb-4">詳細數據</h2>
        {crossStats.length === 0 ? (
          <div className="text-gray-500">暫無資料</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left p-3 font-semibold">場景</th>
                  <th className="text-left p-3 font-semibold">類別</th>
                  <th className="text-right p-3 font-semibold">勝率</th>
                  <th className="text-right p-3 font-semibold">樣本數</th>
                </tr>
              </thead>
              <tbody>
                {crossStats.map((row, i) => (
                  <tr key={i} className="border-b hover:bg-gray-50">
                    <td className="p-3">{row.scenario}</td>
                    <td className="p-3">{row.category}</td>
                    <td className="text-right p-3">
                      <span
                        className="inline-block px-2 py-1 rounded text-white font-semibold"
                        style={{ backgroundColor: getWinRateColor(row.win_rate) }}
                      >
                        {(row.win_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="text-right p-3">{row.sample_count}</td>
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
