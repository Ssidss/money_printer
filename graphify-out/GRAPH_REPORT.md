# Graph Report - /home/chris/workspace/SIDE_PROJECT/money_printer  (2026-04-14)

## Corpus Check
- 152 files · ~111,939 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1156 nodes · 2234 edges · 89 communities detected
- Extraction: 68% EXTRACTED · 32% INFERRED · 0% AMBIGUOUS · INFERRED: 722 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_BacktestV3 核心引擎|BacktestV3 核心引擎]]
- [[_COMMUNITY_BacktestV2 舊版引擎|BacktestV2 舊版引擎]]
- [[_COMMUNITY_SMC 分析引擎|SMC 分析引擎]]
- [[_COMMUNITY_AI 筆記與持倉管理|AI 筆記與持倉管理]]
- [[_COMMUNITY_BacktestV3 多策略系統|BacktestV3 多策略系統]]
- [[_COMMUNITY_REST API 路由層|REST API 路由層]]
- [[_COMMUNITY_嵌入式 PostgreSQL 管理|嵌入式 PostgreSQL 管理]]
- [[_COMMUNITY_系統設定與環境配置|系統設定與環境配置]]
- [[_COMMUNITY_回測指標計算|回測指標計算]]
- [[_COMMUNITY_新聞情緒分析|新聞情緒分析]]
- [[_COMMUNITY_技術指標輔助函數|技術指標輔助函數]]
- [[_COMMUNITY_掃描器與即時事件|掃描器與即時事件]]
- [[_COMMUNITY_工程文件與架構決策|工程文件與架構決策]]
- [[_COMMUNITY_測試配置與 Mock|測試配置與 Mock]]
- [[_COMMUNITY_BacktestV2 資料庫 Schema|BacktestV2 資料庫 Schema]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]

## God Nodes (most connected - your core abstractions)
1. `Stock` - 68 edges
2. `SmcConfig` - 58 edges
3. `PriceHistory` - 53 edges
4. `TrendDirection` - 41 edges
5. `DataProvider` - 33 edges
6. `AnalysisResult` - 32 edges
7. `Signal` - 31 edges
8. `BaseStrategy` - 26 edges
9. `API Client (lib/api.ts)` - 26 edges
10. `HistoricalProvider` - 25 edges

## Surprising Connections (you probably didn't know these)
- `Backtest V3 SMC Strategy Implementation` --implements--> `SMC v2 Strategy (trend)`  [INFERRED]
  backend/app/services/backtest_v3/strategies/smc_strategy.py → docs/MULTI_STRATEGY_DESIGN.md
- `Backtest V3 Momentum Breakout Strategy Implementation` --implements--> `Momentum Breakout Strategy (breakout)`  [INFERRED]
  backend/app/services/backtest_v3/strategies/momentum_breakout.py → docs/MULTI_STRATEGY_DESIGN.md
- `Backtest V3 Explosion Scanner Strategy Implementation` --implements--> `Explosion Scanner Strategy (breakout, wrapper of scanner.py)`  [INFERRED]
  backend/app/services/backtest_v3/strategies/explosion_scanner.py → docs/MULTI_STRATEGY_DESIGN.md
- `RootLayout()` --references--> `Global CSS (Tailwind v4)`  [EXTRACTED]
  /home/chris/workspace/SIDE_PROJECT/money_printer/frontend/src/app/layout.tsx → frontend/src/app/globals.css
- `Backtest V3 Models (Signal, Decision, Order, Position dataclasses)` --implements--> `Signal Dataclass (signal_id, ticker, side, action, confidence, expiry, price_hint)`  [INFERRED]
  backend/app/services/backtest_v3/models.py → docs/MULTI_STRATEGY_DESIGN.md

## Hyperedges (group relationships)
- **Signal → Decision → Order → Fill → Position Pipeline** — multi_signal_dataclass, multi_decision_dataclass, multi_order_dataclass, multi_execution_layer, backtest_v3_models [EXTRACTED 1.00]
- **5-Layer Decision Architecture (MTF → SMC → Momentum → Catalyst → RR → MTF Align)** — readme_layer0_mtf_gate, readme_layer1_smc_structure, readme_layer2_momentum, readme_layer3_catalyst, readme_layer4_rr, readme_layer5_mtf_align, readme_layered_decision_engine [EXTRACTED 1.00]
- **Backtest Execution Iron Rules (T+1, Intraday Path, Gap Protection)** — multi_execution_rule_t1, multi_execution_rule_intraday_path, multi_execution_rule_gap_protection, us_1b01_t1_open_execution, us_1b02_gap_entry_protection, us_1b03_intraday_path, us_1b04_gap_stop [EXTRACTED 1.00]
- **Three Backtest V3 Strategies (SMC v2, Momentum Breakout, Explosion Scanner)** — backtest_v3_smc_strategy, backtest_v3_momentum_strategy, backtest_v3_explosion_strategy, multi_strategy_smc_v2, multi_strategy_momentum_breakout, multi_strategy_explosion_scanner [EXTRACTED 1.00]
- **DataProvider Interface and Implementations (ABC, Historical, Live)** — multi_data_provider_abc, multi_historical_provider, multi_live_provider, backtest_v3_provider, backtest_v3_live_provider [INFERRED 0.85]
- **Frontend App Shell (Layout Composition)** — layout_rootlayout, layout_sidebar, layout_topbar, layout_providers, layout_strategypanel [EXTRACTED 1.00]
- **React Context Providers (Auth + Strategy)** — layout_providers, context_authcontext, context_strategycontext [EXTRACTED 1.00]
- **Dashboard Page Composition** — page_dashboard, dashboard_toppickcard, dashboard_holdingssection, dashboard_analyzebutton, dashboard_batchfetchbutton [EXTRACTED 1.00]
- **Stock Detail Page Composition** — page_stock_detail, stock_chartcontrols, stock_stockchart, stock_ainotes, stock_strategysignals, stock_volumeprofile, stock_backbutton, stock_stockactions [EXTRACTED 1.00]
- **SMC v2 Type System** — type_smcv2data, type_entryplanv2, type_smctrendmtf, api_v2_smc [EXTRACTED 1.00]
- **Portfolio Management UI Flow** — portfolio_client, portfolio_buymodal, portfolio_sellmodal, api_v1_portfolio [EXTRACTED 1.00]
- **Versioned API Endpoints (v1/v2/v3)** — api_v1_analysis, api_v1_portfolio, api_v1_stocks, api_v2_smc, api_v2_strategies, api_v3_backtest, api_v3_signals [INFERRED 0.90]
- **Chart with SMC Overlay Pattern** — stock_stockchart, type_smcdata, lib_lightweightcharts, stock_chartcontrols [EXTRACTED 1.00]

## Communities

### Community 0 - "BacktestV3 核心引擎"
Cohesion: 0.03
Nodes (61): ABC, BaseStrategy, BacktestEngine, Backtest V3 — Core Engine  每日循環：   1. advance_day()   2. 更新持倉 mark-to-market（clo, 執行昨天產生的 orders — T+1 open fill, 檢查所有持倉的出場條件。         鐵律 2: 保守路徑 Open→Low→High→Close         鐵律 3: Gap stop → exi, 對 universe 中每個 ticker 跑所有策略，收集 signals, Phase 1A: 單策略直通模式 — 每個 buy signal 直接轉 decision。         同 ticker 只取 confidence 最 (+53 more)

### Community 1 - "BacktestV2 舊版引擎"
Cohesion: 0.05
Nodes (123): 回測引擎 v2 — SMC 分層決策回測  核心規則：   - T 日計算 SMC + EntryPlan，T+1 才能成交（防止前瞻偏差）   - 三種成交模, 載入所有股票 + price_history。     Returns: (stocks_info, price_data)       stocks_info, 計算 T 日的 SMC + EntryPlan。     只使用 target_date 當天及之前的資料（防止前瞻偏差）。, v2 回測引擎核心。      Returns:         {             "strategy_hash": str,, Limit order: T+1 日 Low <= entry_price → 以 entry_price 成交, Close price: 無條件以 T+1 收盤價成交, SMC v2 — 所有可調參數集中管理  修改任何參數會改變 strategy_hash → 觸發全量重算。, SMC 引擎全域配置（immutable） (+115 more)

### Community 2 - "SMC 分析引擎"
Cohesion: 0.04
Nodes (100): AnalysisResult, _compute_entry(), _extract_smc_summary(), _get_entry(), latest_analysis(), NewsArticle, 取得指定日期（預設今天）的 Top N 推薦, 舊版 MA 進場建議（向後相容用，新分析都用 SMC 驅動版） (+92 more)

### Community 3 - "AI 筆記與持倉管理"
Cohesion: 0.03
Nodes (70): AiAnalysisNote, AiNoteCreate, get_ai_note(), get_latest_notes(), list_ai_notes(), _note_to_dict(), 列出 AI 分析筆記，可按 ticker 或 analysis_type 過濾, 取得每支股票最新一筆 AI 筆記（用於清單頁顯示最後分析時間 + 推薦等級） (+62 more)

### Community 4 - "BacktestV3 多策略系統"
Cohesion: 0.05
Nodes (52): Backtest V3 Engine (backend/app/services/backtest_v3/engine.py), Backtest V3 Explosion Scanner Strategy Implementation, Backtest V3 LiveProvider, Backtest V3 Metrics (CAGR, Sharpe, Sortino, Calmar, CVaR calculations), Backtest V3 Models (Signal, Decision, Order, Position dataclasses), Backtest V3 Momentum Breakout Strategy Implementation, Backtest V3 Provider (HistoricalProvider implementation), Backtest V3 SMC Strategy Implementation (+44 more)

### Community 5 - "REST API 路由層"
Cohesion: 0.07
Nodes (45): API: /api/v1/ai-notes/* (AI Notes Endpoints), API: /api/v1/analysis/* (Analysis Endpoints), API: /api/v1/briefing/* (Briefing Endpoints), API: /api/v1/portfolio/* (Portfolio Endpoints), API: /api/v1/scanner/* (Scanner Endpoints), API: /api/v1/stocks/* (Stock Endpoints), API: /api/v2/smc/* (SMC v2 Endpoints), API: /api/v2/strategies/* (Strategy Endpoints) (+37 more)

### Community 6 - "嵌入式 PostgreSQL 管理"
Cohesion: 0.06
Nodes (20): PostgreSQLManager, 嵌入式 PostgreSQL 啟動管理器 優先使用系統 pg_ctl/initdb，fallback 至 embedded-postgres 套件, 使用 embedded-postgres 套件啟動 PostgreSQL, 等待 PostgreSQL 就緒（能接受連接）, 管理嵌入式 PostgreSQL 實例的啟動、停止、狀態檢查, 初始化 PostgreSQL 管理器          Args:             pgdata_dir: PostgreSQL 資料目錄，預設 ~/., 啟動 PostgreSQL 實例          Returns:             dict with keys: host, port, runni, 使用系統 pg_ctl 啟動 PostgreSQL (+12 more)

### Community 7 - "系統設定與環境配置"
Cohesion: 0.08
Nodes (29): _catalyst_level(), _compute_composite(), _layered_decision(), run_analysis_for_stock(), run_full_analysis(), analyze_df(), analyze_stock(), load_price_df() (+21 more)

### Community 8 - "回測指標計算"
Cohesion: 0.08
Nodes (29): calc_metrics(), calc_trade_cost(), compute_data_hash(), compute_run_hash(), compute_strategy_hash(), load_all_price_data(), Position, precompute_smc_for_date() (+21 more)

### Community 9 - "新聞情緒分析"
Cohesion: 0.09
Nodes (32): crawl_and_store_news(), _google_news(), _parse_date(), _yahoo_news(), 情緒分析 Service — 關鍵字加權，中英文雙語，不需付費 API, 單一標題 → 情緒分數 0~100（50=中性）, score_title(), _collect_htf_key_levels() (+24 more)

### Community 10 - "技術指標輔助函數"
Cohesion: 0.09
Nodes (30): compute_atr(), compute_volume_sma(), df_to_arrays(), _ensure_datetime_index(), get_current_atr(), get_swing_n(), get_swing_tolerance(), get_tick_size() (+22 more)

### Community 11 - "掃描器與即時事件"
Cohesion: 0.09
Nodes (15): emit_progress(), SSE Event Manager — 廣播即時進度給所有連線中的前端, 生成器：讓 FastAPI SSE endpoint 訂閱事件流, SSEManager, _analyze_stock_from_db(), _compute_explosion_score(), _compute_scan_result(), 啟動完整掃描（追蹤 + 外部池，背景執行） (+7 more)

### Community 12 - "工程文件與架構決策"
Cohesion: 0.08
Nodes (30): New Decision Engine Module Structure (entry/sentiment_gate/mtf_gate/position_sizer/portfolio_risk), Money Printer Engineering Refactor Spec v1.2, Decision: recommender.py Rewrite (needs pure SMC + sentiment decision engine), New SMC Engine Module Structure (structure/order_block/fvg/liquidity/fibonacci/regime), Decision: smc.py Rewrite (no Fibonacci, no liquidity, no CHoCH/MSS in v1), Decision: technical.py Deleted (v5.0 strategy does not use traditional TA indicators), AI Analysis Notes (Historical Recommendation Tracking), Composite Score v3 (Condition 0-50 + RR 0-30 + Position 0-20) (+22 more)

### Community 13 - "測試配置與 Mock"
Cohesion: 0.1
Nodes (24): BaseSettings, Settings, db_with_test_data(), pytest 配置和通用 fixtures, 提供臨時的 PostgreSQL 資料目錄, 提供含有測試資料的 AsyncSession     用於 briefing 性能測試和功能驗證      注意：此 fixture 需要實際的 Postgre, temp_pgdata_dir(), Tests for config.py AUTO_DB property (+16 more)

### Community 14 - "BacktestV2 資料庫 Schema"
Cohesion: 0.12
Nodes (16): Backtest Engine v2 Architecture — Software Design, DB Table: backtest_equity, DB Table: backtest_results_v2, DB Table: backtest_trades, DB Table: strategy_profiles (params JSONB, overrides, stock_settings, is_active), DB Table: strategy_signals, Backtest Engine v2 Design — SMC v2 Upgrade from v1, Backtest Fill Model C: Close Price (optimistic, not recommended as primary) (+8 more)

### Community 15 - "Community 15"
Cohesion: 0.21
Nodes (14): calculate_metrics(), _daily_returns(), _max_consecutive_losses(), _portfolio_summary(), Backtest V3 — Metrics Calculator  三層報表：   Level 1: Portfolio Summary（14 個指標）   L, 從 engine 的 raw result 計算完整 metrics。     回傳三層報表結構。, 從 equity curve 算 daily returns, Sharpe = mean(excess_return) / std(return) × √252 (+6 more)

### Community 16 - "Community 16"
Cohesion: 0.18
Nodes (3): DataProvider, LiveProvider, 即時信號用 Provider。      跟 HistoricalProvider 的差別：     - 不需要 advance_day()，直接以最新日期為

### Community 17 - "Community 17"
Cohesion: 0.27
Nodes (12): activate_strategy(), clone_strategy(), create_strategy(), delete_strategy(), follow_signal(), _get_profile(), _get_signal(), get_strategy() (+4 more)

### Community 18 - "Community 18"
Cohesion: 0.18
Nodes (4): 測試 fetcher.py — 台股 symbol 快取 + time.sleep 移除, 測試不存在 time.sleep 延遲（效能檢查）, 測試 _resolve_tw_symbol 的快取和效能, TestResolveTwSymbol

### Community 19 - "Community 19"
Cohesion: 0.25
Nodes (5): authHeaders(), getAuth(), getToken(), postAuth(), putAuth()

### Community 20 - "Community 20"
Cohesion: 0.2
Nodes (0): 

### Community 21 - "Community 21"
Cohesion: 0.25
Nodes (7): 測試 briefing.py N+1 查詢修正 驗證 /briefing/next-open 端點的查詢計數和功能正確性, 測試 /briefing/next-open 的 DB 查詢次數 ≤ 5 次     驗證 N+1 修正成功, 測試 watchlist 和 portfolio 的 AI 筆記被正確填充     驗證 v1_ai_map 和其他 batch 查詢已正確使用, 測試 /briefing/next-open 返回結構正確性     驗證功能未因優化而破損, test_briefing_ai_notes_populated(), test_briefing_next_open_query_count(), test_briefing_next_open_structure()

### Community 22 - "Community 22"
Cohesion: 0.25
Nodes (0): 

### Community 23 - "Community 23"
Cohesion: 0.4
Nodes (0): 

### Community 24 - "Community 24"
Cohesion: 0.6
Nodes (3): loadTradesAndEquity(), refreshResults(), selectResult()

### Community 25 - "Community 25"
Cohesion: 0.4
Nodes (0): 

### Community 26 - "Community 26"
Cohesion: 0.67
Nodes (3): main(), parse_args(), Backtest V3 — 驗證腳本  用 SMCStrategy 在新引擎跑回測，支援 Train/Validation/Test split。  Usage

### Community 27 - "Community 27"
Cohesion: 0.5
Nodes (0): 

### Community 28 - "Community 28"
Cohesion: 0.5
Nodes (0): 

### Community 29 - "Community 29"
Cohesion: 0.5
Nodes (0): 

### Community 30 - "Community 30"
Cohesion: 0.5
Nodes (0): 

### Community 31 - "Community 31"
Cohesion: 0.83
Nodes (3): handleClose(), handleSubmit(), reset()

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (2): main(), run_one()

### Community 33 - "Community 33"
Cohesion: 0.67
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 0.67
Nodes (0): 

### Community 35 - "Community 35"
Cohesion: 0.67
Nodes (0): 

### Community 36 - "Community 36"
Cohesion: 0.67
Nodes (0): 

### Community 37 - "Community 37"
Cohesion: 0.67
Nodes (0): 

### Community 38 - "Community 38"
Cohesion: 0.67
Nodes (3): GET /api/v1/briefing/morning Endpoint, KINA-246: Briefing N+1 Query Optimization, ROW_NUMBER() OVER (PARTITION BY stock_id) Window Function Fix

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (0): 

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (0): 

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (0): 

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (0): 

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (0): 

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (0): 

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (0): 

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (0): 

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (0): 

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (0): 

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (0): 

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (0): 

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (0): 

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (0): 

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (0): 

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (0): 

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (0): 

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (0): 

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (0): 

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (0): 

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (0): 

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (0): 

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (0): 

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): 是否自動啟動嵌入式 PostgreSQL（條件：localhost + 空密碼 + postgres 用戶）

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): [CRITICAL-SEC] 生產環境必須使用自訂 SECRET_KEY，不允許預設值

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (0): 

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (0): 

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (0): 

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): 回傳 OHLCV DataFrame, index=date, max(date) <= current_date

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): current_date 的 close price

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): convenience: RSI, MACD, MA, ATR, BB, Volume — 用 get_ohlcv() 算

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): {"score": 72, "label": "正面", "article_count": 5}

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): {"vix": 18.5, "spy_trend": "uptrend", "regime": "trending"}

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): 停牌 / 資料不足 / 流動性太差 → False

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (1): 前進一天，回傳新日期。超出 end_date → None

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (1): 當前風險金額：用於 portfolio risk cap

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (0): 

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (0): 

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (0): 

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (0): 

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (0): 

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (0): 

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (0): 

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (0): 

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): US-1B-05: Order State Management (pending→filled/cancelled, no cross-day pending)

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): US-1B-06: Portfolio Risk Cap (total simultaneous stop risk ≤ 5%)

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): US-2-04: Strategy Correlation Analysis (diversification verification)

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (1): Development Progress Tracker (task/TODO.md)

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): StocksTable Component

## Knowledge Gaps
- **142 isolated node(s):** `Backtest V3 — 驗證腳本  用 SMCStrategy 在新引擎跑回測，支援 Train/Validation/Test split。  Usage`, `是否自動啟動嵌入式 PostgreSQL（條件：localhost + 空密碼 + postgres 用戶）`, `[CRITICAL-SEC] 生產環境必須使用自訂 SECRET_KEY，不允許預設值`, `嵌入式 PostgreSQL 啟動管理器 優先使用系統 pg_ctl/initdb，fallback 至 embedded-postgres 套件`, `管理嵌入式 PostgreSQL 實例的啟動、停止、狀態檢查` (+137 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 39`** (2 nodes): `main.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (2 nodes): `useSSE.ts`, `useSSE()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (2 nodes): `page.tsx`, `TrendBadge()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (2 nodes): `page.tsx`, `PortfolioPage()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (2 nodes): `page.tsx`, `StocksPage()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (2 nodes): `page.tsx`, `handleSubmit()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (2 nodes): `layout.tsx`, `LoginLayout()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (2 nodes): `page.tsx`, `StrategiesPage()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (2 nodes): `page.tsx`, `StrategyDetailPage()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (2 nodes): `TopPickCard.tsx`, `ScoreBar()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (2 nodes): `trigger()`, `BatchFetchButton.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (2 nodes): `trigger()`, `AnalyzeButton.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (2 nodes): `TrendBadge()`, `HoldingsSection.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (2 nodes): `StockChart.tsx`, `StockChart()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (2 nodes): `BackButton()`, `BackButton.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (2 nodes): `VolumeProfile.tsx`, `VolumeProfile()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (2 nodes): `SellModal.tsx`, `submit()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (2 nodes): `submit()`, `BuyModal.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (2 nodes): `RemoveStockButton.tsx`, `RemoveStockButton()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (2 nodes): `UserMenu.tsx`, `UserMenu()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (2 nodes): `Sidebar.tsx`, `handleLogout()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (2 nodes): `Providers.tsx`, `Providers()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `是否自動啟動嵌入式 PostgreSQL（條件：localhost + 空密碼 + postgres 用戶）`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `[CRITICAL-SEC] 生產環境必須使用自訂 SECRET_KEY，不允許預設值`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `回傳 OHLCV DataFrame, index=date, max(date) <= current_date`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `current_date 的 close price`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `convenience: RSI, MACD, MA, ATR, BB, Volume — 用 get_ohlcv() 算`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `{"score": 72, "label": "正面", "article_count": 5}`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `{"vix": 18.5, "spy_trend": "uptrend", "regime": "trending"}`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `停牌 / 資料不足 / 流動性太差 → False`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `前進一天，回傳新日期。超出 end_date → None`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `當前風險金額：用於 portfolio risk cap`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `next.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `page.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `page.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `page.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `page.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `StrategySignals.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `TopBar.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `US-1B-05: Order State Management (pending→filled/cancelled, no cross-day pending)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `US-1B-06: Portfolio Risk Cap (total simultaneous stop risk ≤ 5%)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `US-2-04: Strategy Correlation Analysis (diversification verification)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (1 nodes): `Development Progress Tracker (task/TODO.md)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `StocksTable Component`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Stock` connect `SMC 分析引擎` to `回測指標計算`, `BacktestV2 舊版引擎`, `AI 筆記與持倉管理`, `掃描器與即時事件`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `Base` connect `AI 筆記與持倉管理` to `SMC 分析引擎`, `測試配置與 Mock`, `嵌入式 PostgreSQL 管理`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Why does `DataProvider` connect `BacktestV3 核心引擎` to `Community 16`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Are the 66 inferred relationships involving `Stock` (e.g. with `Base` and `Live Signal API — Phase B  用 V3 策略邏輯對最新市場數據即時計算信號。 跟回測的差別：回測跑 2 年歷史，這裡跑「今天」。  En`) actually correct?**
  _`Stock` has 66 INFERRED edges - model-reasoned connections that need verification._
- **Are the 55 inferred relationships involving `SmcConfig` (e.g. with `Position` and `回測引擎 v2 — SMC 分層決策回測  核心規則：   - T 日計算 SMC + EntryPlan，T+1 才能成交（防止前瞻偏差）   - 三種成交模`) actually correct?**
  _`SmcConfig` has 55 INFERRED edges - model-reasoned connections that need verification._
- **Are the 51 inferred relationships involving `PriceHistory` (e.g. with `Base` and `Live Signal API — Phase B  用 V3 策略邏輯對最新市場數據即時計算信號。 跟回測的差別：回測跑 2 年歷史，這裡跑「今天」。  En`) actually correct?**
  _`PriceHistory` has 51 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `TrendDirection` (e.g. with `Position` and `回測引擎 v2 — SMC 分層決策回測  核心規則：   - T 日計算 SMC + EntryPlan，T+1 才能成交（防止前瞻偏差）   - 三種成交模`) actually correct?**
  _`TrendDirection` has 38 INFERRED edges - model-reasoned connections that need verification._