"use client"
import { useState } from "react"
import { api } from "@/lib/api"

export function BuyModal() {
  const [open, setOpen] = useState(false)
  const [ticker, setTicker]   = useState("")
  const [shares, setShares]   = useState("")
  const [price, setPrice]     = useState("")
  const [note, setNote]       = useState("")
  const [loading, setLoading] = useState(false)
  const [msg, setMsg]         = useState("")

  const submit = async () => {
    if (!ticker || !shares || !price) return
    setLoading(true)
    setMsg("")
    try {
      const res = await api.buy({
        ticker: ticker.toUpperCase(),
        shares: parseFloat(shares),
        price: parseFloat(price),
        note,
      })
      setMsg(res.message)
      setTimeout(() => { setOpen(false); setMsg(""); window.location.reload() }, 1200)
    } catch {
      setMsg("❌ 買入失敗，請確認後端是否正常")
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-medium transition-colors"
      >
        + 買入
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-2xl shadow-xl w-96 p-6">
            <h3 className="text-lg font-bold text-slate-800 mb-5">買入股票</h3>

            <div className="space-y-4">
              <div>
                <label className="text-xs text-slate-500 uppercase tracking-wide">股票代號</label>
                <input
                  value={ticker} onChange={e => setTicker(e.target.value)}
                  placeholder="e.g. AAPL / 2330"
                  className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-500 uppercase tracking-wide">股數</label>
                  <input
                    type="number" value={shares} onChange={e => setShares(e.target.value)}
                    placeholder="100"
                    className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500 uppercase tracking-wide">買入價格</label>
                  <input
                    type="number" step="0.01" value={price} onChange={e => setPrice(e.target.value)}
                    placeholder="150.00"
                    className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-500 uppercase tracking-wide">備註（選填）</label>
                <input
                  value={note} onChange={e => setNote(e.target.value)}
                  placeholder="系統推薦 / 自行判斷..."
                  className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
              </div>
            </div>

            {price && shares && (
              <p className="mt-3 text-xs text-slate-400">
                總金額：<span className="text-slate-700 font-medium">${(parseFloat(price || "0") * parseFloat(shares || "0")).toLocaleString()}</span>
              </p>
            )}

            {msg && <p className="mt-3 text-sm text-green-600">{msg}</p>}

            <div className="flex gap-3 mt-6">
              <button onClick={() => setOpen(false)} className="flex-1 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm hover:bg-slate-50">
                取消
              </button>
              <button
                onClick={submit} disabled={loading || !ticker || !shares || !price}
                className="flex-1 py-2 rounded-lg bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-medium"
              >
                {loading ? "處理中..." : "確認買入"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
