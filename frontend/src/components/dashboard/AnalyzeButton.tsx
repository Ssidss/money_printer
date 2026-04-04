"use client"
import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import { useSSE } from "@/hooks/useSSE"

export function AnalyzeButton({ initialRunning }: { initialRunning: boolean }) {
  const { progress, isRunning: sseRunning } = useSSE()
  const [running, setRunning] = useState(initialRunning)

  useEffect(() => { setRunning(sseRunning) }, [sseRunning])

  const trigger = async () => {
    setRunning(true)
    await api.triggerAnalysis()
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <button
        onClick={trigger}
        disabled={running}
        className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
      >
        {running ? "分析中..." : "立即分析"}
      </button>
      {running && progress && (
        <div className="w-72">
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span className="truncate">{progress.message}</span>
            <span>{progress.pct}%</span>
          </div>
          <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full transition-all duration-300"
              style={{ width: `${progress.pct}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
