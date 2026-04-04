"use client"
import { useState } from "react"
import { api } from "@/lib/api"

export function SellModal({ ticker, shares }: { ticker: string; shares: number }) {
  const [open, setOpen]     = useState(false)
  const [sellShares, setSellShares] = useState(String(shares))
  const [price, setPrice]   = useState("")
  const [note, setNote]     = useState("")
  const [loading, setLoading] = useState(false)
  const [msg, setMsg]       = useState("")

  const submit = async () => {
    if (!price) return
    setLoading(true)
    setMsg("")
    try {
      const res = await api.sell({
        ticker,
        shares: parseFloat(sellShares),
        price: parseFloat(price),
        note,
      })
      setMsg(`${res.message}　損益：${res.pnl_pct >= 0 ? "+" : ""}${res.pnl_pct.toFixed(2)}%`)
      setTimeout(() => { setOpen(false); setMsg(""); window.location.reload() }, 1500)
    } catch {
      setMsg("❌ 賣出失敗，請確認後端是否正常")
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-xs px-3 py-1.5 rounded-lg bg-red-50 text-red-600 hover:bg-red-100 font-medium transition-colors"
      >
        賣出
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-2xl shadow-xl w-96 p-6">
            <h3 className="text-lg font-bold text-slate-800 mb-1">賣出 {ticker}</h3>
            <p className="text-xs text-slate-400 mb-5">目前持股：{shares} 股</p>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-500 uppercase tracking-wide">賣出股數</label>
                  <input
                    type="number" value={sellShares} onChange={e => setSellShares(e.target.value)}
                    max={shares}
                    className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-red-200"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500 uppercase tracking-wide">賣出價格</label>
                  <input
                    type="number" step="0.01" value={price} onChange={e => setPrice(e.target.value)}
                    placeholder="150.00"
                    className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-red-200"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-500 uppercase tracking-wide">備註（選填）</label>
                <input
                  value={note} onChange={e => setNote(e.target.value)}
                  placeholder="停利出場 / 停損..."
                  className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-red-200"
                />
              </div>
            </div>

            {msg && (
              <p className={`mt-3 text-sm ${msg.includes("❌") ? "text-red-500" : "text-green-600"}`}>{msg}</p>
            )}

            <div className="flex gap-3 mt-6">
              <button onClick={() => setOpen(false)} className="flex-1 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm hover:bg-slate-50">
                取消
              </button>
              <button
                onClick={submit} disabled={loading || !price}
                className="flex-1 py-2 rounded-lg bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm font-medium"
              >
                {loading ? "處理中..." : "確認賣出"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
