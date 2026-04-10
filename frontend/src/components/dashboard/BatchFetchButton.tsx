"use client"
import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import { useSSE } from "@/hooks/useSSE"

export function BatchFetchButton() {
  const { progress, isRunning: sseRunning } = useSSE()
  const [running, setRunning] = useState(false)

  // track batch_fetch phase from SSE
  const isFetching = running || (progress?.phase === "batch_fetch")
  const isDone = progress?.phase === "done" && running

  useEffect(() => {
    if (isDone) setRunning(false)
  }, [isDone])

  const trigger = async () => {
    setRunning(true)
    try {
      await api.batchFetch(7)
    } catch {
      setRunning(false)
    }
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <button
        onClick={trigger}
        disabled={isFetching}
        className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
      >
        {isFetching ? "爬取中..." : "全部爬取股價"}
      </button>
      {isFetching && progress && progress.phase === "batch_fetch" && (
        <div className="w-72">
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span className="truncate">{progress.message}</span>
            <span>{progress.pct}%</span>
          </div>
          <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full transition-all duration-300"
              style={{ width: `${progress.pct}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
