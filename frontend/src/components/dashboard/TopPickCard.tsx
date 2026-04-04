import type { TopPick } from "@/lib/api"
import Link from "next/link"

const RANKS = ["🥇", "🥈", "🥉"]
const REC_COLOR: Record<string, string> = {
  "強力推薦": "text-green-600 bg-green-50 border-green-200",
  "推薦":     "text-blue-600  bg-blue-50  border-blue-200",
  "觀察":     "text-yellow-600 bg-yellow-50 border-yellow-200",
  "不推薦":   "text-slate-500  bg-slate-100  border-slate-200",
}

function ScoreBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
    </div>
  )
}

export function TopPickCard({ pick, rank }: { pick: TopPick; rank: number }) {
  const recColor = REC_COLOR[pick.recommendation] ?? REC_COLOR["不推薦"]
  const macdDir  = (pick as any).macd > (pick as any).macd_signal ? "金叉 ▲" : "死叉 ▼"

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
        <span className={`inline-block text-xs px-2 py-0.5 rounded border ${recColor} mb-4`}>
          {pick.recommendation}
        </span>

        <div className="space-y-2">
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
          <div>
            <div className="flex justify-between text-xs text-slate-500 mb-1">
              <span>情緒分</span><span className="text-slate-700">{pick.sentiment_score}</span>
            </div>
            <ScoreBar value={pick.sentiment_score} color="bg-purple-500" />
          </div>
        </div>

        <div className="flex gap-2 mt-4 flex-wrap">
          <span className={`text-xs px-2 py-1 rounded bg-slate-100 ${pick.rsi < 35 ? "text-green-600" : pick.rsi > 65 ? "text-red-500" : "text-slate-500"}`}>
            RSI {pick.rsi?.toFixed(1)}
          </span>
          <span className={`text-xs px-2 py-1 rounded bg-slate-100 ${macdDir.includes("金") ? "text-green-600" : "text-red-500"}`}>
            {macdDir}
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
