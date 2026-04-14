"use client"
import { useState } from "react"
import { api } from "@/lib/api"
import { useSSE } from "@/hooks/useSSE"

export function BatchFetchButton() {
  const { progress, isRunning: sseRunning } = useSSE()
  const [showMenu, setShowMenu] = useState(false)

  // track batch_fetch phase from SSE
  const isFetching = sseRunning || (progress?.phase === "batch_fetch")

  const trigger = async (backfill: boolean) => {
    setShowMenu(false)
    await api.batchFetch(7, backfill)
  }

  return (
    <div className="relative flex flex-col items-end gap-2">
      <div className="flex gap-1">
        <button
          onClick={() => trigger(false)}
          disabled={isFetching}
          className="px-4 py-2 rounded-l-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
        >
          {isFetching ? "爬取中..." : "更新股價"}
        </button>
        <button
          onClick={() => setShowMenu(!showMenu)}
          disabled={isFetching}
          className="px-2 py-2 rounded-r-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm transition-colors border-l border-emerald-500"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
            <path d="M6 8L2 4h8L6 8z" />
          </svg>
        </button>
      </div>

      {/* Dropdown menu */}
      {showMenu && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
          <div className="absolute right-0 top-full mt-1 z-50 rounded-lg bg-white border border-slate-200 shadow-lg py-1 min-w-[180px]">
            <button
              onClick={() => trigger(false)}
              className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              更新最新股價
              <span className="block text-xs text-slate-400">補最近 7 天</span>
            </button>
            <button
              onClick={() => trigger(true)}
              className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              完整回補至 2020
              <span className="block text-xs text-slate-400">回測需要，約 10-15 分鐘</span>
            </button>
          </div>
        </>
      )}

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
