"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"

export function AddStockModal() {
  const [open, setOpen] = useState(false)
  const [ticker, setTicker] = useState("")
  const [market, setMarket] = useState<"US" | "TW">("US")
  const [name, setName] = useState("")
  const [error, setError] = useState("")
  const [isPending, startTransition] = useTransition()
  const router = useRouter()

  function reset() {
    setTicker("")
    setMarket("US")
    setName("")
    setError("")
  }

  function handleClose() {
    setOpen(false)
    reset()
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const t = ticker.trim().toUpperCase()
    if (!t) { setError("請輸入股票代號"); return }
    setError("")

    try {
      await api.addStock(t, market, name.trim() || undefined)
      setOpen(false)
      reset()
      startTransition(() => router.refresh())
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "新增失敗，請確認代號是否正確")
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 transition-colors"
      >
        <span className="text-base leading-none">+</span> 新增追蹤
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl bg-white shadow-xl p-6 mx-4">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold text-slate-800">新增追蹤股票</h2>
              <button
                onClick={handleClose}
                className="text-slate-400 hover:text-slate-600 text-xl leading-none"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Ticker */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  股票代號 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={ticker}
                  onChange={e => setTicker(e.target.value.toUpperCase())}
                  placeholder="例：NVDA、2330"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                  autoFocus
                />
              </div>

              {/* Market */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">市場</label>
                <div className="flex gap-2">
                  {(["US", "TW"] as const).map(m => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setMarket(m)}
                      className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${
                        market === m
                          ? "bg-indigo-600 text-white border-indigo-600"
                          : "border-slate-200 text-slate-600 hover:border-indigo-300 hover:text-indigo-600"
                      }`}
                    >
                      {m === "US" ? "🇺🇸 美股" : "🇹🇼 台股"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Name (optional) */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  公司名稱 <span className="text-slate-400 text-xs font-normal">（選填）</span>
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="例：NVIDIA、台積電"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                />
              </div>

              {error && (
                <p className="text-sm text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</p>
              )}

              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={handleClose}
                  className="flex-1 rounded-lg border border-slate-200 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60 transition-colors"
                >
                  {isPending ? "新增中…" : "確認新增"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
