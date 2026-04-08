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

  // SMC v2 API
  smcV2: (ticker: string) => get<SmcV2Response>(`/api/v2/smc/stocks/${ticker}`),
  smcV2Entry: (ticker: string) => get<SmcV2EntryResponse>(`/api/v2/smc/stocks/${ticker}/entry`),
  smcV2Summary: (ticker: string) => get<SmcV2Summary>(`/api/v2/smc/stocks/${ticker}/summary`),
  smcV2TopPicks: (n = 10) => get<SmcV2TopPicks>(`/api/v2/smc/analysis/top-picks?n=${n}`),
  smcV2Trends: () => get<SmcV2TrendsResponse>("/api/v2/smc/analysis/trends"),
  smcV2Run: (ticker?: string) =>
    post<{ message: string; running: boolean }>(
      `/api/v2/smc/analysis/run${ticker ? `?ticker=${encodeURIComponent(ticker)}` : ""}`,
      {},
    ),
  smcV2Status: () => get<{ running: boolean }>("/api/v2/smc/analysis/status"),

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
export type SmcTrendMTF = {
  daily: string; weekly: string; monthly: string
  regime?: string | null
  recommendation?: string | null
  action?: string | null
  rr_ratio?: number | null
  source?: "v1" | "v2"
}
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
  smc_v2?: SmcV2Inline
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
  stop_loss: number; take_profit: number | null
  smc_trend: string; alert: string | null
  smc_v2?: SmcV2Inline
  composite_score: number | null; recommendation: string | null
  ai_action: string | null; ai_summary_preview: string | null
  ai_note_id: number | null; ai_note_at: string | null
}
export type BriefingWatchItem = {
  ticker: string; market: string; name: string | null
  composite_score: number | null; recommendation: string | null
  current_price: number | null
  smc_v2?: SmcV2Inline
  distance_pct: number | null
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

// ── SMC v2 Types ──────────────────────────────────────────────
export type SmcV2Response = {
  ticker: string
  analysis_date: string
  computed_at: string | null
  stale: boolean
  smc: SmcV2Data
}

export type SmcV2EntryResponse = {
  ticker: string
  analysis_date: string
  computed_at: string | null
  stale: boolean
  entry_plan: EntryPlanV2
}

export type SmcV2Summary = {
  ticker: string
  analysis_date: string
  stale: boolean
  trend: string
  regime: string | null
  recommendation: string
  action: string
  entry_price: number | null
  stop_price: number | null
  target_price: number | null
  rr_ratio: number | null
  position_tier: string
  current_price: number | null
  warnings: string[]
}

export type SmcV2TopPicks = {
  date: string | null
  count: number
  picks: SmcV2Pick[]
}

export type SmcV2Pick = {
  ticker: string; market: string; name: string | null
  trend: string; regime: string | null
  recommendation: string; action: string
  entry_price: number | null; stop_price: number | null; target_price: number | null
  rr_ratio: number | null; position_tier: string
  max_position_pct: number; conditions_met: number
  current_price: number | null
}

export type SmcV2TrendsResponse = {
  date: string | null
  count: number
  stocks: SmcV2TrendItem[]
}

export type SmcV2TrendItem = {
  ticker: string; market: string; name: string | null
  trend: string; regime: string | null
  recommendation: string; action: string
  rr_ratio: number | null; current_price: number | null
}

export type EntryPlanV2 = {
  ticker: string
  recommendation: string  // "強力推薦" | "推薦" | "觀察" | "觀望" | "不推薦"
  action: string           // "買入" | "等回調" | "觀望" | "不操作"
  entry_price: number | null
  entry_source: string     // "OB(7.8)" | "FVG(B)" | "SwingLow" | "OTE"
  stop_price: number | null
  stop_source: string
  target_price: number | null
  target_source: string
  rr_ratio: number | null
  position_tier: string    // "核心" | "標準" | "探索" | "none"
  max_position_pct: number
  conditions_met: number
  conditions_detail: Record<string, boolean>
  sentiment: { score: number | null; signal: string; reason: string }
  mtf: {
    monthly_trend: string; weekly_trend: string; daily_trend: string
    action: string; max_position_tier: string; max_position_pct: number
  }
  current_price: number
  distance_to_entry_pct: number | null
  warnings: string[]
}

export type SmcV2Data = {
  ticker: string; timeframe: string; bar_count: number
  computed_at: string; strategy_hash: string
  structure: {
    trend: string
    swing_highs: { index: number; date: string; price: number; type: string }[]
    swing_lows: { index: number; date: string; price: number; type: string }[]
    events: { type: string; direction: string; date: string; price: number; index: number }[]
  }
  order_blocks: {
    active_bullish: SmcV2OrderBlock[]
    active_bearish: SmcV2OrderBlock[]
  }
  fvg: {
    active: SmcV2Fvg[]
    gaps: SmcV2Fvg[]
  }
  liquidity: {
    bsl: SmcV2LiqPool[]
    ssl: SmcV2LiqPool[]
  }
  fibonacci: {
    valid: boolean
    current_zone: string
    levels: Record<string, number>
    swing_high_price: number | null
    swing_low_price: number | null
  }
  regime: { regime: string | null; atr_percentile: number | null }
  warnings: string[]
  data_quality: string
}

export type SmcV2OrderBlock = {
  type: "bullish" | "bearish"
  top: number; bottom: number
  date: string; index: number
  score: number; status: string
  retests: number
}

export type SmcV2Fvg = {
  type: "bullish" | "bearish"
  top: number; bottom: number; ce: number
  date: string; index: number
  grade: string; status: string
  gap_pct: number; freshness: number
}

export type SmcV2LiqPool = {
  price: number; touches: number
  first_date: string; last_date: string
  swept: boolean; sweep_date: string | null
  liq_score: number
}

// ── v1 TopPick with optional v2 data ──
export type SmcV2Inline = {
  trend: string
  regime: string | null
  recommendation: string | null
  action: string | null
  entry_price: number | null
  stop_price: number | null
  target_price: number | null
  rr_ratio: number | null
  position_tier: string | null
} | null

export const SSE_URL = `${BASE}/sse/progress`
