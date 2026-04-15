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

export default function MemoryDashboard() {
  const [summary, setSummary] = useState<MemorySummary | null>(null)
  const [crossStats, setCrossStats] = useState<CrossStat[]>([])
  const [activeTab, setActiveTab] = useState("1d")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

  return (
    <div className="p-8 max-w-6xl mx-auto">
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

      {/* 勝率熱力圖 */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-bold mb-4">勝率熱力圖（場景 × 類別）</h2>
        {crossStats.length === 0 ? (
          <div className="text-gray-500">暫無資料</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2">場景</th>
                  <th className="text-left p-2">類別</th>
                  <th className="text-right p-2">勝率</th>
                  <th className="text-right p-2">樣本數</th>
                </tr>
              </thead>
              <tbody>
                {crossStats.map((row, i) => (
                  <tr key={i} className="border-b hover:bg-gray-50">
                    <td className="p-2">{row.scenario}</td>
                    <td className="p-2">{row.category}</td>
                    <td className="text-right p-2">
                      <span className={`inline-block px-2 py-1 rounded text-white ${
                        row.win_rate >= 0.6 ? 'bg-green-500' : row.win_rate >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'
                      }`}>
                        {(row.win_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="text-right p-2">{row.sample_count}</td>
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
