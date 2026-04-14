"use client"
import type { BacktestV3Report } from "@/lib/api"

interface BacktestMetricsProps {
  report: BacktestV3Report | null
}

export function BacktestMetrics({ report }: BacktestMetricsProps) {
  if (!report) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm text-center text-slate-400">
        無數據
      </div>
    )
  }

  const metrics = report.portfolio_summary

  const metricItems = [
    {
      label: "總報酬率",
      value: `${metrics.total_return_pct >= 0 ? "+" : ""}${metrics.total_return_pct.toFixed(2)}%`,
      color: metrics.total_return_pct >= 0 ? "text-green-600" : "text-red-500",
    },
    {
      label: "年化報酬 (CAGR)",
      value: `${metrics.cagr_pct >= 0 ? "+" : ""}${metrics.cagr_pct.toFixed(1)}%`,
      color: metrics.cagr_pct >= 0 ? "text-green-600" : "text-red-500",
    },
    {
      label: "Sharpe Ratio",
      value: metrics.sharpe_ratio.toFixed(3),
      color:
        metrics.sharpe_ratio > 1
          ? "text-green-600"
          : metrics.sharpe_ratio > 0
            ? "text-yellow-600"
            : "text-red-500",
    },
    {
      label: "最大回撤",
      value: `-${metrics.max_drawdown_pct.toFixed(1)}%`,
      color: "text-red-400",
    },
    {
      label: "勝率",
      value: `${metrics.win_rate_pct.toFixed(1)}%`,
      color: metrics.win_rate_pct >= 50 ? "text-green-600" : "text-orange-500",
    },
    {
      label: "交易次數",
      value: metrics.total_trades,
      color: "text-slate-700",
    },
    {
      label: "平均獲利",
      value: `+${metrics.avg_win_pct.toFixed(2)}%`,
      color: "text-green-600",
    },
    {
      label: "平均虧損",
      value: `${metrics.avg_loss_pct.toFixed(2)}%`,
      color: "text-red-400",
    },
    {
      label: "Profit Factor",
      value: metrics.profit_factor.toFixed(2),
      color: metrics.profit_factor > 1.5 ? "text-green-600" : metrics.profit_factor > 1 ? "text-yellow-600" : "text-red-500",
    },
  ]

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-800 mb-4">績效指標</h3>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {metricItems.map((item) => (
          <div key={item.label} className="flex flex-col">
            <p className="text-xs text-slate-400 uppercase tracking-wide">{item.label}</p>
            <p className={`text-sm font-semibold mt-1 ${item.color}`}>{item.value}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
