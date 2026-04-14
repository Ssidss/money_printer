"use client"
import { useState } from "react"
import type { BacktestV3Report, BacktestV3EquityPoint, BacktestV3Trade } from "@/lib/api"
import { StockBacktestForm } from "./StockBacktestForm"
import { BacktestEquityChart } from "./BacktestEquityChart"
import { BacktestMetrics } from "./BacktestMetrics"
import { BacktestTradeList } from "./BacktestTradeList"

// Mock data generator 用於開發階段
function generateMockBacktestData(ticker: string, startDate: string, endDate: string) {
  const start = new Date(startDate)
  const end = new Date(endDate)
  const tradingDays = Math.floor((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))

  // Generate equity curve
  const equityData: BacktestV3EquityPoint[] = []
  let currentEquity = 100000
  for (let i = 0; i < tradingDays; i++) {
    const date = new Date(start.getTime() + i * 24 * 60 * 60 * 1000)
    const dailyReturn = (Math.random() - 0.48) * 0.02 // slight positive bias
    currentEquity *= 1 + dailyReturn
    equityData.push({
      date: date.toISOString().split("T")[0],
      equity: Math.round(currentEquity * 100) / 100,
      drawdown_pct: (Math.random() - 1) * 15,
      cash: currentEquity * 0.2,
      positions_value: currentEquity * 0.8,
      open_positions: Math.floor(Math.random() * 5),
    })
  }

  // Generate trades
  const trades: BacktestV3Trade[] = []
  const numTrades = Math.floor(tradingDays / 20)
  for (let i = 0; i < numTrades; i++) {
    const entryIdx = Math.floor(Math.random() * (tradingDays - 10))
    const exitIdx = entryIdx + Math.floor(Math.random() * 10) + 5
    const entryPrice = 100 + Math.random() * 50
    const exitPrice = entryPrice * (0.98 + Math.random() * 0.06)
    const pnlPct = ((exitPrice - entryPrice) / entryPrice) * 100

    const entryDate = new Date(start.getTime() + entryIdx * 24 * 60 * 60 * 1000)
    const exitDate = new Date(start.getTime() + exitIdx * 24 * 60 * 60 * 1000)

    trades.push({
      position_id: `MOCK-${i}`,
      ticker,
      side: "long",
      strategy_name: "SMC Strategy",
      capital_pool: "main",
      entry_date: entryDate.toISOString().split("T")[0],
      entry_price: entryPrice,
      exit_date: exitDate.toISOString().split("T")[0],
      exit_price: exitPrice,
      exit_reason: "profit_target",
      size: 100,
      gross_pnl: (exitPrice - entryPrice) * 100,
      commission: 10,
      slippage_cost: 5,
      net_pnl: (exitPrice - entryPrice) * 100 - 15,
      pnl_pct: pnlPct,
      mae: -5,
      mfe: 10,
      holding_days: Math.floor((exitDate.getTime() - entryDate.getTime()) / (1000 * 60 * 60 * 24)),
      position_tier: "standard",
      confidence: 0.75,
    })
  }

  // Calculate metrics
  const totalReturn = ((currentEquity - 100000) / 100000) * 100
  const winningTrades = trades.filter(t => (t.pnl_pct || 0) > 0)
  const losingTrades = trades.filter(t => (t.pnl_pct || 0) <= 0)

  const report: BacktestV3Report = {
    portfolio_summary: {
      total_return_pct: totalReturn,
      cagr_pct: (Math.pow(currentEquity / 100000, 1) - 1) * 100,
      max_drawdown_pct: -15.5,
      sharpe_ratio: 1.2,
      sortino_ratio: 1.8,
      calmar_ratio: 1.5,
      profit_factor: winningTrades.reduce((sum, t) => sum + (t.pnl_pct || 0), 0) / Math.abs(losingTrades.reduce((sum, t) => sum + (t.pnl_pct || 0), 0) || 1),
      win_rate_pct: (winningTrades.length / trades.length) * 100,
      total_trades: trades.length,
      avg_holding_days: Math.round(trades.reduce((sum, t) => sum + t.holding_days, 0) / trades.length),
      expectancy: trades.reduce((sum, t) => sum + (t.pnl_pct || 0), 0) / trades.length,
      avg_exposure_pct: 80,
      max_consecutive_losses: 3,
      tail_risk_cvar_5pct: -20,
      avg_win_pct: winningTrades.reduce((sum, t) => sum + (t.pnl_pct || 0), 0) / Math.max(winningTrades.length, 1),
      avg_loss_pct: losingTrades.reduce((sum, t) => sum + (t.pnl_pct || 0), 0) / Math.max(losingTrades.length, 1),
      trading_days: tradingDays,
      final_equity: currentEquity,
      initial_capital: 100000,
    },
    strategy_breakdown: {
      by_strategy: {},
      by_exit_reason: {},
      by_tier: {},
    },
    trade_log: trades,
    equity_curve: equityData,
    order_stats: { total: trades.length * 2, filled: trades.length * 2, cancelled: 0, cancel_reasons: {} },
    kill_switch: { triggered: false, reason: null, date: null },
    open_positions: [],
    metadata: {
      split: "mock",
      start_date: startDate,
      end_date: endDate,
      initial_capital: 100000,
      min_conditions: 2,
      min_rr: 1.8,
      max_positions: 5,
      risk_per_trade_pct: 2,
      max_daily_loss_pct: 5,
      strategies: ["SMC Strategy"],
      duration_seconds: 2,
      stock_count: 1,
      trading_days: tradingDays,
    },
  }

  return { report, equityData, trades }
}

export function StockBacktestClient() {
  const [isLoading, setIsLoading] = useState(false)
  const [report, setReport] = useState<BacktestV3Report | null>(null)
  const [equityData, setEquityData] = useState<BacktestV3EquityPoint[]>([])
  const [trades, setTrades] = useState<BacktestV3Trade[]>([])
  const [selectedTicker, setSelectedTicker] = useState<string>("")
  const [selectedDateRange, setSelectedDateRange] = useState<{ start: string; end: string } | null>(null)

  const handleSubmit = async (ticker: string, market: string, startDate: string, endDate: string) => {
    setIsLoading(true)
    setSelectedTicker(ticker)
    setSelectedDateRange({ start: startDate, end: endDate })

    // Simulate API call delay
    await new Promise((resolve) => setTimeout(resolve, 2000))

    const { report: mockReport, equityData: mockEquity, trades: mockTrades } = generateMockBacktestData(
      ticker,
      startDate,
      endDate,
    )

    setReport(mockReport)
    setEquityData(mockEquity)
    setTrades(mockTrades)
    setIsLoading(false)
  }

  return (
    <div className="space-y-6">
      <StockBacktestForm onSubmit={handleSubmit} isLoading={isLoading} />

      {/* Loading State */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center p-12 bg-slate-50 rounded-xl border border-slate-200">
          <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-3" />
          <p className="text-slate-600 font-medium">回測執行中...</p>
          <p className="text-sm text-slate-400 mt-1">生成模擬數據...</p>
        </div>
      )}

      {/* Results */}
      {!isLoading && selectedTicker && report && selectedDateRange && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-800">{selectedTicker} 策略回測結果</h2>
            <span className="text-sm text-slate-400">
              {selectedDateRange.start} ~ {selectedDateRange.end}
            </span>
          </div>

          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
            <strong>✨ 當前模式：模擬數據</strong> — 此結果使用隨機生成的模擬數據。實際回測結果將在 API 整合後更新。
          </div>

          <BacktestMetrics report={report} />

          {equityData.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-800 mb-3">淨值曲線</h3>
              <BacktestEquityChart data={equityData} height={350} />
            </div>
          )}

          {trades.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-800 mb-3">交易明細</h3>
              <BacktestTradeList trades={trades} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
