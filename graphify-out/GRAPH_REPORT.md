# Graph Report - /home/chris/workspace/SIDE_PROJECT/money_printer/backend/app/services  (2026-04-14)

## Corpus Check
- Corpus is ~33,458 words - fits in a single context window. You may not need a graph.

## Summary
- 546 nodes · 970 edges · 29 communities detected
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 230 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_SMC 分析引擎|SMC 分析引擎]]
- [[_COMMUNITY_VectorBT 回測層|VectorBT 回測層]]
- [[_COMMUNITY_BacktestV3 策略架構|BacktestV3 策略架構]]
- [[_COMMUNITY_AI 分析筆記|AI 分析筆記]]
- [[_COMMUNITY_數據抓取層|數據抓取層]]
- [[_COMMUNITY_TWSE 台股數據|TWSE 台股數據]]
- [[_COMMUNITY_持倉管理|持倉管理]]
- [[_COMMUNITY_警報通知|警報通知]]
- [[_COMMUNITY_BacktestV2 舊版|BacktestV2 舊版]]
- [[_COMMUNITY_BacktestV1 舊版|BacktestV1 舊版]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
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

## God Nodes (most connected - your core abstractions)
1. `SmcConfig` - 58 edges
2. `DataProvider` - 36 edges
3. `Signal` - 34 edges
4. `HistoricalProvider` - 32 edges
5. `BaseStrategy` - 29 edges
6. `BacktestEngine` - 23 edges
7. `SMCStrategy` - 17 edges
8. `LiveProvider` - 16 edges
9. `ExplosionScannerStrategy` - 15 edges
10. `MockStrategy` - 15 edges

## Surprising Connections (you probably didn't know these)
- `回測引擎 v2 — SMC 分層決策回測  核心規則：   - T 日計算 SMC + EntryPlan，T+1 才能成交（防止前瞻偏差）   - 三種成交模` --uses--> `SmcConfig`  [INFERRED]
  /home/chris/workspace/SIDE_PROJECT/money_printer/backend/app/services/backtester_v2.py → /home/chris/workspace/SIDE_PROJECT/money_printer/backend/app/services/smc/config.py
- `Limit order: T+1 日 Low <= entry_price → 以 entry_price 成交` --uses--> `SmcConfig`  [INFERRED]
  /home/chris/workspace/SIDE_PROJECT/money_printer/backend/app/services/backtester_v2.py → /home/chris/workspace/SIDE_PROJECT/money_printer/backend/app/services/smc/config.py
- `Close price: 無條件以 T+1 收盤價成交` --uses--> `SmcConfig`  [INFERRED]
  /home/chris/workspace/SIDE_PROJECT/money_printer/backend/app/services/backtester_v2.py → /home/chris/workspace/SIDE_PROJECT/money_printer/backend/app/services/smc/config.py
- `載入所有股票 + price_history。     Returns: (stocks_info, price_data)       stocks_info` --uses--> `SmcConfig`  [INFERRED]
  /home/chris/workspace/SIDE_PROJECT/money_printer/backend/app/services/backtester_v2.py → /home/chris/workspace/SIDE_PROJECT/money_printer/backend/app/services/smc/config.py
- `計算 T 日的 SMC + EntryPlan。     只使用 target_date 當天及之前的資料（防止前瞻偏差）。` --uses--> `SmcConfig`  [INFERRED]
  /home/chris/workspace/SIDE_PROJECT/money_printer/backend/app/services/backtester_v2.py → /home/chris/workspace/SIDE_PROJECT/money_printer/backend/app/services/smc/config.py

## Communities

### Community 0 - "SMC 分析引擎"
Cohesion: 0.04
Nodes (88): SMC v2 — 所有可調參數集中管理  修改任何參數會改變 strategy_hash → 觸發全量重算。, SMC 引擎全域配置（immutable）, 參數的 md5 hash，用於偵測配置變更, SmcConfig, analyze_fibonacci(), _compute_fib_levels(), _determine_zone(), _find_candidate_legs() (+80 more)

### Community 1 - "VectorBT 回測層"
Cohesion: 0.08
Nodes (46): ABC, _build_registry(), _generate_signal_series(), get_strategy_registry(), list_strategies(), VectorBT 整合 — 策略回測 Service  架構：   1. STRATEGY_REGISTRY — 所有可用策略的 class map   2., 回傳 STRATEGY_REGISTRY（lazy import 版本，避免啟動時間問題）, 回傳所有策略的清單（含 name / label / default_params） (+38 more)

### Community 2 - "BacktestV3 策略架構"
Cohesion: 0.05
Nodes (7): _compute_explosion_metrics(), 計算爆擊分數 (0-100)，權重同 scanner.py, _score_explosion(), Backtest V3 — Core Data Models Signal / Decision / Order / Position / Portfolio, get_split_dates(), Backtest V3 — DataProvider  策略的唯一數據來源。策略不碰 DB，全部透過 Provider。 HistoricalProvider:, 回傳 (start_date, end_date) for a named split.

### Community 3 - "AI 分析筆記"
Cohesion: 0.09
Nodes (20): BacktestEngine, Backtest V3 — Core Engine  每日循環：   1. advance_day()   2. 更新持倉 mark-to-market（clo, 執行昨天產生的 orders — T+1 open fill, 檢查所有持倉的出場條件。         鐵律 2: 保守路徑 Open→Low→High→Close         鐵律 3: Gap stop → exi, 對 universe 中每個 ticker 跑所有策略，收集 signals, Phase 1A: 單策略直通模式 — 每個 buy signal 直接轉 decision。         同 ticker 只取 confidence 最, Decision → Order（1:1）, Decision (+12 more)

### Community 4 - "數據抓取層"
Cohesion: 0.07
Nodes (30): _determine_action(), _find_entry(), _find_stop(), _find_target(), generate_entry_plan(), Decision v2 — 進場建議生成  整合 SMC 全模組結果 → 產生具體的進場/停損/目標價位。, 找進場價位（優先級）：     1. Bullish OB 上緣（score 最高的）     2. Bullish FVG CE 中線     3. 最近 S, 找停損價位（優先級）：     1. OB 底部 - ATR buffer     2. FVG 底部     3. 最近 Swing Low - ATR bu (+22 more)

### Community 5 - "TWSE 台股數據"
Cohesion: 0.08
Nodes (28): calc_metrics(), calc_trade_cost(), compute_data_hash(), compute_run_hash(), compute_strategy_hash(), load_all_price_data(), Position, precompute_smc_for_date() (+20 more)

### Community 6 - "持倉管理"
Cohesion: 0.13
Nodes (25): _collect_htf_key_levels(), compute_smc_entry(), find_fvg(), find_order_blocks(), find_structure(), _find_swing_highs(), _find_swing_lows(), mtf_alignment() (+17 more)

### Community 7 - "警報通知"
Cohesion: 0.11
Nodes (21): ensure_stock_exists(), fetch_all_stocks(), fetch_and_store_prices(), _fetch_realtime_price(), _fetch_yfinance(), get_earliest_price_date(), get_latest_price_date(), 抓取股價並寫入 DB，只補齊缺失的日期      Returns:         寫入的新資料筆數 (+13 more)

### Community 8 - "BacktestV2 舊版"
Cohesion: 0.14
Nodes (16): crawl_and_store_news(), _google_news(), _parse_date(), 爬取一支股票的新聞並寫入 DB，回傳新增筆數, _yahoo_news(), _catalyst_level(), _compute_composite(), _layered_decision() (+8 more)

### Community 9 - "BacktestV1 舊版"
Cohesion: 0.15
Nodes (4): HistoricalProvider, 取特定日期的 bar — 只給 engine 用, Convenience: 用 get_ohlcv() 算常見技術指標, 回測用 Provider — 從預載的 price_data dict 取數據。      price_data: {"NVDA": DataFrame(ind

### Community 10 - "Community 10"
Cohesion: 0.15
Nodes (4): DataProvider, LiveProvider, Backtest V3 — LiveProvider  即時信號用的 DataProvider 實作。 從 DB 載入的 price_data 中取最新日期作為, 即時信號用 Provider。      跟 HistoricalProvider 的差別：     - 不需要 advance_day()，直接以最新日期為

### Community 11 - "Community 11"
Cohesion: 0.18
Nodes (15): analyze_df(), analyze_stock(), load_price_df(), 布林通道評分（趨勢追蹤版）     - 突破上軌 = 強勢動能，高分     - 中軌以上 = 健康趨勢     - 跌破下軌 = 弱勢, 量價配合評分（趨勢追蹤版）     - 漲 + 量增 = 好（有資金推動）     - 漲 + 量縮 = 差（動能不足）     - 跌 + 量增 = 差（賣壓, 對 DataFrame 做技術分析，回傳評分與指標快照, 從 DB 載入近 N 筆收盤資料為 DataFrame, RSI 評分（趨勢追蹤）     - 50-70: 健康動量區間 → 高分     - 70-80: 強勢動量 → 仍然高分（不懲罰）     - >80: 極 (+7 more)

### Community 12 - "Community 12"
Cohesion: 0.18
Nodes (15): _adjusted_score(), _calc_metrics(), _calc_smc_trend(), _calc_technical_score(), _get_trading_dates(), _load_all_price_dfs(), optimize_weights(), 執行回測      Args:         start_date / end_date: 回測期間         buy_threshold: 技術分超過 (+7 more)

### Community 13 - "Community 13"
Cohesion: 0.21
Nodes (14): calculate_metrics(), _daily_returns(), _max_consecutive_losses(), _portfolio_summary(), Backtest V3 — Metrics Calculator  三層報表：   Level 1: Portfolio Summary（14 個指標）   L, 從 engine 的 raw result 計算完整 metrics。     回傳三層報表結構。, 從 equity curve 算 daily returns, Sharpe = mean(excess_return) / std(return) × √252 (+6 more)

### Community 14 - "Community 14"
Cohesion: 0.29
Nodes (9): _analyze_stock_from_db(), _compute_explosion_score(), _compute_scan_result(), 從 DataFrame 計算 ScanResult, 計算爆擊潛力分數 (0-100)      權重：       量比 30%  — 量比越高越異常       漲幅 20%  — 單日漲幅越大越好, scan_all(), scan_external_pool(), scan_tracked_stocks() (+1 more)

### Community 15 - "Community 15"
Cohesion: 0.24
Nodes (11): analyze_liquidity(), _calc_liq_score(), _cluster_swings(), detect_liquidity(), detect_sweeps(), _merge_close_clusters(), SMC v2 — 流動性偵測  EQH/EQL (ATR 自適應容差) + Sweep/Run 判定 + liq_score。, liq_score = touches * 0.4 + time_spread * 0.3 + dwell_ratio * 0.3      touches: (+3 more)

### Community 16 - "Community 16"
Cohesion: 0.22
Nodes (7): decode_token(), get_current_user(), get_optional_user(), 認證服務 — JWT token + 密碼雜湊, 解析 JWT，回傳 payload。失敗拋 JWTError。, 必須登入的 endpoint 用這個 dependency, 可選登入的 endpoint 用這個 dependency（回測、筆記等記錄 created_by）

### Community 17 - "Community 17"
Cohesion: 0.32
Nodes (7): assign_group(), assign_groups_batch(), compute_atr_pct(), Stock Grouper — 依 ATR 波動度 + 市場自動分群  Groups:   US_高波動, US_穩定大型, US_低波動, TW_權值, TW, 批次分群。回測時傳 anchor_date = start_date，只用 anchor_date 前的資料。      Args:         stock, 計算 ATR%（ATR / Close * 100），取最近 period 天平均, 分配股票到群組。      Args:         ticker: 股票代碼         market: "US" | "TW"         atr

### Community 18 - "Community 18"
Cohesion: 0.43
Nodes (7): notify_backtest_done(), notify_daily_report(), notify_portfolio_alert(), 每日分析完成 → 推播 Top Picks, _score_emoji(), _send(), send_test()

### Community 19 - "Community 19"
Cohesion: 0.47
Nodes (5): backfill_ai_note_results(), _calculate_return_pct(), _get_latest_stock_price(), AI Analysis Notes 結果回填服務 負責定期檢查待評估的 AI 分析筆記，並根據當前市場價格更新交易結果。  邏輯： 1. 找出所有 outcom, 回填所有待評估的 AI 分析筆記結果。      Returns:         {"updated": int, "expired": int, "hit_

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (0): 

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): 回傳 OHLCV DataFrame, index=date, max(date) <= current_date

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): current_date 的 close price

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): convenience: RSI, MACD, MA, ATR, BB, Volume — 用 get_ohlcv() 算

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): {"score": 72, "label": "正面", "article_count": 5}

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): {"vix": 18.5, "spy_trend": "uptrend", "regime": "trending"}

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): 停牌 / 資料不足 / 流動性太差 → False

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): 前進一天，回傳新日期。超出 end_date → None

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): 當前風險金額：用於 portfolio risk cap

## Knowledge Gaps
- **107 isolated node(s):** `從 DB 載入近 N 筆收盤資料為 DataFrame`, `RSI 評分（趨勢追蹤）     - 50-70: 健康動量區間 → 高分     - 70-80: 強勢動量 → 仍然高分（不懲罰）     - >80: 極`, `MACD 評分（趨勢追蹤）     - 金叉 + 柱體放大 → 最高分     - 金叉 + 柱體縮小 → 動量減弱但方向仍對     - 死叉 → 低分`, `均線排列評分（本來就是趨勢邏輯，保持原設計）`, `布林通道評分（趨勢追蹤版）     - 突破上軌 = 強勢動能，高分     - 中軌以上 = 健康趨勢     - 跌破下軌 = 弱勢` (+102 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 20`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `回傳 OHLCV DataFrame, index=date, max(date) <= current_date`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `current_date 的 close price`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `convenience: RSI, MACD, MA, ATR, BB, Volume — 用 get_ohlcv() 算`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `{"score": 72, "label": "正面", "article_count": 5}`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `{"vix": 18.5, "spy_trend": "uptrend", "regime": "trending"}`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `停牌 / 資料不足 / 流動性太差 → False`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `前進一天，回傳新日期。超出 end_date → None`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `當前風險金額：用於 portfolio risk cap`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SmcConfig` connect `SMC 分析引擎` to `VectorBT 回測層`, `數據抓取層`, `TWSE 台股數據`, `Community 15`?**
  _High betweenness centrality (0.181) - this node is a cross-community bridge._
- **Why does `DataProvider` connect `VectorBT 回測層` to `Community 10`, `BacktestV1 舊版`, `BacktestV3 策略架構`, `AI 分析筆記`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Why does `SMCStrategy` connect `VectorBT 回測層` to `SMC 分析引擎`, `BacktestV3 策略架構`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Are the 55 inferred relationships involving `SmcConfig` (e.g. with `Position` and `回測引擎 v2 — SMC 分層決策回測  核心規則：   - T 日計算 SMC + EntryPlan，T+1 才能成交（防止前瞻偏差）   - 三種成交模`) actually correct?**
  _`SmcConfig` has 55 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `DataProvider` (e.g. with `BacktestEngine` and `Backtest V3 — Core Engine  每日循環：   1. advance_day()   2. 更新持倉 mark-to-market（clo`) actually correct?**
  _`DataProvider` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `Signal` (e.g. with `BacktestEngine` and `Backtest V3 — Core Engine  每日循環：   1. advance_day()   2. 更新持倉 mark-to-market（clo`) actually correct?**
  _`Signal` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `HistoricalProvider` (e.g. with `VbtBacktestResult` and `VectorBT 整合 — 策略回測 Service  架構：   1. STRATEGY_REGISTRY — 所有可用策略的 class map   2.`) actually correct?**
  _`HistoricalProvider` has 14 INFERRED edges - model-reasoned connections that need verification._