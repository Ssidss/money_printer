"use client"
import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import { BacktestForm } from "@/components/backtest/BacktestForm"
import { StockBacktestClient } from "@/components/backtest/StockBacktestClient"

export default function BacktestPage() {
  const [activeTab, setActiveTab] = useState<"strategy" | "stock">("strategy")

  const tabs: Array<{ id: "strategy" | "stock"; label: string; icon: string }> = [
    { id: "strategy", label: "策略回測", icon: "📊" },
    { id: "stock", label: "個股策略回測", icon: "📈" },
  ]

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">回測</h1>
        <p className="text-slate-500 text-sm mt-1">歷史策略驗證 · 績效分析</p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 bg-slate-100 p-1 rounded-lg border border-slate-200">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 px-4 py-2.5 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-white text-slate-800 shadow-sm"
                : "text-slate-600 hover:text-slate-800"
            }`}
          >
            <span className="mr-1">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Strategy Backtest Tab */}
      {activeTab === "strategy" && (
        <StrategyBacktestContent />
      )}

      {/* Stock Backtest Tab */}
      {activeTab === "stock" && (
        <StockBacktestClient />
      )}
    </div>
  )
}

// 策略回測內容元件
function StrategyBacktestContent() {
  const [results, setResults] = useState<any[]>([])

  useEffect(() => {
    const loadResults = async () => {
      try {
        const data = await api.backtestResults()
        setResults(data)
      } catch (err) {
        console.error("Failed to load backtest results:", err)
      }
    }
    loadResults()
  }, [])

  return (
    <div className="space-y-6">
      {/* Form */}
      <BacktestForm />

      {/* Results List */}
      {results.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-slate-800 mb-4">歷史回測紀錄</h2>
          <div className="space-y-4">
            {results.map((r) => (
              <div key={r.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <p className="font-semibold text-slate-800">{r.name || `回測 #${r.id}`}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{r.start_date} → {r.end_date}</p>
                  </div>
                  <span className={`text-sm font-bold ${r.metrics.total_return_pct >= 0 ? "text-green-600" : "text-red-500"}`}>
                    {r.metrics.total_return_pct >= 0 ? "+" : ""}{r.metrics.total_return_pct.toFixed(2)}%
                  </span>
                </div>

                <div className="grid grid-cols-4 gap-4 md:grid-cols-8">
                  {[
                    { label: "年化報酬", value: `${r.metrics.annual_return_pct >= 0 ? "+" : ""}${r.metrics.annual_return_pct.toFixed(1)}%`, color: r.metrics.annual_return_pct >= 0 ? "text-green-600" : "text-red-500" },
                    { label: "最大回撤", value: `-${r.metrics.max_drawdown_pct.toFixed(1)}%`, color: "text-red-400" },
                    { label: "Sharpe", value: r.metrics.sharpe_ratio.toFixed(3), color: r.metrics.sharpe_ratio > 1 ? "text-green-600" : r.metrics.sharpe_ratio > 0 ? "text-yellow-600" : "text-red-500" },
                    { label: "勝率", value: `${r.metrics.win_rate.toFixed(1)}%`, color: r.metrics.win_rate >= 50 ? "text-green-600" : "text-orange-500" },
                    { label: "總交易", value: `${r.metrics.total_trades}`, color: "text-slate-700" },
                    { label: "獲利筆", value: `${r.metrics.profitable_trades}`, color: "text-green-600" },
                    { label: "平均獲利", value: `+${r.metrics.avg_profit_pct.toFixed(2)}%`, color: "text-green-600" },
                    { label: "平均虧損", value: `${r.metrics.avg_loss_pct.toFixed(2)}%`, color: "text-red-400" },
                  ].map((m) => (
                    <div key={m.label}>
                      <p className="text-xs text-slate-400">{m.label}</p>
                      <p className={`text-sm font-semibold mt-0.5 ${m.color}`}>{m.value}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
