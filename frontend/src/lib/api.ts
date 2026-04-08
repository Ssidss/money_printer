const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  // Stocks
  stocks: () => get<Stock[]>("/api/v1/stocks"),
  addStock: (ticker: string, market: string, name?: string) =>
    post<{ message: string; id: number }>(
      `/api/v1/stocks?ticker=${encodeURIComponent(ticker)}&market=${encodeURIComponent(market)}${name ? `&name=${encodeURIComponent(name)}` : ""}`,
      {}
    ),
  removeStock: (ticker: string) =>
    del<{ message: string }>(`/api/v1/stocks/${ticker}`),
  stockPrices: (ticker: string, limit = 120, timeframe: "daily" | "weekly" | "monthly" = "daily") =>
    get<PriceBar[]>(`/api/v1/stocks/${ticker}/prices?limit=${limit}&timeframe=${timeframe}`),
  stockAnalysis: (ticker: string) =>
    get<AnalysisRow[]>(`/api/v1/stocks/${ticker}/analysis`),
  stockNews: (ticker: string) =>
    get<NewsItem[]>(`/api/v1/stocks/${ticker}/news`),
  stockFetch: (ticker: string, days = 7) =>
    post<{ message: string; rows_added: number }>(`/api/v1/stocks/${ticker}/fetch?days=${days}`, {}),
  batchFetch: (days = 7) =>
    post<{ message: string }>(`/api/v1/stocks/batch-fetch?days=${days}`, {}),
  stockAnalyze: (ticker: string) =>
    post<{ message: string }>(`/api/v1/stocks/${ticker}/analyze`, {}),
  stockAnalyzeSync: (ticker: string) =>
    post<StockAnalysisResult>(`/api/v1/stocks/${ticker}/analyze/sync`, {}),

  // Analysis
  triggerAnalysis: () => post<{ message: string }>("/api/v1/analysis/run", {}),
  analysisStatus: () => get<{ running: boolean }>("/api/v1/analysis/status"),
  topPicks: (n = 3) => get<TopPick[]>(`/api/v1/analysis/top-picks?n=${n}`),
  latestAnalysis: () => get<LatestAnalysis>("/api/v1/analysis/latest"),

  // Portfolio
  holdings: () => get<Holding[]>("/api/v1/portfolio"),
  transactions: () => get<Transaction[]>("/api/v1/portfolio/transactions"),
  buy: (body: BuyRequest) => post<{ message: string }>("/api/v1/portfolio/buy", body),
  sell: (body: SellRequest) => post<{ message: string; pnl_pct: number }>("/api/v1/portfolio/sell", body),

  // SMC
  smcTrendsRaw: () => get<Record<string, SmcTrendMTF | string>>("/api/v1/stocks/smc-trends"),
  smcTrends: async (): Promise<Record<string, string>> => {
    const raw = await get<Record<string, SmcTrendMTF | string>>("/api/v1/stocks/smc-trends")
    const out: Record<string, string> = {}
    for (const [k, v] of Object.entries(raw)) {
      out[k] = typeof v === "string" ? v : v.daily
    }
    return out
  },
  smcTrendsMTF: async (): Promise<Record<string, SmcTrendMTF>> => {
    const raw = await get<Record<string, SmcTrendMTF | string>>("/api/v1/stocks/smc-trends")
    const out: Record<string, SmcTrendMTF> = {}
    for (const [k, v] of Object.entries(raw)) {
      out[k] = typeof v === "string"
        ? { daily: v, weekly: "未知", monthly: "未知" }
        : v
    }
    return out
  },
  stockSmc: (ticker: string, limit = 120, timeframe: "daily" | "weekly" | "monthly" = "daily") =>
    get<SmcData>(`/api/v1/stocks/${ticker}/smc?limit=${limit}&timeframe=${timeframe}`),

  // Realtime prices
  realtimePrice: (ticker: string) =>
    get<RealtimePrice>(`/api/v1/stocks/${ticker}/realtime`),
  realtimePrices: () =>
    get<Record<string, RealtimePrice>>(`/api/v1/stocks/realtime`),

  // Backtest
  backtestResults: () => get<BacktestSummary[]>("/api/v1/backtest/results"),
  backtestDetail: (id: number) => get<BacktestDetail>(`/api/v1/backtest/results/${id}`),
  triggerBacktest: (body: BacktestRequest) =>
    post<{ message: string }>("/api/v1/backtest/run", body),

  // Briefing
  nextOpenBriefing: () => get<NextOpenBriefing>("/api/v1/briefing/next-open"),

  // AI Notes
  aiNotes: (ticker?: string, limit = 20) =>
    get<AiNote[]>(`/api/v1/ai-notes${ticker ? `?ticker=${encodeURIComponent(ticker)}&limit=${limit}` : `?limit=${limit}`}`),
  aiNotesLatest: () => get<Record<string, AiNoteLatest>>("/api/v1/ai-notes/latest"),
  aiNote: (id: number) => get<AiNote>(`/api/v1/ai-notes/${id}`),
}

// Types
export type RealtimePrice = {
  ticker?: string; name?: string | null; market?: string
  price: number; open: number | null; high: number | null; low: number | null
  prev_close: number | null; change: number | null; change_pct: number | null
  volume: number | null; market_cap: number | null
}
export type SmcTrendMTF = { daily: string; weekly: string; monthly: string }
export type Stock = { id: number; ticker: string; name: string | null; market: string }
export type PriceBar = { date: string; open: number; high: number; low: number; close: number; volume: number }
export type AnalysisRow = {
  date: string; composite_score: number; technical_score: number; sentiment_score: number
  recommendation: string; rsi: number; macd: number; close_price: number
  signals: string[]; news_summary: Record<string, unknown>
  entry_suggestion?: EntrySuggestion | null
}
export type NewsItem = { id: number; title: string; url: string; source: string; published_at: string; sentiment_score: number }
export type EntrySuggestion = {
  entry: number        // 建議買進價
  stop: number         // 建議停損價
  target: number       // 目標價
  rr: number           // 風報比
  entry_basis?: string // 進場依據 e.g. "OB+FVG"
  target_basis?: string // 目標依據 e.g. "OB壓力"
  risk_pct?: number    // 風險百分比
  reward_pct?: number  // 獲利百分比
  position_tier?: string | null  // 倉位等級: "核心持倉" / "標準倉位" / "探索倉位"
}

export type TopPick = {
  ticker: string; market: string; name: string | null
  composite_score: number; technical_score: number; sentiment_score: number
  recommendation: string; rsi: number; close_price: number
  signals: string[]; news_summary: { label: string; article_count: number; score: number }
  entry_suggestion?: EntrySuggestion | null
}
export type LatestAnalysis = { date: string | null; results: TopPick[] }
export type Holding = {
  ticker: string; market: string; name: string | null
  shares: number; avg_cost: number; highest_price: number; cost_basis: number
  stop_loss_price: number; take_profit_price: number
}
export type Transaction = {
  id: number; ticker: string; market: string; action: string
  shares: number; price: number; total: number; note: string; date: string
}
export type BuyRequest = { ticker: string; shares: number; price: number; note?: string }
export type SellRequest = { ticker: string; shares: number; price: number; note?: string }
export type BacktestSummary = {
  id: number; name: string; start_date: string; end_date: string
  metrics: BacktestMetrics; created_at: string
}
export type BacktestMetrics = {
  total_return_pct: number; annual_return_pct: number; max_drawdown_pct: number
  sharpe_ratio: number; win_rate: number; total_trades: number; profitable_trades: number
  avg_profit_pct: number; avg_loss_pct: number
}
export type BacktestDetail = BacktestSummary & {
  config: Record<string, unknown>
  trades: BacktestTrade[]
  equity_curve: { date: string; equity: number }[]
}
export type BacktestTrade = {
  ticker: string; buy_date: string; buy_price: number
  sell_date: string; sell_price: number; pnl_pct: number; exit_reason: string
}
export type BacktestRequest = {
  name?: string; start_date: string; end_date: string
  buy_threshold?: number; stop_loss_pct?: number; trailing_stop_pct?: number
  initial_capital?: number; position_size_pct?: number; max_positions?: number
  use_smc_filter?: boolean; smc_exit_on_downtrend?: boolean
}

// SMC Types
export type OrderBlock = {
  type: "bullish" | "bearish"; date: string
  top: number; bottom: number; high: number; low: number
  strength: number; mitigated: boolean
}
export type FVG = {
  type: "bullish" | "bearish"; date: string
  top: number; bottom: number; gap_pct: number; filled: boolean
}
export type VolLevel = {
  price_low: number; price_high: number; price_mid: number
  buy_vol: number; sell_vol: number; total_vol: number
  is_poc: boolean; in_va: boolean; buy_pct: number; sell_pct: number
}
export type VolumeProfileData = {
  levels: VolLevel[]; poc: number; va_high: number; va_low: number
  price_min: number; price_max: number
}
export type SmcData = {
  order_blocks: OrderBlock[]
  fvg: FVG[]
  structure: {
    trend: string
    swing_highs: { index: number; date: string; price: number }[]
    swing_lows:  { index: number; date: string; price: number }[]
    bos: { type: string; date: string; price: number; broke: boolean }[]
  }
  volume_profile: VolumeProfileData
  probability: {
    bullish_pct: number; bearish_pct: number
    outlook: string; detail: string; reasons: string[]
  }
  key_levels: { type: "resistance" | "support"; price: number; date: string }[]
  entry_suggestion?: EntrySuggestion | null
}

export type NextOpenBriefing = {
  analysis_date: string | null
  market_indices: Record<string, { price: number; change_pct: number; trend: string }>
  portfolio: BriefingPortfolioItem[]
  watchlist: BriefingWatchItem[]
  portfolio_alerts: number
}
export type BriefingPortfolioItem = {
  ticker: string; market: string; name: string | null
  shares: number; avg_cost: number; current_price: number | null; pnl_pct: number | null
  stop_loss: number; smc_trend: string; alert: string | null
  composite_score: number | null; recommendation: string | null
  ai_action: string | null; ai_summary_preview: string | null
  ai_note_id: number | null; ai_note_at: string | null
}
export type BriefingWatchItem = {
  ticker: string; market: string; name: string | null
  composite_score: number | null; recommendation: string | null
  rsi: number | null; current_price: number | null
  entry_suggestion: EntrySuggestion | null; distance_pct: number | null
  signals: string[]
  ai_action: string | null; ai_summary_preview: string | null
  ai_note_id: number | null; ai_note_at: string | null
}

export type StockAnalysisResult = {
  ticker: string; prices_added: number; news_added: number
  analysis: {
    composite_score: number; technical_score: number; sentiment_score: number
    recommendation: string; position_tier: string | null
    smc_trend: string; catalyst: string; signals_met: number; signals: string[]
  }
}

// AI Note Types
export type AiNote = {
  id: number; stock_id: number; ticker: string
  analysis_type: string; recommendation: string; action: string | null
  summary: string
  price_at_analysis: number | null; composite_score: number | null; smc_trend: string | null
  entry_price: number | null; stop_price: number | null; target_price: number | null; rr_ratio: number | null
  scenarios: Record<string, unknown> | null
  created_at: string
}
export type AiNoteLatest = {
  id: number; recommendation: string; action: string | null
  analysis_type: string; created_at: string; summary_preview: string
}

export const SSE_URL = `${BASE}/sse/progress`
