"use client"
import { useEffect, useRef } from "react"
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  CandlestickSeries,
  HistogramSeries,
  type Time,
} from "lightweight-charts"
import type { PriceBar, SmcData } from "@/lib/api"

interface Props {
  bars: PriceBar[]
  smc: SmcData | null
  height?: number | "100%"
}

const COLORS = {
  bullOB: "rgba(34,197,94,0.18)",
  bearOB: "rgba(239,68,68,0.18)",
  bullFVG: "rgba(99,102,241,0.15)",
  bearFVG: "rgba(249,115,22,0.15)",
  poc: "#f59e0b",
  vaHigh: "rgba(99,102,241,0.5)",
  vaLow: "rgba(99,102,241,0.5)",
  swingHigh: "#ef4444",
  swingLow: "#22c55e",
}

export function StockChart({ bars, smc, height = 520 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef     = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!containerRef.current || bars.length === 0) return

    const el = containerRef.current
    const computedHeight = height === "100%" ? el.clientHeight : height

    const chart = createChart(el, {
      width: el.clientWidth,
      height: computedHeight,
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
        timeVisible: true,
      },
      crosshair: {
        vertLine: { color: "#94a3b8", width: 1, style: 3 },
        horzLine: { color: "#94a3b8", width: 1, style: 3 },
      },
    })

    chartRef.current = chart

    // Candles
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#16a34a",
      borderDownColor: "#dc2626",
      wickUpColor: "#16a34a",
      wickDownColor: "#dc2626",
    })

    const candleData: CandlestickData<Time>[] = bars.map(b => ({
      time: b.date as Time,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }))
    candleSeries.setData(candleData)

    // Volume
    const volSeries = chart.addSeries(HistogramSeries, {
      color: "#94a3b8",
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    })
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } })
    volSeries.setData(bars.map(b => ({
      time: b.date as Time,
      value: b.volume,
      color: b.close >= b.open ? "rgba(34,197,94,0.4)" : "rgba(239,68,68,0.4)",
    })))

    // SMC overlay
    if (smc) {
      // Order Blocks
      smc.order_blocks?.forEach(ob => {
        if (ob.mitigated) return
        candleSeries.createPriceLine({
          price: ob.top,
          color: ob.type === "bullish" ? COLORS.bullOB.replace("0.18", "0.8") : COLORS.bearOB.replace("0.18", "0.8"),
          lineWidth: 1,
          lineStyle: 2,
          title: `${ob.type === "bullish" ? "🟢" : "🔴"} OB`,
        })
        candleSeries.createPriceLine({
          price: ob.bottom,
          color: ob.type === "bullish" ? COLORS.bullOB.replace("0.18", "0.5") : COLORS.bearOB.replace("0.18", "0.5"),
          lineWidth: 1,
          lineStyle: 2,
          title: "",
        })
      })

      // FVG
      smc.fvg?.filter(f => !f.filled).slice(0, 6).forEach(f => {
        candleSeries.createPriceLine({
          price: f.top,
          color: f.type === "bullish" ? "#6366f1" : "#f97316",
          lineWidth: 1,
          lineStyle: 3,
          title: `${f.type === "bullish" ? "↑" : "↓"} FVG ${f.gap_pct}%`,
        })
        candleSeries.createPriceLine({
          price: f.bottom,
          color: f.type === "bullish" ? "#6366f1" : "#f97316",
          lineWidth: 1,
          lineStyle: 3,
          title: "",
        })
      })

      // POC & Value Area
      if (smc.volume_profile) {
        const vp = smc.volume_profile
        candleSeries.createPriceLine({ price: vp.poc,     color: COLORS.poc,    lineWidth: 2, lineStyle: 0, title: "POC 成交密集" })
        candleSeries.createPriceLine({ price: vp.va_high, color: "#6366f1",     lineWidth: 1, lineStyle: 1, title: "價值區上緣" })
        candleSeries.createPriceLine({ price: vp.va_low,  color: "#6366f1",     lineWidth: 1, lineStyle: 1, title: "價值區下緣" })
      }

      // Key Levels
      smc.key_levels?.forEach(lv => {
        candleSeries.createPriceLine({
          price: lv.price,
          color: lv.type === "resistance" ? "#ef4444" : "#22c55e",
          lineWidth: 1,
          lineStyle: 4,
          title: lv.type === "resistance" ? "壓力" : "支撐",
        })
      })
    }

    chart.timeScale().fitContent()

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (!el) return
      const newHeight = height === "100%" ? el.clientHeight : height
      chart.applyOptions({ width: el.clientWidth, height: newHeight })
    })
    ro.observe(el)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [bars, smc, height])

  const style = height === "100%"
    ? { width: "100%", height: "100%" }
    : { width: "100%", height }

  return <div ref={containerRef} style={style} />
}
