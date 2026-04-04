import { api } from "@/lib/api"
import Link from "next/link"
import type { NextOpenBriefing, BriefingPortfolioItem, BriefingWatchItem } from "@/lib/api"

export const revalidate = 0

const TREND_STYLE: Record<string, string> = {
  "上升趨勢": "text-green-600 bg-green-50",
  "下降趨勢": "text-red-500 bg-red-50",
  "盤整":     "text-yellow-600 bg-yellow-50",
  "未知":     "text-slate-400 bg-slate-50",
}

const ALERT_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  stop_hit:   { bg: "bg-red-500",    text: "text-white",     label: "已觸停損" },
  near_stop:  { bg: "bg-orange-400", text: "text-white",     label: "接近停損" },
  trend_down: { bg: "bg-yellow-400", text: "text-yellow-900", label: "趨勢轉弱" },
}

const REC_BADGE: Record<string, string> = {
  "強力推薦": "bg-green-100 text-green-700",
  "推薦":     "bg-blue-100 text-blue-700",
  "觀察":     "bg-yellow-100 text-yellow-700",
  "不推薦":   "bg-slate-100 text-slate-500",
}

const ACTION_BADGE: Record<string, string> = {
  "買入": "bg-green-500 text-white",
  "加碼": "bg-green-100 text-green-700",
  "持有": "bg-blue-100 text-blue-700",
  "減倉": "bg-orange-100 text-orange-700",
  "出場": "bg-red-500 text-white",
  "觀望": "bg-slate-100 text-slate-600",
}

export default async function BriefingPage() {
  let data: NextOpenBriefing | null = null
  try {
    data = await api.nextOpenBriefing()
  } catch {
    // API not available
  }

  if (!data) {
    return (
      <div className="max-w-5xl mx-auto py-12 text-center text-slate-400">
        <p className="text-4xl mb-3">📡</p>
        <p>無法取得簡報資料，請確認後端是否正常</p>
      </div>
    )
  }

  const urgentActions = data.portfolio.filter(p => p.alert === "stop_hit" || p.alert === "near_stop")
  const trendWarnings = data.portfolio.filter(p => p.alert === "trend_down")
  const healthyHoldings = data.portfolio.filter(p => !p.alert)

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-800">🔔 下次開盤簡報</h1>
        <p className="text-slate-500 text-sm mt-1">
          最新分析：{data.analysis_date ?? "尚未分析"}
          {data.portfolio_alerts > 0 && (
            <span className="ml-2 text-red-500 font-medium">
              {data.portfolio_alerts} 個持倉警報
            </span>
          )}
        </p>
      </div>

      {/* 大盤指標 */}
      <div className="grid grid-cols-3 gap-3">
        {Object.entries(data.market_indices).map(([ticker, idx]) => (
          <div key={ticker} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-slate-700">{ticker}</span>
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${TREND_STYLE[idx.trend] ?? TREND_STYLE["未知"]}`}>
                {idx.trend}
              </span>
            </div>
            <div className="mt-1">
              <span className="text-xl font-bold text-slate-800">{idx.price.toFixed(2)}</span>
              <span className={`ml-2 text-sm font-medium ${idx.change_pct >= 0 ? "text-green-600" : "text-red-500"}`}>
                {idx.change_pct >= 0 ? "+" : ""}{idx.change_pct.toFixed(2)}%
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* ═══ 緊急行動 ═══ */}
      {urgentActions.length > 0 && (
        <div className="rounded-xl border-2 border-red-300 bg-red-50 p-5 shadow-sm">
          <h2 className="text-base font-bold text-red-700 mb-4 flex items-center gap-2">
            <span>🚨</span> 緊急行動 — 開盤優先處理
          </h2>
          <div className="space-y-3">
            {urgentActions.map(p => (
              <PortfolioAlertCard key={p.ticker} item={p} />
            ))}
          </div>
        </div>
      )}

      {/* ═══ 趨勢警告 ═══ */}
      {trendWarnings.length > 0 && (
        <div className="rounded-xl border-2 border-yellow-300 bg-yellow-50 p-5 shadow-sm">
          <h2 className="text-base font-bold text-yellow-700 mb-4 flex items-center gap-2">
            <span>⚠️</span> 趨勢轉弱 — 需要關注
          </h2>
          <div className="space-y-3">
            {trendWarnings.map(p => (
              <PortfolioAlertCard key={p.ticker} item={p} />
            ))}
          </div>
        </div>
      )}

      {/* ═══ 持倉健康 ═══ */}
      {healthyHoldings.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <span>✅</span> 持倉正常
          </h2>
          <div className="space-y-3">
            {healthyHoldings.map(p => (
              <PortfolioAlertCard key={p.ticker} item={p} />
            ))}
          </div>
        </div>
      )}

      {/* ═══ 觀察清單 ═══ */}
      {data.watchlist.length > 0 && (
        <div className="rounded-xl border-2 border-indigo-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-bold text-indigo-700 mb-1 flex items-center gap-2">
            <span>🎯</span> 觀察清單 — 可能的進場機會
          </h2>
          <p className="text-xs text-slate-400 mb-4">以下股票 SMC 為上升/盤整趨勢，且推薦等級 ≥ 觀察</p>
          <div className="space-y-3">
            {data.watchlist.map(w => (
              <WatchlistCard key={w.ticker} item={w} />
            ))}
          </div>
        </div>
      )}

      {/* ═══ 行動總結 ═══ */}
      <div className="rounded-xl border-2 border-slate-300 bg-gradient-to-r from-slate-50 to-white p-5 shadow-sm">
        <h2 className="text-base font-bold text-slate-800 mb-4 flex items-center gap-2">
          <span>📋</span> 綜合行動指示
        </h2>
        <div className="space-y-2">
          {urgentActions.map(p => (
            <ActionItem
              key={p.ticker}
              priority="high"
              text={`${p.ai_action === "出場" ? "🔴 出場" : "🟠 減倉"} ${p.ticker} — ${p.pnl_pct !== null ? `虧損 ${p.pnl_pct.toFixed(1)}%` : ""} ${p.alert === "stop_hit" ? "已穿停損" : "接近停損"}，${p.smc_trend}`}
            />
          ))}
          {trendWarnings.map(p => (
            <ActionItem
              key={p.ticker}
              priority="medium"
              text={`⚠️ 觀察 ${p.ticker} — ${p.pnl_pct !== null ? `${p.pnl_pct >= 0 ? "+" : ""}${p.pnl_pct.toFixed(1)}%` : ""} SMC 下降趨勢，準備出場條件`}
            />
          ))}
          {healthyHoldings.map(p => (
            <ActionItem
              key={p.ticker}
              priority="low"
              text={`✅ 持有 ${p.ticker} — ${p.pnl_pct !== null ? `${p.pnl_pct >= 0 ? "+" : ""}${p.pnl_pct.toFixed(1)}%` : ""} ${p.smc_trend}，正常持有`}
            />
          ))}
          {data.watchlist.filter(w => w.distance_pct !== null && w.distance_pct <= 3).map(w => (
            <ActionItem
              key={w.ticker}
              priority="watch"
              text={`🎯 關注 ${w.ticker} — 距離進場價 ${w.distance_pct?.toFixed(1)}%，如果開盤拉回到 $${w.entry_suggestion?.entry.toFixed(2)} 附近可進場`}
            />
          ))}
          {data.watchlist.filter(w => w.distance_pct !== null && w.distance_pct > 3).map(w => (
            <ActionItem
              key={w.ticker}
              priority="wait"
              text={`👀 等待 ${w.ticker} — 距離進場價 ${w.distance_pct?.toFixed(1)}%，等拉回再看`}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Components ──────────────────────────────────────

function PortfolioAlertCard({ item: p }: { item: BriefingPortfolioItem }) {
  const alertStyle = p.alert ? ALERT_STYLE[p.alert] : null
  return (
    <div className={`rounded-lg border p-4 ${p.alert === "stop_hit" ? "border-red-200 bg-red-50/50" : p.alert === "near_stop" ? "border-orange-200 bg-orange-50/50" : "border-slate-100 bg-white"}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Link href={`/stocks/${p.ticker}`} className="font-bold text-indigo-600 hover:text-indigo-800 hover:underline">
            {p.ticker}
          </Link>
          {p.name && <span className="text-xs text-slate-400">{p.name}</span>}
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${TREND_STYLE[p.smc_trend] ?? TREND_STYLE["未知"]}`}>
            {p.smc_trend}
          </span>
          {alertStyle && (
            <span className={`text-xs px-2 py-0.5 rounded font-bold ${alertStyle.bg} ${alertStyle.text}`}>
              {alertStyle.label}
            </span>
          )}
        </div>
        {p.ai_action && (
          <span className={`text-xs px-2.5 py-1 rounded-lg font-bold ${ACTION_BADGE[p.ai_action] ?? "bg-slate-100 text-slate-500"}`}>
            {p.ai_action}
          </span>
        )}
      </div>
      <div className="grid grid-cols-4 gap-3 text-sm">
        <div>
          <span className="text-xs text-slate-400">均價</span>
          <p className="font-medium text-slate-700">${p.avg_cost.toFixed(2)}</p>
        </div>
        <div>
          <span className="text-xs text-slate-400">現價</span>
          <p className="font-medium text-slate-700">${p.current_price?.toFixed(2) ?? "—"}</p>
        </div>
        <div>
          <span className="text-xs text-slate-400">損益</span>
          <p className={`font-bold ${(p.pnl_pct ?? 0) >= 0 ? "text-green-600" : "text-red-500"}`}>
            {p.pnl_pct !== null ? `${p.pnl_pct >= 0 ? "+" : ""}${p.pnl_pct.toFixed(1)}%` : "—"}
          </p>
        </div>
        <div>
          <span className="text-xs text-slate-400">停損</span>
          <p className="font-medium text-red-500">${p.stop_loss.toFixed(2)}</p>
        </div>
      </div>
      {p.ai_summary_preview && (
        <p className="mt-2 text-xs text-slate-500 leading-relaxed line-clamp-2">{p.ai_summary_preview}</p>
      )}
    </div>
  )
}

function WatchlistCard({ item: w }: { item: BriefingWatchItem }) {
  const entry = w.entry_suggestion
  const isNearEntry = w.distance_pct !== null && w.distance_pct <= 3
  return (
    <div className={`rounded-lg border p-4 ${isNearEntry ? "border-indigo-200 bg-indigo-50/50" : "border-slate-100 bg-white"}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Link href={`/stocks/${w.ticker}`} className="font-bold text-indigo-600 hover:text-indigo-800 hover:underline">
            {w.ticker}
          </Link>
          {w.name && <span className="text-xs text-slate-400">{w.name}</span>}
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${REC_BADGE[w.recommendation ?? ""] ?? ""}`}>
            {w.recommendation}
          </span>
          {isNearEntry && (
            <span className="text-xs px-2 py-0.5 rounded font-bold bg-indigo-500 text-white animate-pulse">
              接近進場價
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {w.ai_action && (
            <span className={`text-xs px-2.5 py-1 rounded-lg font-bold ${ACTION_BADGE[w.ai_action] ?? "bg-slate-100 text-slate-500"}`}>
              {w.ai_action}
            </span>
          )}
          <span className="text-xs text-slate-400">
            綜合 <span className="font-medium text-slate-600">{w.composite_score?.toFixed(1)}</span>
          </span>
        </div>
      </div>
      <div className="grid grid-cols-5 gap-3 text-sm">
        <div>
          <span className="text-xs text-slate-400">現價</span>
          <p className="font-medium text-slate-700">${w.current_price?.toFixed(2) ?? "—"}</p>
        </div>
        <div>
          <span className="text-xs text-slate-400">進場價</span>
          <p className="font-bold text-indigo-600">${entry?.entry.toFixed(2) ?? "—"}</p>
        </div>
        <div>
          <span className="text-xs text-slate-400">距離</span>
          <p className={`font-medium ${isNearEntry ? "text-indigo-600" : "text-slate-500"}`}>
            {w.distance_pct !== null ? `${w.distance_pct > 0 ? "+" : ""}${w.distance_pct.toFixed(1)}%` : "—"}
          </p>
        </div>
        <div>
          <span className="text-xs text-slate-400">目標</span>
          <p className="font-medium text-green-600">${entry?.target.toFixed(2) ?? "—"}</p>
        </div>
        <div>
          <span className="text-xs text-slate-400">R:R</span>
          <p className={`font-bold ${(entry?.rr ?? 0) >= 2 ? "text-green-600" : "text-yellow-600"}`}>
            {entry?.rr ?? "—"}x
          </p>
        </div>
      </div>
      {w.signals.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {w.signals.slice(0, 4).map((s, i) => (
            <span key={i} className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded">{s}</span>
          ))}
        </div>
      )}
      {w.ai_summary_preview && (
        <p className="mt-2 text-xs text-slate-500 leading-relaxed line-clamp-2">{w.ai_summary_preview}</p>
      )}
    </div>
  )
}

function ActionItem({ priority, text }: { priority: "high" | "medium" | "low" | "watch" | "wait"; text: string }) {
  const styles = {
    high:   "bg-red-50 border-red-200 text-red-700",
    medium: "bg-yellow-50 border-yellow-200 text-yellow-700",
    low:    "bg-green-50 border-green-200 text-green-700",
    watch:  "bg-indigo-50 border-indigo-200 text-indigo-700",
    wait:   "bg-slate-50 border-slate-200 text-slate-600",
  }
  return (
    <div className={`rounded-lg border px-4 py-2.5 text-sm font-medium ${styles[priority]}`}>
      {text}
    </div>
  )
}
