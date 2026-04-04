"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"

export function RemoveStockButton({ ticker }: { ticker: string }) {
  const [confirm, setConfirm] = useState(false)
  const [isPending, startTransition] = useTransition()
  const router = useRouter()

  async function handleRemove() {
    try {
      await api.removeStock(ticker)
      startTransition(() => router.refresh())
    } catch {
      alert(`移除 ${ticker} 失敗`)
    }
    setConfirm(false)
  }

  if (confirm) {
    return (
      <span className="inline-flex items-center gap-1">
        <button
          onClick={handleRemove}
          disabled={isPending}
          className="text-xs px-2 py-1 rounded bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 transition-colors"
        >
          確認
        </button>
        <button
          onClick={() => setConfirm(false)}
          className="text-xs px-2 py-1 rounded bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors"
        >
          取消
        </button>
      </span>
    )
  }

  return (
    <button
      onClick={() => setConfirm(true)}
      className="text-xs px-2 py-1 rounded text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
      title={`停止追蹤 ${ticker}`}
    >
      移除
    </button>
  )
}
