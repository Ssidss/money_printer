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
  stockPrices: (ticker: string, limit = 120) =>
    get<PriceBar[]>(`/api/v1/stocks/${ticker}/prices?limit=${limit}`),
  stockAnalysis: (ticker: string) =>
    get<AnalysisRow[]>(`/api/v1/stocks/${ticker}/analysis`),
  stockNews: (ticker: string) =>
    get<NewsItem[]>(`/api/v1/stocks/${ticker}/news`),

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
  smcTrends: () => get<Record<string, string>>("/api/v1/stocks/smc-trends"),
  stockSmc: (ticker: string, limit = 120) =>
    get<SmcData>(`/api/v1/stocks/${ticker}/smc?limit=${limit}`),

  // Backtest
  backtestResults: () => get<BacktestSummary[]>("/api/v1/backtest/results"),
  backtestDetail: (id: number) => get<BacktestDetail>(`/api/v1/backtest/results/${id}`),
  triggerBacktest: (body: BacktestRequest) =>
    post<{ message: string }>("/api/v1/backtest/run", body),
}

// Types
export type Stock = { id: number; ticker: string; name: string | null; market: string }
export type PriceBar = { date: string; open: number; high: number; low: number; close: number; volume: number }
export type AnalysisRow = {
  date: string; composite_score: number; technical_score: number; sentiment_score: number
  recommendation: string; rsi: number; macd: number; close_price: number
  signals: string[]; news_summary: Record<string, unknown>
}
export type NewsItem = { id: number; title: string; url: string; source: string; published_at: string; sentiment_score: number }
export type EntrySuggestion = {
  entry: number   // 建議買進價
  stop: number    // 建議停損價
  target: number  // 目標價
  rr: number      // 風報比
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
  buy_threshold?: number; stop_loss_pct?: number; take_profit_pct?: number
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
}

export const SSE_URL = `${BASE}/sse/progress`
