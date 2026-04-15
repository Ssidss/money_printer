"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import { usePipelineProgress } from "@/hooks/usePipelineProgress"

interface PipelineFormData {
  symbols: string[]
  train_start: string
  train_end: string
  val_start: string
  val_end: string
  strategies: string[]
  timeframe: string
  max_iterations: number
  convergence_threshold: number
}

interface ValidationReport {
  symbols: string[]
  total_trades: number
  total_wins: number
  total_losses: number
  avg_win_rate: number
  avg_return: number
}

export default function PipelinePage() {
  const [formData, setFormData] = useState<PipelineFormData>({
    symbols: ["2330", "2454"],
    train_start: "2024-01-01",
    train_end: "2024-12-31",
    val_start: "2025-01-01",
    val_end: "2025-03-31",
    strategies: ["smc_v2"],
    timeframe: "1d",
    max_iterations: 5,
    convergence_threshold: 0.02,
  })

  const [status, setStatus] = useState<{ running: boolean; current_iteration: number; win_rate_history: number[]; status: string } | null>(null)
  const [report, setReport] = useState<ValidationReport | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { events, isConnected } = usePipelineProgress()

  // Refresh status periodically
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const s = await api.getPipelineStatus()
        setStatus(s)
        setRunning(s.running)

        if (s.status === "completed") {
          const r = await api.getPipelineReport()
          setReport(r)
        }
      } catch (e) {
        console.error("Failed to fetch status", e)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  async function handleStart() {
    try {
      setError(null)
      setRunning(true)
      const result = await api.triggerPipeline(formData)
      console.log("Pipeline started:", result)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start pipeline")
      setRunning(false)
    }
  }

  function handleSymbolChange(value: string) {
    setFormData({ ...formData, symbols: value.split(",").map((s) => s.trim()) })
  }

  function handleStrategyChange(value: string) {
    setFormData({ ...formData, strategies: value.split(",").map((s) => s.trim()) })
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">回測迭代 Pipeline</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* 設定表單 */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-bold mb-4">設定</h2>
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); handleStart() }}>
            <div>
              <label className="block text-sm font-medium mb-1">股票代碼（逗號分隔）</label>
              <input
                type="text"
                value={formData.symbols.join(", ")}
                onChange={(e) => handleSymbolChange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="2330, 2454"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">訓練開始日</label>
                <input
                  type="date"
                  value={formData.train_start}
                  onChange={(e) => setFormData({ ...formData, train_start: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">訓練結束日</label>
                <input
                  type="date"
                  value={formData.train_end}
                  onChange={(e) => setFormData({ ...formData, train_end: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">驗證開始日</label>
                <input
                  type="date"
                  value={formData.val_start}
                  onChange={(e) => setFormData({ ...formData, val_start: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">驗證結束日</label>
                <input
                  type="date"
                  value={formData.val_end}
                  onChange={(e) => setFormData({ ...formData, val_end: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">初始策略（逗號分隔）</label>
              <input
                type="text"
                value={formData.strategies.join(", ")}
                onChange={(e) => handleStrategyChange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                placeholder="smc_v2"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">時間框架</label>
                <select
                  value={formData.timeframe}
                  onChange={(e) => setFormData({ ...formData, timeframe: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  <option>1d</option>
                  <option>4h</option>
                  <option>1h</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">最大迭代次數</label>
                <input
                  type="number"
                  value={formData.max_iterations}
                  onChange={(e) => setFormData({ ...formData, max_iterations: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  min="1"
                  max="20"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">收斂閾值（勝率變動）</label>
              <input
                type="number"
                value={formData.convergence_threshold}
                onChange={(e) => setFormData({ ...formData, convergence_threshold: parseFloat(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                min="0"
                max="1"
                step="0.01"
              />
            </div>

            {error && <div className="p-3 bg-red-100 text-red-700 rounded-lg text-sm">{error}</div>}

            <button
              type="submit"
              disabled={running}
              className={`w-full py-2 rounded-lg font-medium text-white transition-colors ${
                running
                  ? "bg-gray-400 cursor-not-allowed"
                  : "bg-blue-600 hover:bg-blue-700"
              }`}
            >
              {running ? "執行中..." : "啟動 Pipeline"}
            </button>
          </form>
        </div>

        {/* 進度顯示 */}
        <div>
          {/* 狀態卡片 */}
          {status && (
            <div className="bg-white p-6 rounded-lg shadow mb-6">
              <h2 className="text-xl font-bold mb-4">狀態</h2>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600">狀態</span>
                  <span className={`font-semibold ${status.running ? "text-blue-600" : "text-green-600"}`}>
                    {status.running ? "執行中" : status.status}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">當前迭代</span>
                  <span className="font-semibold">{status.current_iteration}</span>
                </div>
                {status.win_rate_history.length > 0 && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">最新勝率</span>
                    <span className="font-semibold">{(status.win_rate_history[status.win_rate_history.length - 1] * 100).toFixed(2)}%</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 驗證報告 */}
          {report && (
            <div className="bg-white p-6 rounded-lg shadow">
              <h2 className="text-xl font-bold mb-4">驗證報告</h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">股票</span>
                  <span>{report.symbols?.join(", ") || "-"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">總交易數</span>
                  <span className="font-semibold">{report.total_trades}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">勝利</span>
                  <span className="font-semibold text-green-600">{report.total_wins}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">失敗</span>
                  <span className="font-semibold text-red-600">{report.total_losses}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">勝率</span>
                  <span className="font-semibold text-blue-600">{(report.avg_win_rate * 100).toFixed(2)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">平均回報</span>
                  <span className="font-semibold">{(report.avg_return * 100).toFixed(2)}%</span>
                </div>
              </div>
            </div>
          )}

          {/* SSE 進度日誌 */}
          {events.length > 0 && (
            <div className="bg-white p-6 rounded-lg shadow mt-6 max-h-96 overflow-y-auto">
              <h2 className="text-xl font-bold mb-4">進度日誌</h2>
              <div className="space-y-2 text-sm font-mono">
                {events.map((event, i) => (
                  <div key={i} className={`p-2 rounded ${
                    event.type === "error" ? "bg-red-50 text-red-700" :
                    event.type === "complete" ? "bg-green-50 text-green-700" :
                    "bg-gray-50 text-gray-700"
                  }`}>
                    {event.message}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 連接狀態 */}
          <div className="mt-4 text-xs text-gray-500">
            SSE 連接: <span className={isConnected ? "text-green-600" : "text-red-600"}>
              {isConnected ? "✓ 已連接" : "✗ 未連接"}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
