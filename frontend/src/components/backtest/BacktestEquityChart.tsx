"use client"
import { useEffect, useRef } from "react"
import {
  createChart,
  type IChartApi,
  type LineData,
  LineSeries,
  type Time,
} from "lightweight-charts"
import type { BacktestV3EquityPoint } from "@/lib/api"

interface BacktestEquityChartProps {
  data: BacktestV3EquityPoint[]
  height?: number
}

export function BacktestEquityChart({ data, height = 400 }: BacktestEquityChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return

    const el = containerRef.current
    const chart = createChart(el, {
      width: el.clientWidth,
      height,
      layout: {
        background: { color: "#ffffff" },
        textColor: "#475569",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      },
      grid: {
        vertLines: { color: "#f1f5f9" },
        horzLines: { color: "#f1f5f9" },
      },
      rightPriceScale: { borderColor: "#e2e8f0" },
      timeScale: {
        borderColor: "#e2e8f0",
        timeVisible: false,
      },
      crosshair: {
        vertLine: { color: "#94a3b8", width: 1, style: 3 },
        horzLine: { color: "#94a3b8", width: 1, style: 3 },
      },
    })

    chartRef.current = chart

    // 構建圖表數據
    const chartData: LineData<Time>[] = data.map((point) => {
      // 轉換日期為時間戳
      const [year, month, day] = point.date.split("-").map(Number)
      const timestamp = Math.floor(new Date(year, month - 1, day).getTime() / 1000) as Time
      return {
        time: timestamp,
        value: parseFloat(point.equity.toString()),
      }
    })

    // 添加線圖系列
    const lineSeries = chart.addSeries(LineSeries, {
      color: "#4f46e5",
      lineWidth: 2,
      crosshairMarkerVisible: true,
    })

    lineSeries.setData(chartData)

    // 自動適應範圍
    chart.timeScale().fitContent()

    // 處理窗口大小變化
    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
        })
      }
    }

    window.addEventListener("resize", handleResize)

    return () => {
      window.removeEventListener("resize", handleResize)
      chart.remove()
    }
  }, [data, height])

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center bg-slate-50 rounded-xl border border-slate-200 text-slate-400"
        style={{ height: `${height}px` }}
      >
        無資料
      </div>
    )
  }

  return <div ref={containerRef} className="rounded-xl border border-slate-200 bg-white overflow-hidden" />
}
