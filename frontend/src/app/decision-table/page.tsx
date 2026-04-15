"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"

interface DecisionRule {
  scenario: string
  stock_category: string
  action: string
  stop_loss_pct: number
  take_profit_pct: number
  win_rate: number
  sample_size: number
  confidence: number
}

interface DecisionTable {
  version: number
  generated_at: string
  timeframe: string
  rules: DecisionRule[]
}

export default function DecisionTablePage() {
  const [table, setTable] = useState<DecisionTable | null>(null)
  const [versions, setVersions] = useState<Array<{ version: number; generated_at: string }>>([])
  const [activeTab, setActiveTab] = useState("1d")
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true)
        const [table, versions] = await Promise.all([
          api.getDecisionTable(activeTab),
          api.getDecisionTableVersions(activeTab),
        ])
        setTable(table)
        setVersions(versions)
        setSelectedVersion(table.version)
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load decision table")
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [activeTab])

  if (loading) return <div className="p-8">加載中...</div>
  if (error) return <div className="p-8 text-red-500">錯誤: {error}</div>

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">決策表</h1>

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

      {table && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex justify-between items-center">
            <div>
              <p className="text-sm text-gray-600">當前版本</p>
              <p className="text-xl font-bold">版本 {table.version}</p>
              <p className="text-sm text-gray-600">{new Date(table.generated_at).toLocaleString("zh-TW")}</p>
            </div>
            <button className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              生成新版本
            </button>
          </div>
        </div>
      )}

      {/* 規則表格 */}
      <div className="bg-white p-6 rounded-lg shadow overflow-x-auto">
        <h2 className="text-xl font-bold mb-4">規則清單</h2>
        {table?.rules && table.rules.length > 0 ? (
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left p-3 font-semibold">場景</th>
                <th className="text-left p-3 font-semibold">類別</th>
                <th className="text-center p-3 font-semibold">動作</th>
                <th className="text-right p-3 font-semibold">停損%</th>
                <th className="text-right p-3 font-semibold">停利%</th>
                <th className="text-right p-3 font-semibold">勝率</th>
                <th className="text-right p-3 font-semibold">樣本</th>
                <th className="text-right p-3 font-semibold">信心</th>
              </tr>
            </thead>
            <tbody>
              {table.rules.map((rule, i) => (
                <tr key={i} className="border-b hover:bg-gray-50">
                  <td className="p-3">{rule.scenario}</td>
                  <td className="p-3">{rule.stock_category}</td>
                  <td className="text-center p-3">
                    <span className={`inline-block px-2 py-1 rounded text-white text-xs font-bold ${
                      rule.action === "BUY" ? "bg-green-600" :
                      rule.action === "SELL" ? "bg-red-600" :
                      "bg-gray-600"
                    }`}>
                      {rule.action}
                    </span>
                  </td>
                  <td className="text-right p-3">{(rule.stop_loss_pct * 100).toFixed(2)}%</td>
                  <td className="text-right p-3">{(rule.take_profit_pct * 100).toFixed(2)}%</td>
                  <td className="text-right p-3 font-semibold text-blue-600">{(rule.win_rate * 100).toFixed(1)}%</td>
                  <td className="text-right p-3">{rule.sample_size}</td>
                  <td className="text-right p-3">{(rule.confidence * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-gray-500">暫無規則</div>
        )}
      </div>

      {/* 版本歷史 */}
      {versions.length > 0 && (
        <div className="mt-8 bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-bold mb-4">版本歷史</h2>
          <div className="flex gap-2 flex-wrap">
            {versions.map((v) => (
              <button
                key={v.version}
                onClick={() => setSelectedVersion(v.version)}
                className={`px-3 py-2 rounded border transition-colors ${
                  selectedVersion === v.version
                    ? "bg-blue-600 text-white border-blue-600"
                    : "border-gray-300 hover:border-blue-600"
                }`}
              >
                <div className="text-sm font-semibold">v{v.version}</div>
                <div className="text-xs text-gray-600">{new Date(v.generated_at).toLocaleDateString()}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
