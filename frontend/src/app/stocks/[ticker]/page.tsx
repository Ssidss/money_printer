import { api } from "@/lib/api"
import { StockChart } from "@/components/stock/StockChart"
import { VolumeProfile } from "@/components/stock/VolumeProfile"
import { BackButton } from "@/components/stock/BackButton"
import { AiNotes } from "@/components/stock/AiNotes"
import type { SmcData } from "@/lib/api"

export const revalidate = 0

const TREND_COLOR: Record<string, string> = {
  "上升趨勢": "text-green-600 bg-green-50 border-green-200",
  "下降趨勢": "text-red-500 bg-red-50 border-red-200",
  "盤整":     "text-yellow-600 bg-yellow-50 border-yellow-200",
  "未知":     "text-slate-500 bg-slate-100 border-slate-200",
}

const REC_BADGE: Record<string, string> = {
  "強力推薦": "bg-green-100 text-green-700 border-green-200",
  "推薦":     "bg-blue-100 text-blue-700 border-blue-200",
  "觀察":     "bg-yellow-100 text-yellow-700 border-yellow-200",
  "不推薦":   "bg-slate-100 text-slate-500 border-slate-200",
}

export default async function StockDetailPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params
  const T = ticker.toUpperCase()

  const [barsRes, smcRes, analysisRes, newsRes] = await Promise.allSettled([
    api.stockPrices(T, 120),
    api.stockSmc(T, 120),
    api.stockAnalysis(T),
    api.stockNews(T),
  ])

  const bars     = barsRes.status === "fulfilled" ? barsRes.value : []
  const smc: SmcData | null = smcRes.status === "fulfilled" ? smcRes.value : null
  const analysis = analysisRes.status === "fulfilled" ? analysisRes.value : []
  const news     = newsRes.status === "fulfilled" ? newsRes.value : []
  const latest   = analysis[analysis.length - 1] ?? null
  const prob     = smc?.probability
  const vp       = smc?.volume_profile
  const entry    = latest?.entry_suggestion

  return (
    <div className="max-w-7xl mx-auto space-y-6">

      {/* Back Button + Header */}
      <div className="flex items-start justify-between">
        <div>
          <BackButton />
          <div className="flex items-center gap-3 mt-1">
            <h1 className="text-3xl font-bold text-slate-800">{T}</h1>
            {smc?.structure?.trend && (
              <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${TREND_COLOR[smc.structure.trend] ?? TREND_COLOR["未知"]}`}>
                {smc.structure.trend}
              </span>
            )}
            {latest?.recommendation && (
              <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${REC_BADGE[latest.recommendation] ?? REC_BADGE["不推薦"]}`}>
                {latest.recommendation}
              </span>
            )}
          </div>
          {latest && (
            <p className="text-slate-500 text-sm mt-1">
              最新收盤 <span className="font-semibold text-slate-700">{latest.close_price}</span>
              　RSI <span className={`font-medium ${latest.rsi < 35 ? "text-green-600" : latest.rsi > 65 ? "text-red-500" : "text-slate-600"}`}>{latest.rsi?.toFixed(1)}</span>
              　<span className="text-slate-400">{latest.date}</span>
            </p>
          )}
        </div>

        {/* 走勢機率 */}
        {prob && (
          <div className="text-right">
            <p className="text-xs text-slate-400 mb-1">走勢機率</p>
            <div className="flex items-center gap-2">
              <span className="text-green-600 font-bold text-lg">↑{prob.bullish_pct}%</span>
              <div className="w-32 h-2.5 bg-red-200 rounded-full overflow-hidden">
                <div className="h-full bg-green-500 rounded-full" style={{ width: `${prob.bullish_pct}%` }} />
              </div>
              <span className="text-red-500 font-bold text-lg">↓{prob.bearish_pct}%</span>
            </div>
            <p className={`text-xs mt-1 font-medium ${prob.outlook === "偏多" ? "text-green-600" : prob.outlook === "偏空" ? "text-red-500" : "text-yellow-600"}`}>
              {prob.outlook}
            </p>
          </div>
        )}
      </div>

      {/* SMC 驅動進出場建議 */}
      {entry && latest?.recommendation !== "不推薦" && (
        <div className="rounded-xl border-2 border-indigo-200 bg-gradient-to-r from-indigo-50 to-white p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-lg">🎯</span>
            <h3 className="font-semibold text-slate-800">SMC 進出場建議</h3>
            {entry.position_tier && (
              <span className={`text-xs px-2.5 py-1 rounded-full font-bold ${
                entry.position_tier === "核心持倉" ? "bg-green-100 text-green-700 border border-green-200" :
                entry.position_tier === "標準倉位" ? "bg-blue-100 text-blue-700 border border-blue-200" :
                "bg-yellow-100 text-yellow-700 border border-yellow-200"
              }`}>
                {entry.position_tier}
              </span>
            )}
            {entry.entry_basis && (
              <span className="text-xs bg-indigo-100 text-indigo-600 px-2 py-0.5 rounded-full font-medium">
                依據: {entry.entry_basis}
              </span>
            )}
            <span className="text-xs text-slate-400 ml-auto">基於 Order Block / FVG / 市場結構計算</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="rounded-lg bg-indigo-100/60 border border-indigo-200 p-4 text-center">
              <p className="text-xs text-indigo-500 font-medium uppercase tracking-wide mb-1">建議買入價</p>
              <p className="text-2xl font-bold text-indigo-700">{entry.entry.toFixed(2)}</p>
              {latest.close_price && (
                <p className="text-xs text-indigo-400 mt-1">
                  {entry.entry < latest.close_price
                    ? `低於現價 ${((1 - entry.entry / latest.close_price) * 100).toFixed(1)}%`
                    : "接近現價"
                  }
                </p>
              )}
            </div>
            <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-center">
              <p className="text-xs text-red-500 font-medium uppercase tracking-wide mb-1">停損價</p>
              <p className="text-2xl font-bold text-red-600">{entry.stop.toFixed(2)}</p>
              <p className="text-xs text-red-400 mt-1">
                風險 -{entry.risk_pct ?? ((1 - entry.stop / entry.entry) * 100).toFixed(1)}%
              </p>
            </div>
            <div className="rounded-lg bg-green-50 border border-green-200 p-4 text-center">
              <p className="text-xs text-green-600 font-medium uppercase tracking-wide mb-1">目標價</p>
              <p className="text-2xl font-bold text-green-600">{entry.target.toFixed(2)}</p>
              <p className="text-xs text-green-500 mt-1">
                獲利 +{entry.reward_pct ?? ((entry.target / entry.entry - 1) * 100).toFixed(1)}%
                {entry.target_basis && <span className="text-slate-400 ml-1">({entry.target_basis})</span>}
              </p>
            </div>
            <div className="rounded-lg bg-slate-50 border border-slate-200 p-4 text-center">
              <p className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1">風報比 R:R</p>
              <p className={`text-2xl font-bold ${entry.rr >= 2 ? "text-green-600" : entry.rr >= 1.5 ? "text-yellow-600" : "text-red-500"}`}>
                {entry.rr}x
              </p>
              <p className="text-xs text-slate-400 mt-1">
                {entry.rr >= 2 ? "優秀" : entry.rr >= 1.5 ? "可接受" : "偏低"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Chart */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="px-4 pt-4 pb-2 border-b border-slate-100 flex items-center gap-2">
          <span className="text-xs font-medium text-slate-500">日線圖</span>
          <span className="text-xs text-slate-300">· SMC 疊加</span>
          {smc && (
            <div className="ml-auto flex items-center gap-3 text-xs text-slate-400">
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-green-500 inline-block" /> OB多</span>
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-red-500 inline-block" /> OB空</span>
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-indigo-500 border-dashed border-t border-indigo-500 inline-block" /> FVG</span>
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-amber-400 inline-block" /> POC</span>
            </div>
          )}
        </div>
        <StockChart bars={bars} smc={smc} height={480} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* SMC 分析 */}
        <div className="lg:col-span-2 space-y-4">

          {/* 走勢機率詳情 */}
          {prob && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-semibold text-slate-800 mb-3">📊 走勢機率分析</h3>
              <div className="flex gap-4 mb-4">
                <div className="flex-1 rounded-lg bg-green-50 border border-green-100 p-3 text-center">
                  <p className="text-2xl font-bold text-green-600">{prob.bullish_pct}%</p>
                  <p className="text-xs text-green-500 mt-0.5">看漲機率</p>
                </div>
                <div className="flex-1 rounded-lg bg-red-50 border border-red-100 p-3 text-center">
                  <p className="text-2xl font-bold text-red-500">{prob.bearish_pct}%</p>
                  <p className="text-xs text-red-400 mt-0.5">看跌機率</p>
                </div>
              </div>
              <p className="text-sm text-slate-600 mb-3">{prob.detail}</p>
              <div className="space-y-1.5">
                {prob.reasons.map((r, i) => (
                  <p key={i} className="text-xs text-slate-500 flex gap-2">
                    <span className="text-indigo-400">•</span>{r}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* Order Blocks */}
          {smc?.order_blocks && smc.order_blocks.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-semibold text-slate-800 mb-3">🧱 Order Blocks</h3>
              <p className="text-xs text-slate-400 mb-3">機構買賣的原始區域，未被補回的 OB 是強力支撐/壓力</p>
              <div className="space-y-2">
                {smc.order_blocks.filter(ob => !ob.mitigated).slice(0, 6).map((ob, i) => (
                  <div key={i} className={`flex items-center gap-3 rounded-lg p-3 border ${ob.type === "bullish" ? "bg-green-50 border-green-100" : "bg-red-50 border-red-100"}`}>
                    <span className="text-lg">{ob.type === "bullish" ? "🟢" : "🔴"}</span>
                    <div className="flex-1">
                      <p className="text-xs text-slate-500">{ob.date}</p>
                      <p className="text-sm font-medium text-slate-700">
                        {ob.bottom.toFixed(2)} ~ {ob.top.toFixed(2)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-slate-400">移動強度</p>
                      <p className={`text-sm font-bold ${ob.type === "bullish" ? "text-green-600" : "text-red-500"}`}>+{ob.strength}%</p>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded ${ob.type === "bullish" ? "bg-green-100 text-green-600" : "bg-red-100 text-red-500"}`}>
                      {ob.type === "bullish" ? "支撐" : "壓力"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Fair Value Gaps */}
          {smc?.fvg && smc.fvg.filter(f => !f.filled).length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-semibold text-slate-800 mb-3">🕳 Fair Value Gaps</h3>
              <p className="text-xs text-slate-400 mb-3">價格快速移動留下的缺口，市場有高機率回補</p>
              <div className="space-y-2">
                {smc.fvg.filter(f => !f.filled).slice(0, 6).map((f, i) => (
                  <div key={i} className={`flex items-center gap-3 rounded-lg p-3 border ${f.type === "bullish" ? "bg-indigo-50 border-indigo-100" : "bg-orange-50 border-orange-100"}`}>
                    <span className="text-lg">{f.type === "bullish" ? "↑" : "↓"}</span>
                    <div className="flex-1">
                      <p className="text-xs text-slate-500">{f.date}</p>
                      <p className="text-sm font-medium text-slate-700">
                        {f.bottom.toFixed(2)} ~ {f.top.toFixed(2)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-slate-400">缺口大小</p>
                      <p className={`text-sm font-bold ${f.type === "bullish" ? "text-indigo-600" : "text-orange-600"}`}>{f.gap_pct}%</p>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded ${f.type === "bullish" ? "bg-indigo-100 text-indigo-600" : "bg-orange-100 text-orange-600"}`}>
                      {f.type === "bullish" ? "上行缺口" : "下行缺口"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 最新技術分析訊號 */}
          {latest?.signals && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-semibold text-slate-800 mb-3">📡 技術訊號</h3>
              <div className="grid grid-cols-2 gap-3 mb-4">
                {[
                  { label: "綜合分", value: latest.composite_score?.toFixed(1), color: latest.composite_score >= 65 ? "text-green-600" : latest.composite_score >= 50 ? "text-yellow-600" : "text-red-500" },
                  { label: "技術分", value: latest.technical_score?.toFixed(1), color: "text-blue-600" },
                  { label: "情緒分", value: latest.sentiment_score?.toFixed(1), color: "text-purple-600" },
                  { label: "RSI",   value: latest.rsi?.toFixed(1), color: latest.rsi < 35 ? "text-green-600" : latest.rsi > 65 ? "text-red-500" : "text-slate-700" },
                ].map(s => (
                  <div key={s.label} className="bg-slate-50 rounded-lg p-3">
                    <p className="text-xs text-slate-400">{s.label}</p>
                    <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
                  </div>
                ))}
              </div>
              <div className="space-y-1.5">
                {latest.signals.map((s: string, i: number) => (
                  <p key={i} className="text-sm text-slate-600 flex gap-2 items-start">
                    <span className="text-indigo-400 mt-0.5">•</span>{s}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 右側 Panel */}
        <div className="space-y-4">

          {/* 量能分佈 */}
          {vp && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-semibold text-slate-800 mb-1">📊 買賣壓分佈</h3>
              <p className="text-xs text-slate-400 mb-3">
                POC <span className="text-amber-600 font-medium">{vp.poc.toFixed(2)}</span>
                　VA {vp.va_low.toFixed(2)} ~ {vp.va_high.toFixed(2)}
              </p>
              <VolumeProfile vp={vp} />
            </div>
          )}

          {/* 關鍵價位 */}
          {smc?.key_levels && smc.key_levels.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-semibold text-slate-800 mb-3">🎯 關鍵支撐/壓力</h3>
              <div className="space-y-2">
                {[...smc.key_levels].sort((a, b) => b.price - a.price).map((lv, i) => (
                  <div key={i} className={`flex items-center justify-between rounded-lg px-3 py-2 ${lv.type === "resistance" ? "bg-red-50" : "bg-green-50"}`}>
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${lv.type === "resistance" ? "bg-red-400" : "bg-green-400"}`} />
                      <span className="text-xs text-slate-500">{lv.type === "resistance" ? "壓力" : "支撐"}</span>
                    </div>
                    <span className={`text-sm font-bold ${lv.type === "resistance" ? "text-red-600" : "text-green-600"}`}>
                      {lv.price.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI 分析記錄 */}
          <AiNotes ticker={T} />

          {/* 最新新聞 */}
          {news.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-semibold text-slate-800 mb-3">📰 最新新聞</h3>
              <div className="space-y-3">
                {news.slice(0, 5).map((n) => (
                  <a key={n.id} href={n.url} target="_blank" rel="noopener noreferrer"
                    className="block hover:bg-slate-50 rounded-lg p-2 -mx-2 transition-colors">
                    <p className="text-xs text-slate-700 leading-snug line-clamp-2">{n.title}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-slate-400">{n.source}</span>
                      {n.sentiment_score !== null && (
                        <span className={`text-xs font-medium ${n.sentiment_score >= 60 ? "text-green-600" : n.sentiment_score <= 40 ? "text-red-500" : "text-slate-400"}`}>
                          情緒 {n.sentiment_score}
                        </span>
                      )}
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
