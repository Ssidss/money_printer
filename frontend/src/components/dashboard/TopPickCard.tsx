import type { TopPick } from "@/lib/api"
import Link from "next/link"

const RANKS = ["🥇", "🥈", "🥉"]
const REC_COLOR: Record<string, string> = {
  "強力推薦": "text-green-600 bg-green-50 border-green-200",
  "推薦":     "text-blue-600  bg-blue-50  border-blue-200",
  "觀察":     "text-yellow-600 bg-yellow-50 border-yellow-200",
  "不推薦":   "text-slate-500  bg-slate-100  border-slate-200",
}

const ACTION_BADGE: Record<string, string> = {
  "買入": "text-green-700 bg-green-100",
  "加碼": "text-green-600 bg-green-50",
  "等回調": "text-amber-600 bg-amber-50",
  "觀望": "text-slate-500 bg-slate-100",
  "不操作": "text-slate-400 bg-slate-50",
}

const TREND_LABEL: Record<string, string> = {
  uptrend: "上升", weak_uptrend: "弱上升", downtrend: "下降",
  weak_downtrend: "弱下降", ranging: "盤整",
  "上升趨勢": "上升", "下降趨勢": "下降", "盤整": "盤整",
}

function ScoreBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
    </div>
  )
}

export function TopPickCard({ pick, rank }: { pick: TopPick; rank: number }) {
  const v2 = pick.smc_v2
  const displayRec = v2?.recommendation ?? pick.recommendation
  const recColor = REC_COLOR[displayRec] ?? REC_COLOR["不推薦"]

  return (
    <Link href={`/stocks/${pick.ticker}`}>
      <div className="rounded-xl border border-slate-200 bg-white p-5 hover:border-indigo-300 hover:shadow-md transition-all cursor-pointer h-full shadow-sm">
        <div className="flex justify-between items-start mb-3">
          <div>
            <span className="text-xl font-bold text-slate-800">{pick.ticker}</span>
            <span className="ml-2 text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded">{pick.market}</span>
          </div>
          <span className="text-2xl">{RANKS[rank - 1] ?? `#${rank}`}</span>
        </div>

        <p className="text-3xl font-bold text-slate-800 mb-1">{pick.close_price}</p>
        <div className="flex items-center gap-2 mb-4">
          <span className={`inline-block text-xs px-2 py-0.5 rounded border ${recColor}`}>
            {displayRec}
          </span>
          {v2?.action && (
            <span className={`text-xs px-2 py-0.5 rounded font-medium ${ACTION_BADGE[v2.action] ?? "text-slate-500 bg-slate-100"}`}>
              {v2.action}
            </span>
          )}
          {v2?.trend && (
            <span className="text-xs text-slate-400">
              {TREND_LABEL[v2.trend] ?? v2.trend}
            </span>
          )}
        </div>

        {/* v2 Entry Plan */}
        {v2?.entry_price && v2?.stop_price && v2?.target_price ? (
          <div className="bg-slate-50 rounded-lg p-3 mb-3 space-y-1 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400">買入</span>
              <span className="font-semibold text-indigo-600">{v2.entry_price.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">停損</span>
              <span className="font-medium text-red-500">{v2.stop_price.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">目標</span>
              <span className="font-medium text-green-600">{v2.target_price.toFixed(2)}</span>
            </div>
            {v2.rr_ratio && (
              <div className="flex justify-between">
                <span className="text-slate-400">R:R</span>
                <span className={`font-bold ${v2.rr_ratio >= 2 ? "text-green-600" : "text-yellow-600"}`}>
                  {v2.rr_ratio.toFixed(2)}x
                </span>
              </div>
            )}
            {v2.position_tier && (
              <div className="text-center pt-1 border-t border-slate-200 mt-1">
                <span className={`font-bold ${
                  v2.position_tier === "核心持倉" ? "text-green-600" :
                  v2.position_tier === "標準倉位" ? "text-blue-600" :
                  "text-yellow-600"
                }`}>
                  {v2.position_tier === "核心持倉" ? "🟢 核心" : v2.position_tier === "標準倉位" ? "🔵 標準" : "🟡 探索"}
                </span>
              </div>
            )}
          </div>
        ) : (
          /* Fallback: v1 scores */
          <div className="space-y-2 mb-3">
            <div>
              <div className="flex justify-between text-xs text-slate-500 mb-1">
                <span>綜合分</span><span className="text-slate-700 font-medium">{pick.composite_score}</span>
              </div>
              <ScoreBar value={pick.composite_score} color={pick.composite_score >= 65 ? "bg-green-500" : pick.composite_score >= 50 ? "bg-yellow-500" : "bg-red-500"} />
            </div>
            <div>
              <div className="flex justify-between text-xs text-slate-500 mb-1">
                <span>技術分</span><span className="text-slate-700">{pick.technical_score}</span>
              </div>
              <ScoreBar value={pick.technical_score} color="bg-blue-500" />
            </div>
          </div>
        )}

        <div className="flex gap-2 flex-wrap">
          <span className={`text-xs px-2 py-1 rounded bg-slate-100 ${pick.rsi < 35 ? "text-green-600" : pick.rsi > 65 ? "text-red-500" : "text-slate-500"}`}>
            RSI {pick.rsi?.toFixed(1)}
          </span>
          <span className="text-xs px-2 py-1 rounded bg-slate-100 text-slate-500">
            {pick.news_summary?.label}
          </span>
        </div>

        {pick.signals?.slice(0, 2).map((s, i) => (
          <p key={i} className="text-xs text-slate-400 mt-2">• {s}</p>
        ))}
      </div>
    </Link>
  )
}
