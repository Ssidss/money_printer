"use client"
import { useState, useEffect } from "react"
import { api, type Stock } from "@/lib/api"

interface StockBacktestFormProps {
  onSubmit: (ticker: string, market: string, startDate: string, endDate: string) => Promise<void>
  isLoading: boolean
}

export function StockBacktestForm({ onSubmit, isLoading }: StockBacktestFormProps) {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [selectedTicker, setSelectedTicker] = useState<string>("")
  const [market, setMarket] = useState<string>("US")
  const [startDate, setStartDate] = useState<string>("")
  const [endDate, setEndDate] = useState<string>("")
  const [error, setError] = useState<string>("")
  const [stocksLoading, setStocksLoading] = useState(true)

  useEffect(() => {
    const loadStocks = async () => {
      try {
        setStocksLoading(true)
        const data = await api.stocks()
        setStocks(data)
        if (data.length > 0) {
          setSelectedTicker(data[0].ticker)
          setMarket(data[0].market || "US")
        }
      } catch (err) {
        console.error("Failed to load stocks:", err)
        setError("無法載入股票列表")
      } finally {
        setStocksLoading(false)
      }
    }
    loadStocks()
  }, [])

  // 初始化日期為最近一年
  useEffect(() => {
    const today = new Date()
    const oneYearAgo = new Date(today)
    oneYearAgo.setFullYear(today.getFullYear() - 1)

    setEndDate(today.toISOString().split("T")[0])
    setStartDate(oneYearAgo.toISOString().split("T")[0])
  }, [])

  const handleSubmit = async () => {
    setError("")
    if (!selectedTicker) {
      setError("請選擇股票")
      return
    }
    if (!startDate || !endDate) {
      setError("請選擇日期範圍")
      return
    }
    if (new Date(startDate) >= new Date(endDate)) {
      setError("開始日期必須早於結束日期")
      return
    }

    try {
      await onSubmit(selectedTicker, market, startDate, endDate)
    } catch (err) {
      setError(err instanceof Error ? err.message : "回測失敗，請稍後再試")
    }
  }

  const shortcutDateRanges: Record<string, { days: number; label: string }> = {
    "1M": { days: 30, label: "1個月" },
    "3M": { days: 90, label: "3個月" },
    "6M": { days: 180, label: "6個月" },
    "1Y": { days: 365, label: "1年" },
    "2Y": { days: 730, label: "2年" },
  }

  const applyDateShortcut = (days: number) => {
    const today = new Date()
    const start = new Date(today)
    start.setDate(today.getDate() - days)
    setStartDate(start.toISOString().split("T")[0])
    setEndDate(today.toISOString().split("T")[0])
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-base font-semibold text-slate-800 mb-5">個股策略回測</h2>

      <div className="space-y-4">
        {/* 股票選擇 */}
        <div>
          <label className="text-xs text-slate-500 uppercase tracking-wide">股票代號</label>
          <select
            value={selectedTicker}
            onChange={(e) => {
              setSelectedTicker(e.target.value)
              const stock = stocks.find(s => s.ticker === e.target.value)
              if (stock) setMarket(stock.market || "US")
            }}
            disabled={stocksLoading}
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:opacity-50"
          >
            {stocks.map((s) => (
              <option key={s.ticker} value={s.ticker}>
                {s.ticker} {s.name ? `(${s.name})` : ""}
              </option>
            ))}
          </select>
        </div>

        {/* 市場選擇 */}
        <div>
          <label className="text-xs text-slate-500 uppercase tracking-wide">市場</label>
          <div className="mt-1 flex gap-3">
            {["US", "TW"].map((m) => (
              <label key={m} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="market"
                  value={m}
                  checked={market === m}
                  onChange={(e) => setMarket(e.target.value)}
                  className="w-4 h-4 accent-indigo-600"
                />
                <span className="text-sm text-slate-700">{m === "US" ? "美股" : "台股"}</span>
              </label>
            ))}
          </div>
        </div>

        {/* 日期範圍 */}
        <div>
          <label className="text-xs text-slate-500 uppercase tracking-wide mb-2 block">回測期間</label>
          <div className="flex gap-2 mb-3 flex-wrap">
            {Object.entries(shortcutDateRanges).map(([key, { days, label }]) => (
              <button
                key={key}
                onClick={() => applyDateShortcut(days)}
                className="px-3 py-1.5 text-xs rounded-lg border border-slate-200 text-slate-600 hover:bg-indigo-50 hover:border-indigo-300 transition-colors"
              >
                {label}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-500">開始日期</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </div>
            <div>
              <label className="text-xs text-slate-500">結束日期</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </div>
          </div>
        </div>

        {/* 錯誤消息 */}
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
            {error}
          </div>
        )}

        {/* 提交按鈕 */}
        <button
          onClick={handleSubmit}
          disabled={isLoading || stocksLoading}
          className="w-full px-6 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium transition-colors"
        >
          {isLoading ? "回測執行中..." : "開始回測"}
        </button>
      </div>
    </div>
  )
}
