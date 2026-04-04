"use client"
import { useState } from "react"
import { api } from "@/lib/api"
import { useSSE } from "@/hooks/useSSE"

export function BacktestForm() {
  const { progress, isRunning } = useSSE()

  const today = new Date().toISOString().slice(0, 10)
  const oneYearAgo = new Date(Date.now() - 365 * 24 * 3600 * 1000).toISOString().slice(0, 10)

  const [form, setForm] = useState({
    name: "",
    start_date: oneYearAgo,
    end_date: today,
    buy_threshold: 60,
    stop_loss_pct: 7,
    trailing_stop_pct: 5,
    initial_capital: 1000000,
    position_size_pct: 10,
    max_positions: 5,
    use_smc_filter: true,
    smc_exit_on_downtrend: true,
  })
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState("")

  const set = (k: string, v: string | number) => setForm(f => ({ ...f, [k]: v }))

  const submit = async () => {
    setLoading(true)
    setMsg("")
    try {
      await api.triggerBacktest({
        name: form.name || undefined,
        start_date: form.start_date,
        end_date: form.end_date,
        buy_threshold: form.buy_threshold,
        stop_loss_pct: form.stop_loss_pct / 100,
        trailing_stop_pct: form.trailing_stop_pct / 100,
        initial_capital: form.initial_capital,
        position_size_pct: form.position_size_pct / 100,
        max_positions: form.max_positions,
        use_smc_filter: form.use_smc_filter,
        smc_exit_on_downtrend: form.smc_exit_on_downtrend,
      })
      setMsg("回測已啟動，請稍候...")
      setTimeout(() => { setMsg(""); window.location.reload() }, 8000)
    } catch {
      setMsg("❌ 啟動失敗，請確認後端是否正常")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-base font-semibold text-slate-800 mb-5">執行回測</h2>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="col-span-2 md:col-span-3">
          <label className="text-xs text-slate-500 uppercase tracking-wide">回測名稱（選填）</label>
          <input
            value={form.name} onChange={e => set("name", e.target.value)}
            placeholder="e.g. 2024年度回測"
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
        </div>

        <div>
          <label className="text-xs text-slate-500 uppercase tracking-wide">開始日期</label>
          <input type="date" value={form.start_date} onChange={e => set("start_date", e.target.value)}
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 uppercase tracking-wide">結束日期</label>
          <input type="date" value={form.end_date} onChange={e => set("end_date", e.target.value)}
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 uppercase tracking-wide">買入門檻分數</label>
          <input type="number" value={form.buy_threshold} onChange={e => set("buy_threshold", parseFloat(e.target.value))}
            min={40} max={90} step={5}
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 uppercase tracking-wide">停損 (%)</label>
          <input type="number" value={form.stop_loss_pct} onChange={e => set("stop_loss_pct", parseFloat(e.target.value))}
            min={1} max={30} step={1}
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 uppercase tracking-wide">追蹤停損 (%)</label>
          <input type="number" value={form.trailing_stop_pct} onChange={e => set("trailing_stop_pct", parseFloat(e.target.value))}
            min={3} max={20} step={1}
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 uppercase tracking-wide">初始資金</label>
          <input type="number" value={form.initial_capital} onChange={e => set("initial_capital", parseFloat(e.target.value))}
            step={100000}
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 uppercase tracking-wide">單筆倉位 (%)</label>
          <input type="number" value={form.position_size_pct} onChange={e => set("position_size_pct", parseFloat(e.target.value))}
            min={5} max={50} step={5}
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 uppercase tracking-wide">最大持倉數</label>
          <input type="number" value={form.max_positions} onChange={e => set("max_positions", parseInt(e.target.value))}
            min={1} max={20}
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
        </div>
      </div>

      {/* SMC 設定 */}
      <div className="mt-4 flex flex-wrap gap-4 p-4 bg-indigo-50 rounded-xl border border-indigo-100">
        <p className="w-full text-xs font-semibold text-indigo-700 uppercase tracking-wide mb-1">SMC 過濾設定</p>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.use_smc_filter}
            onChange={e => setForm(f => ({ ...f, use_smc_filter: e.target.checked }))}
            className="w-4 h-4 accent-indigo-600"
          />
          <span className="text-sm text-slate-700">
            <span className="font-medium">過濾下降趨勢</span>
            <span className="text-slate-400 ml-1">（下降趨勢不買入，上升/盤整調整排序權重）</span>
          </span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.smc_exit_on_downtrend}
            disabled={!form.use_smc_filter}
            onChange={e => setForm(f => ({ ...f, smc_exit_on_downtrend: e.target.checked }))}
            className="w-4 h-4 accent-indigo-600 disabled:opacity-40"
          />
          <span className={`text-sm ${form.use_smc_filter ? "text-slate-700" : "text-slate-400"}`}>
            <span className="font-medium">趨勢反轉出場</span>
            <span className="text-slate-400 ml-1">（持倉中途 SMC 轉下降趨勢則提早出場）</span>
          </span>
        </label>
      </div>

      {/* Progress */}
      {(loading || isRunning) && progress && (
        <div className="mt-4">
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span>{progress.message}</span>
            <span>{progress.pct}%</span>
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-indigo-500 rounded-full transition-all duration-300" style={{ width: `${progress.pct}%` }} />
          </div>
        </div>
      )}

      {msg && <p className={`mt-3 text-sm ${msg.includes("❌") ? "text-red-500" : "text-slate-500"}`}>{msg}</p>}

      <div className="flex gap-3 mt-5">
        <button
          onClick={submit} disabled={loading || isRunning}
          className="px-6 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium transition-colors"
        >
          {loading || isRunning ? "回測執行中..." : "開始回測"}
        </button>
        <p className="text-xs text-slate-400 self-center">回測期間越長、股票越多，執行時間越久（約 30s~5min）</p>
      </div>
    </div>
  )
}
