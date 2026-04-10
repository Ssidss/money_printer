# 回測引擎 v2 — 軟體設計圖

> 版本：v2.0 | 2026-04-08
> 配套文件：`BACKTEST_V2_DESIGN.md`（策略邏輯與規則）
> v2.0 變更：修正 10 項 production 風險（JSONB 拆表、cache 完整性、分群穩定性等）

---

## 一、系統全景圖

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Money Printer                               │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │   Frontend    │    │   Backend    │    │     PostgreSQL        │  │
│  │   (Next.js)   │◄──►│  (FastAPI)   │◄──►│                       │  │
│  │              │    │              │    │  stocks                │  │
│  │  /strategies  │    │  /api/v2/    │    │  price_history        │  │
│  │  /backtest    │    │  backtest/   │    │  analysis_results     │  │
│  │  /compare     │    │  strategies/ │    │  strategy_profiles ★  │  │
│  │              │    │              │    │  backtest_results_v2 ★ │  │
│  │              │    │              │    │  backtest_trades ★     │  │
│  │              │    │              │    │  backtest_equity ★     │  │
│  └──────────────┘    └──────┬───────┘    │  strategy_signals ★   │  │
│                             │            │  news_articles        │  │
│                             │            │  portfolio_holdings   │  │
│                             ▼            │  portfolio_txns       │  │
│                    ┌────────────────┐    │  ai_analysis_notes    │  │
│                    │  Backtest V2   │    └───────────────────────┘  │
│                    │    Engine      │                                │
│                    │               │    ★ = 新增 Table               │
│                    │  SMC v2 ──────┤                                │
│                    │  Decision ────┤                                │
│                    │  Cost Model ──┤                                │
│                    │  Fill Model ──┤                                │
│                    └────────────────┘                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、新增 DB Tables

### 2.1 strategy_profiles — 策略檔案

```sql
CREATE TABLE strategy_profiles (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,          -- "v2-穩健版"
    description   TEXT,                           -- 使用者備註
    
    -- 策略參數 (JSONB)
    params        JSONB NOT NULL DEFAULT '{}',    -- 全域參數
    overrides     JSONB NOT NULL DEFAULT '{}',    -- 群組覆蓋參數
    stock_settings JSONB NOT NULL DEFAULT '{}',   -- 個股開關
    
    -- 狀態
    is_active     BOOLEAN NOT NULL DEFAULT FALSE, -- 當前啟用（只能有一個 active）
    
    -- 回測摘要（最近一次回測的結果，快速查看用）
    latest_backtest_id  INTEGER REFERENCES backtest_results_v2(id),
    
    -- 時間戳
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 同時只能有一個 is_active = true
CREATE UNIQUE INDEX idx_strategy_active ON strategy_profiles (is_active) WHERE is_active = TRUE;
```

**params JSONB 結構：**

```jsonc
{
  // ── 回測設定 ──
  "backtest_mode": "smc_only",     // smc_only | smc_neutral | smc_full
  "fill_model": "limit",           // limit | conservative | close
  "cost_model": true,

  // ── 進場規則 ──
  "min_rr": 2.0,                   // 最低 R:R
  "min_conditions": 2,             // 最少條件數
  "entry_tolerance_atr": 0.5,      // 進場容許偏離（ATR 倍數）
  
  // ── 出場規則 ──
  "stop_mode": "smc_structure",    // smc_structure | fixed_pct | atr_multiple
  "fixed_stop_pct": 0.07,          // stop_mode=fixed_pct 時使用
  "atr_buffer": 0.15,              // SMC 停損 ATR buffer
  "target_mode": "smc_target",     // smc_target | fixed_pct | trailing
  "exit_on_reversal": "mss_all",   // mss_all | choch_half_mss_all | off
  "breakeven_mode": "structure",   // structure | simple_1r | off
  
  // ── 倉位與風控 ──
  "position_mode": "v2_dynamic",   // v2_dynamic | fixed_pct
  "fixed_position_pct": 0.10,      // position_mode=fixed_pct 時使用
  "risk_per_trade": 0.02,          // 單筆風險上限
  "max_heat": 0.10,                // portfolio 總風險上限
  "max_positions": 8,
  "us_exposure_limit": 0.70,       // 美股曝險上限
  "tw_exposure_limit": 0.50,       // 台股曝險上限
  "use_sentiment": false,          // 情緒影響開關
  "use_mtf": true,                 // MTF 過濾開關

  // ── SMC 引擎（進階，通常不動） ──
  "smc_config": {
    "ob_score_threshold": 4.0,
    "ob_entry_min_score": 3.0,
    "fvg_grade_a_atr": 1.5,
    "swing_n_daily": 3,
    "swing_n_weekly": 5,
    "trend_swing_groups": 4
  }
}
```

**overrides JSONB 結構：**

```jsonc
{
  "TW_權值": {
    "atr_buffer": 0.20,
    "min_rr": 2.5
  },
  "US_高波動": {
    "atr_buffer": 0.20
  }
}
```

**stock_settings JSONB 結構：**

```jsonc
{
  "GME":  { "enabled": false, "reason": "迷因股，不適合 SMC" },
  "0050": { "enabled": false, "reason": "ETF 定期定額" }
}
```

### 2.2 backtest_results_v2 — 回測結果（主表，只存摘要）

> **設計原則：trades 和 equity_curve 拆成獨立 table，不用 JSONB。**
> 100 股 × 2 年回測可能產生 500+ trades 和 500+ equity points。
> JSONB 存這些會導致單 row 5-50MB，查詢慢、index 失效、I/O 爆。

```sql
CREATE TABLE backtest_results_v2 (
    id             SERIAL PRIMARY KEY,
    profile_id     INTEGER NOT NULL REFERENCES strategy_profiles(id) ON DELETE CASCADE,
    name           VARCHAR(100),
    
    -- 回測區間
    start_date     DATE NOT NULL,
    end_date       DATE NOT NULL,
    initial_capital NUMERIC(14,2) NOT NULL DEFAULT 1000000,
    market_filter  VARCHAR(10) DEFAULT 'ALL',   -- US | TW | ALL
    
    -- 可重現性鎖（Reproducibility Lock）
    params_snapshot JSONB NOT NULL,              -- 跑的當下的完整參數
    strategy_hash   VARCHAR(64) NOT NULL,        -- params + smc_config 的 hash
    run_hash        VARCHAR(64) NOT NULL,        -- 完整 hash（見下方說明）
    stock_universe  JSONB NOT NULL DEFAULT '[]', -- 參與回測的 ticker 列表
    data_hash       VARCHAR(64),                 -- price_history 的 checksum
    
    -- 績效指標（JSONB OK — 固定大小，~2KB）
    metrics        JSONB NOT NULL DEFAULT '{}',
    
    -- 診斷報告（JSONB OK — 固定大小，~5KB）
    diagnosis      JSONB,
    
    -- 元數據
    duration_secs  NUMERIC(10,1),
    stock_count    INTEGER,
    trading_days   INTEGER,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_bt2_profile ON backtest_results_v2 (profile_id);
CREATE INDEX idx_bt2_run_hash ON backtest_results_v2 (run_hash);
```

**run_hash 計算（完整快取 key）：**

```python
run_hash = sha256(
    strategy_hash       # params + smc_config
    + sorted(stock_universe)  # 參與的股票列表
    + start_date + end_date   # 回測區間
    + data_hash               # 價格資料版本
    + fill_model              # 成交模型
    + cost_model              # 成本模型開關
).hexdigest()

# 用途：
# 1. 同一個 run_hash → 結果完全一樣 → 不需要重跑
# 2. 任何一個因素變了 → hash 不同 → 需要重跑
# 3. L2 cache 也用這個 key
```

**data_hash 計算：**

```python
data_hash = sha256(
    # 每支股票的最新 price_history 日期 + 總筆數
    # 補了資料或修正了資料 → hash 變 → 舊回測結果標記為 stale
    ",".join(f"{ticker}:{latest_date}:{count}" for ticker in sorted(universe))
).hexdigest()[:16]
```

### 2.3 backtest_trades — 回測交易明細（拆表）

```sql
CREATE TABLE backtest_trades (
    id              SERIAL PRIMARY KEY,
    backtest_id     INTEGER NOT NULL REFERENCES backtest_results_v2(id) ON DELETE CASCADE,
    
    -- 股票
    ticker          VARCHAR(20) NOT NULL,
    market          VARCHAR(10) NOT NULL,
    stock_group     VARCHAR(40),                 -- "US_高波動" / "TW_權值" 等
    
    -- 進場
    signal_date     DATE NOT NULL,               -- T 日（信號生成）
    fill_date       DATE NOT NULL,               -- T+1 日（實際成交）
    fill_price      NUMERIC(14,4) NOT NULL,
    entry_source    VARCHAR(40),                 -- "OB(7.6)" / "FVG(B)" / "SwingLow"
    position_tier   VARCHAR(20),                 -- 核心 / 標準 / 探索
    conditions_met  SMALLINT,
    position_size_pct NUMERIC(6,2),
    
    -- 出場
    exit_date       DATE,
    exit_price      NUMERIC(14,4),
    exit_reason     VARCHAR(30),                 -- 停損 / 停利 / 結構反轉 / 強制平倉
    stop_source     VARCHAR(40),
    target_source   VARCHAR(40),
    
    -- 損益
    planned_rr      NUMERIC(8,2),
    actual_rr       NUMERIC(8,2),
    pnl_pct         NUMERIC(8,4),
    pnl_amount      NUMERIC(14,2),
    trade_cost      NUMERIC(14,2),
    net_pnl         NUMERIC(14,2),
    holding_days    INTEGER,
    
    -- MAE / MFE
    mae_pct         NUMERIC(8,4),                -- 最大不利偏移
    mfe_pct         NUMERIC(8,4),                -- 最大有利偏移
    
    -- 上下文
    smc_trend_at_entry VARCHAR(30),
    smc_trend_at_exit  VARCHAR(30)
);

CREATE INDEX idx_bt_trades_backtest ON backtest_trades (backtest_id);
CREATE INDEX idx_bt_trades_ticker ON backtest_trades (ticker);
CREATE INDEX idx_bt_trades_exit_reason ON backtest_trades (backtest_id, exit_reason);
```

### 2.4 backtest_equity — 權益曲線（拆表）

```sql
CREATE TABLE backtest_equity (
    id              SERIAL PRIMARY KEY,
    backtest_id     INTEGER NOT NULL REFERENCES backtest_results_v2(id) ON DELETE CASCADE,
    
    trade_date      DATE NOT NULL,
    equity          NUMERIC(14,2) NOT NULL,
    drawdown_pct    NUMERIC(8,4),
    cash            NUMERIC(14,2),
    positions_value NUMERIC(14,2),
    open_positions  SMALLINT
);

CREATE INDEX idx_bt_equity_backtest ON backtest_equity (backtest_id, trade_date);
```

### 2.5 strategy_signals — 實戰信號追蹤

> **資料量控制**：只記「有動作」的信號（買入/出場/等回調），
> 不記每天每股的「不操作」，否則 200 股 × 365 天 = 73,000 rows/年。
> 加 TTL：超過 1 年的 followed=NULL 記錄自動歸檔。

```sql
CREATE TABLE strategy_signals (
    id              SERIAL PRIMARY KEY,
    profile_id      INTEGER NOT NULL REFERENCES strategy_profiles(id) ON DELETE CASCADE,
    stock_id        INTEGER NOT NULL REFERENCES stocks(id),
    
    -- 策略信號（只記有動作的）
    signal_date     DATE NOT NULL,
    signal_action   VARCHAR(20) NOT NULL,         -- 買入 | 等回調 | 出場
    signal_entry    NUMERIC(14,4),
    signal_stop     NUMERIC(14,4),
    signal_target   NUMERIC(14,4),
    signal_rr       NUMERIC(6,2),
    signal_tier     VARCHAR(20),
    signal_conditions SMALLINT,
    
    -- 使用者操作
    followed        BOOLEAN,                     -- NULL=尚未決定, true=跟了, false=跳過
    actual_entry    NUMERIC(14,4),
    actual_exit     NUMERIC(14,4),
    actual_pnl_pct  NUMERIC(8,4),
    
    -- 事後追蹤（系統自動填）
    outcome_if_followed NUMERIC(8,4),            -- 如果跟了會怎樣
    
    skip_reason     TEXT,
    notes           TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 防重複
    UNIQUE (profile_id, stock_id, signal_date)
);

CREATE INDEX idx_signals_profile_date ON strategy_signals (profile_id, signal_date);
CREATE INDEX idx_signals_followed ON strategy_signals (profile_id, followed) WHERE followed IS NULL;
```

**歸檔策略：**

```sql
-- 每月排程：把 1 年前的 NULL followed 記錄搬到歸檔表
INSERT INTO strategy_signals_archive SELECT * FROM strategy_signals
WHERE followed IS NULL AND created_at < NOW() - INTERVAL '1 year';

DELETE FROM strategy_signals
WHERE followed IS NULL AND created_at < NOW() - INTERVAL '1 year';
```

---

## 三、Entity Relationship

```
strategy_profiles
  │
  ├── 1:N ── backtest_results_v2    (一個 profile 可跑多次回測)
  │             ├── 1:N ── backtest_trades   (回測交易明細，獨立表)
  │             └── 1:N ── backtest_equity   (權益曲線，獨立表)
  │
  ├── 1:N ── strategy_signals       (實戰信號追蹤)
  │             └── → stocks
  │
  └── 1:1 ── is_active              (當前啟用的策略)

stocks
  ├── 1:N ── price_history
  ├── 1:N ── analysis_results       (含 smc_data, entry_plan JSONB)
  ├── 1:N ── news_articles
  ├── 1:N ── portfolio_holdings
  ├── 1:N ── portfolio_transactions
  ├── 1:N ── ai_analysis_notes
  └── 1:N ── strategy_signals
```

---

## 四、後端模組架構

```
backend/app/
├── models/
│   ├── stock.py              (現有：Stock, PriceHistory)
│   ├── analysis.py           (現有：AnalysisResult, NewsArticle)
│   ├── portfolio.py          (現有：PortfolioHolding, PortfolioTransaction)
│   ├── backtest.py           (現有：BacktestResult — v1，保留)
│   ├── ai_note.py            (現有：AiAnalysisNote)
│   └── strategy.py           ★ 新增：StrategyProfile, BacktestResultV2, BacktestTrade, BacktestEquity, StrategySignal
│
├── schemas/
│   ├── decision.py           (現有：EntryPlan, SentimentGate, MtfGate)
│   └── strategy.py           ★ 新增：請求/回應 schema
│
├── routers/
│   ├── backtest.py           (現有：v1 回測 API，保留)
│   ├── backtest_v2.py        ★ 新增：v2 回測 API
│   └── strategies.py         ★ 新增：策略檔案 CRUD + 實戰追蹤
│
├── services/
│   ├── backtester.py         (現有：v1 回測引擎，保留)
│   ├── backtester_v2.py      ★ 新增：v2 回測引擎
│   ├── strategy_tracker.py   ★ 新增：實戰信號追蹤
│   ├── stock_grouper.py      ★ 新增：自動分群
│   ├── diagnosis.py          ★ 新增：診斷報告生成
│   │
│   ├── smc/                  (現有：v2 SMC 引擎)
│   │   ├── __init__.py       run_smc_analysis_v2()
│   │   ├── config.py         SmcConfig（含 strategy_hash）
│   │   ├── structure.py
│   │   ├── order_block.py
│   │   ├── fvg.py
│   │   ├── liquidity.py
│   │   ├── fibonacci.py
│   │   └── regime.py
│   │
│   ├── decision/             (現有：決策引擎)
│   │   ├── entry.py          generate_entry_plan()
│   │   ├── position_sizer.py
│   │   ├── sentiment_gate.py
│   │   └── mtf_gate.py
│   │
│   └── smc_worker.py         (現有：SMC 批次分析)
│
└── main.py                   (註冊新 router)
```

### 4.1 stock_grouper.py 穩定性規則

> **問題**：分群用 ATR 波動率，而 ATR 本身每天變動，若回測途中股票跳群組，
> 同一支股票前半段用 A 參數、後半段用 B 參數，結果不可重現。

**規則：**
1. **回測時**：groups 在 `start_date` 固定一次，整段回測期間不變
2. **實戰時**：groups 每月底更新一次（配合月線 SMC 更新）
3. **邊界處理**：ATR 跨界 ±10% 不跳群（hysteresis），避免頻繁切換
4. **記錄**：回測結果的 `stock_universe` JSONB 含每支股票的分群，可稽核

```python
class StockGrouper:
    def assign_groups(self, stocks, price_data, anchor_date: date) -> dict[str, str]:
        """以 anchor_date 的 ATR 為準分群，回測期間固定不變"""
        ...
    
    def should_regroup(self, current_group, new_atr, thresholds) -> bool:
        """hysteresis: ATR 需超過閾值 ±10% 才跳群"""
        ...
```

### 4.2 非同步任務架構

> **問題**：100 股 × 2 年回測可能跑 2-10 分鐘，不能在 HTTP request 內等完。

**Phase 1（簡單版）：FastAPI BackgroundTask**
- 適用單 user、單回測場景
- 透過 SSE 回報進度
- 缺點：重啟 server 就中斷、無 retry

**Phase 4+（生產版）：arq + Redis**
```
┌──────────┐     ┌───────────┐     ┌──────────────┐
│  FastAPI  │────►│  Redis Q  │────►│  arq Worker  │
│  POST run │     │  (enqueue)│     │  backtester  │
└──────────┘     └───────────┘     └──────┬───────┘
                                          │
                                          ▼
                                   backtest_results_v2
```
- 好處：可重啟、可 retry、可水平擴展 worker
- 進度回報：worker 寫 Redis key，前端 polling 或 SSE 讀
- 不需要 Celery（太重），arq 是 async-native、輕量

### 新增檔案清單（7 個 + 未來 1 個）

| 檔案 | 用途 | 大小預估 |
|------|------|---------|
| `models/strategy.py` | 3 個新 Model | ~120 行 |
| `schemas/strategy.py` | Request/Response Schema | ~100 行 |
| `routers/strategies.py` | 策略檔案 CRUD API | ~150 行 |
| `routers/backtest_v2.py` | v2 回測 API | ~80 行 |
| `services/backtester_v2.py` | v2 回測引擎（核心） | ~500 行 |
| `services/stock_grouper.py` | 自動分群邏輯（含穩定性） | ~120 行 |
| `services/diagnosis.py` | 診斷報告生成 | ~150 行 |
| `workers/backtest_worker.py` | arq worker（Phase 4+） | ~60 行 |

---

## 五、API 設計

### 5.1 策略檔案 API

```
POST   /api/v2/strategies                     建立策略檔案
GET    /api/v2/strategies                     列出所有策略檔案
GET    /api/v2/strategies/:id                 取得單一策略（含最近回測摘要）
PUT    /api/v2/strategies/:id                 更新策略參數
DELETE /api/v2/strategies/:id                 刪除策略檔案
POST   /api/v2/strategies/:id/activate        設為啟用（其他自動停用）
POST   /api/v2/strategies/:id/clone           複製策略（用於 A/B 測試）
```

### 5.2 回測 API

```
POST   /api/v2/backtest/run                   執行回測
  Body: { profile_id, start_date, end_date, initial_capital, market }
  → 背景執行，透過 SSE 回報進度
  → 完成後寫入 backtest_results_v2

GET    /api/v2/backtest/status                回測進度
GET    /api/v2/backtest/results               列出回測結果（分頁 limit/offset）
GET    /api/v2/backtest/results/:id           單次回測詳情
GET    /api/v2/backtest/results/:id/trades    交易明細（分頁 limit/offset，預設 50 筆）
GET    /api/v2/backtest/compare?a=1&b=2       兩次回測對比
```

### 5.3 實戰追蹤 API

```
GET    /api/v2/strategies/:id/signals         取得策略信號歷史
POST   /api/v2/strategies/:id/signals/:sid/follow   標記「有跟」
POST   /api/v2/strategies/:id/signals/:sid/skip     標記「沒跟」+ 原因
GET    /api/v2/strategies/:id/performance     實戰績效統計
```

---

## 六、前端頁面架構

```
frontend/src/app/
├── strategies/                    ★ 新增
│   ├── page.tsx                   策略檔案列表
│   ├── [id]/
│   │   └── page.tsx               單一策略詳情（參數 + 回測 + 實戰）
│   └── compare/
│       └── page.tsx               策略對比頁
│
├── backtest/
│   └── page.tsx                   回測頁（改版：選策略 → 跑回測 → 看結果）
│
└── (現有頁面不動)

frontend/src/components/
├── strategy/                      ★ 新增
│   ├── ProfileCard.tsx            策略卡片（名稱 + 回測摘要 + 啟用狀態）
│   ├── ParamsEditor.tsx           參數編輯器（含依賴關係 UI）
│   ├── OverridesEditor.tsx        群組覆蓋編輯器
│   ├── BacktestChart.tsx          權益曲線圖表
│   ├── TradeTable.tsx             交易明細表（虛擬滾動 + 分頁，見 6.1）
│   ├── DiagnosisCard.tsx          診斷報告卡片
│   ├── CompareView.tsx            對比檢視
│   └── LiveTracker.tsx            實戰信號追蹤
│
└── backtest/
    └── BacktestForm.tsx           改版：選策略 profile → 設定回測區間 → 執行
```

### 6.1 前端效能對策

> **問題**：100 股 × 2 年回測可能產生 500+ trades，一次全渲染會卡。

| 元件 | 策略 | 工具 |
|------|------|------|
| TradeTable | 伺服器端分頁（limit/offset），前端只載 50 筆 | API 分頁參數 |
| TradeTable 展開列 | 點擊展開才載 MAE/MFE 詳情 | lazy load |
| 權益曲線 | 每日一點，500 天 OK，超過 1000 天做 downsampling | Chart.js decimation |
| 策略對比 | equity_curves 只取 sampling points（每週一點） | API 端 downsample |

Phase 1 用 API 分頁即可；Phase 4+ 若需要前端即時篩選 500+ 筆，加 `@tanstack/react-virtual` 虛擬滾動。

---

## 七、核心流程圖

### 7.1 回測執行流程

```
使用者點「執行回測」
        │
        ▼
┌─ POST /api/v2/backtest/run ─────────────────────────┐
│  { profile_id: 3, start: "2024-01-01", end: "2026-04-01" }  │
└──────────────┬──────────────────────────────────────┘
               │
               ▼
   ┌── BackgroundTask ──────────────────────────────┐
   │                                                 │
   │  1. 從 DB 讀取 StrategyProfile.params           │
   │     └── 合併 overrides（按群組）                  │
   │     └── 過濾 stock_settings（排除停用的）          │
   │                                                 │
   │  2. 載入所有股票的 price_history                  │
   │     └── 自動分群（stock_grouper, anchor=start)    │
   │     └── 分群固定不變（見 §4.1 穩定性規則）           │
   │                                                 │
   │  3. 預計算 SMC（滾動窗口，可分段/平行，見 §九）      │
   │     ┌─────────────────────────────────┐         │
   │     │ for each trading_day T:         │         │
   │     │   for each stock:               │         │
   │     │     日線 SMC ← bars[:T]         │         │
   │     │     週線 SMC ← 每週五更新       │          │
   │     │     月線 SMC ← 每月底更新       │          │
   │     │     EntryPlan ← decision engine │         │
   │     │     cache[(ticker,T)] = result  │         │
   │     └─────────────────────────────────┘         │
   │          │                                      │
   │          ▼ SSE: "預計算進度 45%"                  │
   │                                                 │
   │  4. 回測主迴圈                                   │
   │     ┌─────────────────────────────────┐         │
   │     │ for each trading_day T+1:       │         │
   │     │                                 │         │
   │     │   Phase A: 持倉管理             │          │
   │     │     for each position:          │         │
   │     │       check_exit(pos, T+1_OHLC) │         │
   │     │       update MAE/MFE            │         │
   │     │                                 │         │
   │     │   Phase B: 新倉進場             │          │
   │     │     signals = cache[(*, T)]     │         │
   │     │     for each signal:            │         │
   │     │       try_fill(signal, T+1_OHLC)│         │
   │     │       apply cost_model          │         │
   │     │       check position limits     │         │
   │     │                                 │         │
   │     │   Phase C: 記錄                 │          │
   │     │     equity_curve.append(...)    │         │
   │     └─────────────────────────────────┘         │
   │          │                                      │
   │          ▼ SSE: "回測進度 78%"                    │
   │                                                 │
   │  5. 計算績效指標                                  │
   │     └── metrics, by_exit, by_tier, by_group     │
   │                                                 │
   │  6. 生成診斷報告                                  │
   │     └── diagnosis.generate(trades, metrics)     │
   │                                                 │
   │  7. 寫入 DB（拆表）                                │
   │     └── backtest_results_v2（摘要 + metrics）     │
   │     └── backtest_trades（交易明細，批次 INSERT）    │
   │     └── backtest_equity（權益曲線，批次 INSERT）    │
   │     └── 更新 profile.latest_backtest_id          │
   │                                                 │
   │          ▼ SSE: "回測完成"                        │
   └─────────────────────────────────────────────────┘
```

### 7.2 實戰追蹤流程

```
每日收盤後（手動或排程觸發）
        │
        ▼
┌─ strategy_tracker.py ──────────────────────────────┐
│                                                     │
│  1. 讀取 active StrategyProfile                     │
│                                                     │
│  2. 對每支啟用的股票跑 SMC v2 + EntryPlan            │
│     （這步已經由 smc_worker 做了，直接讀 DB）          │
│                                                     │
│  3. 對每個有信號的股票：                               │
│     └── 寫入 strategy_signals（signal_date, action 等）│
│                                                     │
│  4. 對已有持倉的股票：                                │
│     └── 檢查是否觸發出場信號                          │
│     └── 計算 outcome_if_followed（如果跟了會怎樣）     │
│                                                     │
│  5. 使用者在前端：                                    │
│     └── 看到今天的信號列表                            │
│     └── 點「跟了」或「跳過」                           │
│     └── 填實際成交價                                 │
└─────────────────────────────────────────────────────┘
```

### 7.3 策略對比流程

```
使用者選兩個回測結果進行對比
        │
        ▼
┌─ GET /api/v2/backtest/compare?a=1&b=2 ────────────┐
│                                                     │
│  回傳：                                              │
│  {                                                  │
│    "profile_a": { name, params_diff },              │
│    "profile_b": { name, params_diff },              │
│    "params_diff": [                                 │
│      { key: "atr_buffer", a: 0.15, b: 0.20 },      │
│      { key: "min_rr", a: 2.0, b: 2.5 },            │
│    ],                                               │
│    "metrics_comparison": {                           │
│      "total_return":  { a: 38.5, b: 31.2 },        │
│      "max_drawdown":  { a: -11.2, b: -8.5 },       │
│      "sharpe":        { a: 1.45, b: 1.62 },        │
│      "win_rate":      { a: 54.3, b: 51.1 },        │
│    },                                               │
│    "equity_curves": { a: [...], b: [...] },         │
│    "trade_overlap": {                               │
│      "both_won": 28,                                │
│      "a_won_b_lost": 12,                            │
│      "a_lost_b_won": 8,                             │
│      "both_lost": 15,                               │
│    }                                                │
│  }                                                  │
└─────────────────────────────────────────────────────┘
```

---

## 八、資料流向圖

```
                    ┌──────────────┐
                    │ price_history │
                    │ (OHLCV 日線)  │
                    └──────┬───────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ SMC 日線  │    │ SMC 週線  │    │ SMC 月線  │
    │ structure │    │ structure │    │ structure │
    │ OB / FVG  │    │ trend     │    │ trend     │
    │ liquidity │    └─────┬────┘    └─────┬────┘
    │ fibonacci │          │               │
    └─────┬────┘          │               │
          │               │               │
          ▼               ▼               ▼
    ┌─────────────────────────────────────────┐
    │           Decision Engine                │
    │                                         │
    │  entry.py:  entry/stop/target + R:R     │
    │  mtf_gate:  月週日 → 倉位上限            │
    │  sentiment: 情緒 → 升降級               │ ◄── news_articles (可選)
    │  position:  條件數 → tier + %           │
    │                                         │
    │  Output: EntryPlan                      │
    └────────────────┬────────────────────────┘
                     │
        ┌────────────┼────────────────┐
        │            │                │
        ▼            ▼                ▼
  ┌──────────┐ ┌──────────┐   ┌───────────┐
  │ 回測引擎  │ │ 前端顯示  │   │ 實戰追蹤   │
  │          │ │ 個股頁    │   │           │
  │ T日信號   │ │ Dashboard │   │ 每日信號   │
  │ T+1成交   │ │ 簡報頁    │   │ 跟/不跟    │
  │ 績效統計   │ │          │   │ 損益追蹤   │
  └────┬─────┘ └──────────┘   └─────┬─────┘
       │                            │
       ▼                            ▼
  backtest_results_v2         strategy_signals
  backtest_trades
  backtest_equity
```

---

## 九、分段與平行計算

> **問題**：100 股 × 500 天 × 3 timeframes = 150,000 次 SMC 計算。
> 全部串行跑可能 5-10 分鐘，需要拆分加速。

### 9.1 SMC 預計算分段（Chunking）

```
Phase 1（單 process、分段回報進度）:

  stocks = [AAPL, NVDA, AMD, ...]  # 100 支
  chunks = split(stocks, chunk_size=10)  # 10 支一段

  for i, chunk in enumerate(chunks):
      for stock in chunk:
          for day in trading_days:
              compute_smc(stock, day, daily)
              if is_friday(day): compute_smc(stock, day, weekly)
              if is_month_end(day): compute_smc(stock, day, monthly)
      
      yield SSE(progress=i/len(chunks)*100)  # 每段回報進度
```

### 9.2 平行計算（Phase 4+）

```
Phase 4+（多 process / asyncio.gather）:

  ┌───────────────────────────────────────────┐
  │  SMC 預計算（股票間獨立 → 可平行）            │
  │                                            │
  │  Worker 1: AAPL ~ AMD (10 stocks)          │
  │  Worker 2: ARM ~ COST (10 stocks)          │
  │  Worker 3: GOOG ~ META (10 stocks)         │
  │  ...                                       │
  │                                            │
  │  注意：回測主迴圈 Phase B（新倉進場）           │
  │  涉及 portfolio 狀態 → 必須單線程串行          │
  │  只有 SMC 計算和預填 cache 可以平行            │
  └───────────────────────────────────────────┘

  Phase 1 最佳化：
  · 先跑 SMC 預計算（可平行） → 全部存 L1 cache
  · 再跑回測主迴圈（必須串行） → 直接查 L1

  效果：主迴圈從「邊算 SMC 邊跑」變成「只查 cache 跑」
  預估加速：3-5x（SMC 佔總時間 70-80%）
```

---

## 十、SMC 快取架構

```
┌─────────────────────────────────────────────────────────┐
│                    SMC 快取層                             │
│                                                         │
│  L1: 記憶體 Dict（單次回測內）                              │
│  ┌─────────────────────────────────────────────┐        │
│  │  key = (ticker, date, timeframe)             │        │
│  │  value = SmcResult                           │        │
│  │  lifetime = 回測結束即釋放                      │        │
│  └─────────────────────────────────────────────┘        │
│                                                         │
│  L2: 磁碟 Pickle（跨回測重用）                             │
│  ┌─────────────────────────────────────────────┐        │
│  │  path = .cache/smc/{strategy_hash}/           │       │
│  │         {ticker}_{date}_{timeframe}.pkl       │       │
│  │                                               │       │
│  │  失效條件：                                    │       │
│  │  · strategy_hash 不同 → miss（參數變了）        │       │
│  │  · data_version 不同 → miss（補了新價格資料）    │       │
│  │  · 檔案超過 30 天 → 自動清理                    │       │
│  └─────────────────────────────────────────────┘        │
│                                                         │
│  L3: Redis（未來擴展 — 分散式快取）                          │
│  ┌─────────────────────────────────────────────┐        │
│  │  用途：多 worker / 多 process 共享 SMC 結果    │        │
│  │  key = smc:{strategy_hash}:{ticker}:{date}:{tf}       │
│  │  value = MessagePack 序列化的 SmcResult       │        │
│  │  TTL = 7 days（跟回測區間無關）                │        │
│  │                                               │       │
│  │  Phase 1 不需要 → 單 process 用 L1+L2 足夠     │       │
│  │  Phase 4+ 引入 arq worker 後才值得加            │       │
│  └─────────────────────────────────────────────┘        │
│                                                         │
│  cache hit 流程：                                        │
│  request(ticker, date, tf)                               │
│    → check L1 → hit? return                              │
│    → check L2 → hit? load to L1, return                  │
│    → (L3 Redis if available) → hit? load to L1, return   │
│    → miss → compute SMC → store L1 + L2 (+ L3), return   │
│                                                         │
│  cache key 完整性（run_hash 一致性）：                      │
│  · L2 目錄以 strategy_hash 分隔，不同參數不會互用           │
│  · data_hash 變更 → 清除該 ticker 的 L2 快取              │
│  · run_hash 是結果級 key，快取是計算級 key，兩者獨立        │
└─────────────────────────────────────────────────────────┘
```

---

## 十一、前端頁面 Wireframe

### 11.1 /strategies — 策略列表頁

```
┌────────────────────────────────────────────────────────┐
│  策略管理                              [+ 建立新策略]    │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ┌─ 策略卡片 ────────────────────────────────────┐     │
│  │  v2-穩健版                          ⭐ 啟用中   │     │
│  │  R:R≥2.0 · 條件≥2 · 動態倉位 · SMC停損          │     │
│  │                                                │     │
│  │  最近回測 (2024-01 ~ 2026-04)                   │     │
│  │  +38.5%  回撤-11.2%  Sharpe 1.45  勝率 54%     │     │
│  │                                                │     │
│  │  實戰 (啟用 12 天)                               │     │
│  │  信號 8 次 · 跟了 6 次 · 實戰 +5.2%              │     │
│  │                                                │     │
│  │  [編輯] [回測] [複製] [對比]                      │     │
│  └────────────────────────────────────────────────┘     │
│                                                        │
│  ┌─ 策略卡片 ────────────────────────────────────┐     │
│  │  v2-積極版                                     │     │
│  │  R:R≥1.5 · 條件≥2 · ATR buffer 0.12           │     │
│  │  ...                                           │     │
│  └────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────┘
```

### 11.2 /strategies/:id — 策略詳情頁

```
┌────────────────────────────────────────────────────────┐
│  ← 返回    v2-穩健版                    [⭐ 啟用] [編輯] │
├──────────┬─────────────────────────────────────────────┤
│          │                                             │
│  Tab:    │  ┌─ 回測結果 ───────────────────────────┐   │
│  [參數]   │  │                                     │   │
│  [回測]   │  │  📈 權益曲線圖                        │   │
│  [實戰]   │  │  ┌─────────────────────────────────┐│   │
│  [對比]   │  │  │         ~~~~~/\~~~~              ││   │
│          │  │  │    ~~~~/      \   /~~~           ││   │
│          │  │  │  /~~           \/                ││   │
│          │  │  └─────────────────────────────────┘│   │
│          │  │                                     │   │
│          │  │  +38.5%  回撤-11.2%  Sharpe 1.45   │   │
│          │  │  勝率 54%  87筆  成本$2,340         │   │
│          │  │                                     │   │
│          │  │  ┌─ 按出場原因 ──┐ ┌─ 按倉位等級 ──┐│   │
│          │  │  │停損  35% -4.2%│ │核心  +15.2%  ││   │
│          │  │  │停利  42% +8.1%│ │標準   +6.8%  ││   │
│          │  │  │反轉  23% +2.3%│ │探索   +1.2%  ││   │
│          │  │  └───────────────┘ └───────────────┘│   │
│          │  │                                     │   │
│          │  │  ┌─ 診斷 ──────────────────────────┐│   │
│          │  │  │ ✅ 上升趨勢勝率 68%              ││   │
│          │  │  │ ⚠️ 弱上升勝率僅 42%              ││   │
│          │  │  │ ❌ TW_權值 成本佔獲利 18%        ││   │
│          │  │  │ 💡 建議：台股 R:R 提高到 2.5      ││   │
│          │  │  └──────────────────────────────────┘│   │
│          │  │                                     │   │
│          │  │  ┌─ 交易明細（可展開）─────────────┐ │   │
│          │  │  │ AMD  03-15→04-02  +12.8% 停利  │ │   │
│          │  │  │  └ OB(7.6) R:R 12.7→2.9        │ │   │
│          │  │  │  └ MAE -1.2%  MFE +15.1%       │ │   │
│          │  │  │ NVDA 02-10→02-28  -5.1% 停損   │ │   │
│          │  │  │  └ FVG(B) R:R 3.2→-            │ │   │
│          │  │  │  └ MAE -5.1%  MFE +3.2%        │ │   │
│          │  │  └─────────────────────────────────┘ │   │
│          │  └─────────────────────────────────────┘   │
└──────────┴─────────────────────────────────────────────┘
```

### 11.3 /strategies/compare — 策略對比頁

```
┌────────────────────────────────────────────────────────┐
│  策略對比                                               │
│  [選擇 A ▼ v2-穩健版]    vs    [選擇 B ▼ v2-積極版]     │
├────────────────────────────────────────────────────────┤
│                                                        │
│  參數差異                                               │
│  ┌──────────────┬────────────┬────────────┐            │
│  │ 參數          │ 穩健版      │ 積極版      │            │
│  ├──────────────┼────────────┼────────────┤            │
│  │ min_rr       │ 2.0        │ 1.5 ←      │            │
│  │ atr_buffer   │ 0.15       │ 0.12 ←     │            │
│  │ min_conditions│ 2          │ 2          │            │
│  └──────────────┴────────────┴────────────┘            │
│                                                        │
│  績效對比                                               │
│  ┌──────────────┬────────────┬────────────┐            │
│  │ 指標          │ 穩健版      │ 積極版      │            │
│  ├──────────────┼────────────┼────────────┤            │
│  │ 總報酬       │ +38.5% ✓   │ +52.1%     │            │
│  │ 最大回撤     │ -11.2% ✓   │ -18.7%     │            │
│  │ Sharpe       │ 1.45 ✓     │ 1.21       │            │
│  │ 勝率         │ 54.3%      │ 48.2%      │            │
│  │ Profit Factor│ 1.82 ✓     │ 1.55       │            │
│  └──────────────┴────────────┴────────────┘            │
│                                                        │
│  📈 權益曲線疊加                                         │
│  ┌────────────────────────────────────────┐            │
│  │  ─── 穩健版    ─ ─ 積極版               │            │
│  │       ~~~~/\~~~~    -- -/\ ---          │            │
│  │    ~~/ ----\---/~~  -/    \  /--        │            │
│  │  /~~ /      \/    /--     \/            │            │
│  └────────────────────────────────────────┘            │
│                                                        │
│  交易重疊分析                                            │
│  ┌────────────────────────────────────────┐            │
│  │  兩邊都賺：28 筆                         │            │
│  │  A 賺 B 賠：12 筆 ← 穩健版的優勢          │            │
│  │  A 賠 B 賺：8 筆                         │            │
│  │  兩邊都賠：15 筆                          │            │
│  └────────────────────────────────────────┘            │
└────────────────────────────────────────────────────────┘
```

---

## 十二、實作優先順序

```
Phase 1（核心 — 先能跑回測）
━━━━━━━━━━━━━━━━━━━━━━━━━━
  models/strategy.py          StrategyProfile + BacktestResultV2 + BacktestTrade + BacktestEquity
  schemas/strategy.py         Request/Response
  routers/strategies.py       CRUD API（建立/讀取/更新/啟用）
  routers/backtest_v2.py      POST run + GET results
  services/backtester_v2.py   回測引擎核心
  services/stock_grouper.py   自動分群
  前端：策略列表 + 參數編輯 + 回測按鈕 + 結果頁

Phase 2（診斷 + 對比）
━━━━━━━━━━━━━━━━━━━━━━━━━━
  services/diagnosis.py       診斷報告
  /compare API + 前端         策略對比
  MAE/MFE 圖表               前端視覺化
  分類統計 UI                  by_tier / by_trend / by_group

Phase 3（實戰追蹤）
━━━━━━━━━━━━━━━━━━━━━━━━━━
  models/strategy.py          StrategySignal
  services/strategy_tracker.py 每日信號生成
  前端：實戰信號列表 + 跟/不跟 + 績效統計

Phase 4（效能 + 非同步）
━━━━━━━━━━━━━━━━━━━━━━━━━━
  L2 磁碟快取（Pickle）
  SMC 預計算平行化（asyncio / ProcessPool）
  arq + Redis 非同步任務佇列
  L3 Redis 分散式快取
  增量 SMC（只算新的天數）
  前端虛擬滾動（@tanstack/react-virtual）

Phase 5（進階分析）
━━━━━━━━━━━━━━━━━━━━━━━━━━
  參數網格搜索（Grid Search）
  群組參數覆蓋 UI
  多策略資金模型（Portfolio-level simulation）
    → 多個策略共用一個資金池，互相競爭資金
    → 需要排程器：同日多信號 → 資金分配邏輯
    → Phase 1-4 都是單策略模型，暫不需要
```
