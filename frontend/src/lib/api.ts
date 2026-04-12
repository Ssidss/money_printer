const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

// ── Token 管理（client-side only）──────────────────────
function getToken(): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem("mp_token")
}
export function setToken(token: string) {
  localStorage.setItem("mp_token", token)
}
export function clearToken() {
  localStorage.removeItem("mp_token")
}

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// ── HTTP helpers ────────────────────────────────────────
async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

/** GET with auth token */
async function getAuth<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    headers: authHeaders(),
  })
  if (res.status === 401) throw new Error("UNAUTHORIZED")
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

/** POST with auth token */
async function postAuth<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (res.status === 401) throw new Error("UNAUTHORIZED")
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function putAuth<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (res.status === 401) throw new Error("UNAUTHORIZED")
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

// ── Auth types ──────────────────────────────────────────
export type AuthUser = {
  id: number
  email: string
  display_name: string
  is_admin: boolean
}

export type TokenResponse = {
  access_token: string
  token_type: string
  user: AuthUser
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    post<TokenResponse>("/api/v1/auth/login", { email, password }),
  register: (email: string, password: string, display_name: string) =>
    post<TokenResponse>("/api/v1/auth/register", { email, password, display_name }),
  me: () => getAuth<AuthUser>("/api/v1/auth/me"),
  updateMe: (body: { display_name?: string; password?: string }) =>
    putAuth<AuthUser>("/api/v1/auth/me", body),

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

  // Portfolio (auth required)
  holdings: () => getAuth<Holding[]>("/api/v1/portfolio"),
  transactions: () => getAuth<Transaction[]>("/api/v1/portfolio/transactions"),
  buy: (body: BuyRequest) => postAuth<{ message: string }>("/api/v1/portfolio/buy", body),
  sell: (body: SellRequest) => postAuth<{ message: string; pnl_pct: number }>("/api/v1/portfolio/sell", body),

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

  // ── Strategy v2 ──
  strategies: () => get<StrategyListItem[]>("/api/v2/strategies"),
  strategy: (id: number) => get<StrategyFull>(`/api/v2/strategies/${id}`),
  createStrategy: (body: StrategyCreateReq) => post<StrategyFull>("/api/v2/strategies", body),
  updateStrategy: (id: number, body: Partial<StrategyCreateReq>) =>
    fetch(`${BASE}/api/v2/strategies/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(r => r.json()) as Promise<StrategyFull>,
  deleteStrategy: (id: number) => del<{ ok: boolean }>(`/api/v2/strategies/${id}`),
  activateStrategy: (id: number) => post<{ ok: boolean }>(`/api/v2/strategies/${id}/activate`, {}),
  cloneStrategy: (id: number) => post<StrategyFull>(`/api/v2/strategies/${id}/clone`, {}),

  // ── Backtest v2 ──
  backtestV2Run: (body: BacktestV2RunReq) => post<{ message: string }>("/api/v2/backtest/run", body),
  backtestV2Status: () => get<{ running: boolean }>("/api/v2/backtest/status"),
  backtestV2Results: (profileId?: number, limit = 20) =>
    get<BacktestV2Result[]>(`/api/v2/backtest/results?limit=${limit}${profileId ? `&profile_id=${profileId}` : ""}`),
  backtestV2Detail: (id: number) => get<BacktestV2Result>(`/api/v2/backtest/results/${id}`),
  backtestV2Trades: (id: number, limit = 50, offset = 0) =>
    get<BacktestV2Trade[]>(`/api/v2/backtest/results/${id}/trades?limit=${limit}&offset=${offset}`),
  backtestV2Equity: (id: number) =>
    get<BacktestV2EquityPoint[]>(`/api/v2/backtest/results/${id}/equity`),
  backtestV2Compare: (a: number, b: number) =>
    get<BacktestV2Compare>(`/api/v2/backtest/compare?a=${a}&b=${b}`),

  // ── Strategy signals ──
  strategySignals: (profileId: number, limit = 50) =>
    get<StrategySignal[]>(`/api/v2/strategies/${profileId}/signals?limit=${limit}`),
  followSignal: (profileId: number, signalId: number, body: { actual_entry?: number }) =>
    post<{ ok: boolean }>(`/api/v2/strategies/${profileId}/signals/${signalId}/follow`, body),
  skipSignal: (profileId: number, signalId: number, body: { skip_reason?: string }) =>
    post<{ ok: boolean }>(`/api/v2/strategies/${profileId}/signals/${signalId}/skip`, body),

  // Scanner (量價異常掃描器)
  scannerLatest: () => get<ScanResponse>("/api/v1/scanner"),
  scannerTracked: (minScore = 15) => get<ScanResponse>(`/api/v1/scanner/tracked?min_score=${minScore}`),
  scannerRun: (includeExternal = true, minScore = 15) =>
    post<{ message: string; running: boolean }>(
      `/api/v1/scanner/run?include_external=${includeExternal}&min_score=${minScore}`, {}
    ),
  scannerStatus: () => get<{ running: boolean }>("/api/v1/scanner/status"),

  // ── Backtest v3 (Multi-Strategy Engine) ──
  backtestV3Run: (body: BacktestV3RunReq) => post<{ message: string; status: string }>("/api/v3/backtest-v3/run", body),
  backtestV3Status: () => get<BacktestV3Status>("/api/v3/backtest-v3/status"),
  backtestV3Result: () => get<BacktestV3Report>("/api/v3/backtest-v3/result"),
  backtestV3Summary: () => get<{ portfolio_summary: BacktestV3Summary; metadata: BacktestV3Metadata }>("/api/v3/backtest-v3/result/summary"),
  backtestV3Trades: (limit = 50, offset = 0, strategy?: string, tier?: string) => {
    let url = `/api/v3/backtest-v3/result/trades?limit=${limit}&offset=${offset}`
    if (strategy) url += `&strategy=${encodeURIComponent(strategy)}`
    if (tier) url += `&tier=${encodeURIComponent(tier)}`
    return get<{ total: number; trades: BacktestV3Trade[] }>(url)
  },
  backtestV3Equity: () => get<BacktestV3EquityPoint[]>("/api/v3/backtest-v3/result/equity"),
  backtestV3Splits: () => get<BacktestV3Split[]>("/api/v3/backtest-v3/splits"),

  // Live Signals
  liveSignals: (ticker: string, strategies = "explosion_scanner,momentum_breakout") =>
    get<LiveSignalResponse>(`/api/v3/signals/${encodeURIComponent(ticker)}?strategies=${encodeURIComponent(strategies)}`),
  batchSignals: (strategy = "explosion_scanner", market = "US") =>
    get<BatchSignalResponse>(`/api/v3/signals/batch/all?strategy=${encodeURIComponent(strategy)}&market=${encodeURIComponent(market)}`),

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

// ── Strategy v2 Types ──────────────────────────────────────────
export type StrategyListItem = {
  id: number; name: string; description: string | null
  is_active: boolean; latest_backtest_id: number | null
  latest_metrics: BacktestV2Metrics | null
  created_at: string; updated_at: string
}
export type StrategyFull = StrategyListItem & {
  params: Record<string, unknown>
  overrides: Record<string, unknown>
  stock_settings: Record<string, unknown>
}
export type StrategyCreateReq = {
  name: string; description?: string
  params?: Record<string, unknown>
  overrides?: Record<string, unknown>
  stock_settings?: Record<string, unknown>
}

export type BacktestV2RunReq = {
  profile_id: number
  start_date: string; end_date: string
  initial_capital?: number; market_filter?: string
}
export type BacktestV2Metrics = {
  total_return_pct: number; annual_return_pct: number
  max_drawdown_pct: number; sharpe_ratio: number
  win_rate: number; total_trades: number
  profitable_trades: number; losing_trades: number
  avg_profit_pct: number; avg_loss_pct: number
  profit_factor: number; total_cost: number
  by_exit_reason: Record<string, { count: number; avg_pnl_pct: number }>
  by_tier: Record<string, { count: number; avg_pnl_pct: number }>
  by_group: Record<string, { count: number; avg_pnl_pct: number }>
}
export type BacktestV2Result = {
  id: number; profile_id: number; name: string | null
  start_date: string; end_date: string
  initial_capital: number; market_filter: string
  strategy_hash: string; run_hash: string
  stock_universe: { ticker: string; group: string }[]
  metrics: BacktestV2Metrics
  diagnosis: BacktestDiagnosis | null
  duration_secs: number | null
  stock_count: number | null; trading_days: number | null
  status: string; error_message: string | null
  created_at: string
}
export type BacktestDiagnosis = {
  highlights: string[]; warnings: string[]; suggestions: string[]
  by_trend: Record<string, { count: number; win_rate: number; avg_pnl: number }>
  by_tier: Record<string, { count: number; win_rate: number; avg_pnl: number }>
  stop_efficiency: { count: number; avg_loss_pct: number; pct_of_total: number }
  target_efficiency: { count: number; avg_gain_pct: number; pct_of_total: number }
  mae_mfe_analysis: Record<string, number>
}
export type BacktestV2Trade = {
  id: number; ticker: string; market: string; stock_group: string | null
  signal_date: string; fill_date: string; fill_price: number
  entry_source: string | null; position_tier: string | null
  conditions_met: number | null; position_size_pct: number | null
  exit_date: string | null; exit_price: number | null; exit_reason: string | null
  planned_rr: number | null; actual_rr: number | null
  pnl_pct: number | null; pnl_amount: number | null
  trade_cost: number | null; net_pnl: number | null; holding_days: number | null
  mae_pct: number | null; mfe_pct: number | null
  smc_trend_at_entry: string | null; smc_trend_at_exit: string | null
}
export type BacktestV2EquityPoint = {
  trade_date: string; equity: number; drawdown_pct: number | null
  cash: number | null; positions_value: number | null; open_positions: number | null
}
export type BacktestV2Compare = {
  profile_a: { id: number; name: string; metrics: BacktestV2Metrics }
  profile_b: { id: number; name: string; metrics: BacktestV2Metrics }
  params_diff: { key: string; a: unknown; b: unknown }[]
  metrics_comparison: Record<string, { a: number; b: number }>
  equity_a: { date: string; equity: number }[]
  equity_b: { date: string; equity: number }[]
}
export type StrategySignal = {
  id: number; ticker: string | null; signal_date: string
  signal_action: string; signal_entry: number | null
  signal_stop: number | null; signal_target: number | null
  signal_rr: number | null; signal_tier: string | null
  signal_conditions: number | null
  followed: boolean | null; actual_entry: number | null
  actual_pnl_pct: number | null
  outcome_if_followed: number | null
  skip_reason: string | null; notes: string | null
  created_at: string
}

// ── Scanner Types ─────────────────────────────────────────
export type ScanResult = {
  ticker: string
  market: string
  name: string | null
  close_price: number
  change_pct: number
  volume: number
  avg_volume_20: number
  volume_ratio: number
  consecutive_up_days: number
  cumulative_gain_pct: number
  is_52w_high: boolean
  is_20d_high: boolean
  vol_acceleration: number
  explosion_score: number
  signals: string[]
}

export type ScanResponse = {
  scan_date: string | null
  tracked_count: number
  external_count: number
  total_count: number
  results: ScanResult[]
  message?: string
}

// ── Backtest V3 Types ────────────────────────────────────────
export type BacktestV3RunReq = {
  split?: string
  start_date?: string
  end_date?: string
  initial_capital?: number
  min_conditions?: number
  min_rr?: number
  max_positions?: number
  risk_per_trade_pct?: number
  max_daily_loss_pct?: number
  market_filter?: string
  strategies?: string[]
}
export type BacktestV3Status = {
  running: boolean
  has_result: boolean
  error: string | null
}
export type BacktestV3Summary = {
  total_return_pct: number
  cagr_pct: number
  max_drawdown_pct: number
  sharpe_ratio: number
  sortino_ratio: number
  calmar_ratio: number
  profit_factor: number
  win_rate_pct: number
  total_trades: number
  avg_holding_days: number
  expectancy: number
  avg_exposure_pct: number
  max_consecutive_losses: number
  tail_risk_cvar_5pct: number
  avg_win_pct: number
  avg_loss_pct: number
  trading_days: number
  final_equity: number
  initial_capital: number
}
export type BacktestV3Metadata = {
  split: string
  start_date: string
  end_date: string
  initial_capital: number
  min_conditions: number
  min_rr: number
  max_positions: number
  risk_per_trade_pct: number
  max_daily_loss_pct: number
  strategies: string[]
  duration_seconds: number
  stock_count: number
  trading_days: number
}
export type BacktestV3Trade = {
  position_id: string
  ticker: string
  side: string
  strategy_name: string
  capital_pool: string
  entry_date: string
  entry_price: number
  exit_date: string | null
  exit_price: number | null
  exit_reason: string | null
  size: number
  gross_pnl: number | null
  commission: number
  slippage_cost: number
  net_pnl: number | null
  pnl_pct: number | null
  mae: number
  mfe: number
  holding_days: number
  position_tier: string
  confidence: number
  linked_signal_id?: string
  stop_price?: number | null
  target_price?: number | null
  signal_meta?: {
    strategy_name: string
    strategy_type: string
    confidence: number
    position_tier: string
    price_hint?: {
      entry: number
      stop: number
      target: number
      rr_ratio: number
    }
    meta: Record<string, unknown>
    timestamp: string
    expiry: string
  }
}
export type BacktestV3EquityPoint = {
  date: string
  equity: number
  drawdown_pct: number
  cash: number
  positions_value: number
  open_positions: number
}
export type BacktestV3TierBreakdown = {
  total_trades: number
  win_rate_pct: number
  profit_factor: number
  avg_pnl_pct: number
  total_pnl: number
  avg_holding_days: number
}
export type BacktestV3Report = {
  portfolio_summary: BacktestV3Summary
  strategy_breakdown: {
    by_strategy: Record<string, { total_trades: number; win_rate_pct: number; profit_factor: number; avg_pnl_pct: number }>
    by_exit_reason: Record<string, { count: number; avg_pnl_pct: number; total_pnl: number }>
    by_tier: Record<string, BacktestV3TierBreakdown>
  }
  trade_log: BacktestV3Trade[]
  equity_curve: BacktestV3EquityPoint[]
  order_stats: { total: number; filled: number; cancelled: number; cancel_reasons: Record<string, number> }
  kill_switch: { triggered: boolean; reason: string | null; date: string | null }
  open_positions: { ticker: string; strategy_name: string; entry_date: string; entry_price: number; current_price: number; unrealized_pnl_pct: number; size: number; holding_days: number }[]
  metadata: BacktestV3Metadata
}
export type BacktestV3Split = {
  name: string
  start_date: string
  end_date: string
}

// ── Live Signal Types ─────────────────────────────────────
export type LiveSignal = {
  signal_id: string
  strategy_name: string
  strategy_type: string
  action: string            // "buy" | "sell" | "hold" | "watch"
  confidence: number
  position_tier: string     // "核心" | "標準" | "探索"
  entry: number | null
  stop: number | null
  target: number | null
  rr_ratio: number | null
  expiry: string
  meta: Record<string, unknown>
}

export type LiveSignalResponse = {
  ticker: string
  data_date: string
  current_price: number | null
  signal_count: number
  signals: LiveSignal[]
  strategy_status: Record<string, { status: string; message?: string; signal_count: number }>
  timing: { data_load_ms: number; compute_ms: number }
}

export type BatchSignalResult = LiveSignal & {
  ticker: string
  current_price: number | null
}

export type BatchSignalResponse = {
  strategy: string
  data_date: string
  stock_count: number
  signal_count: number
  results: BatchSignalResult[]
  timing: { data_load_ms: number; compute_ms: number }
}

export const SSE_URL = `${BASE}/sse/progress`
