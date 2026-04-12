# Money Printer — 專案交接文件

> 版本：2.1.0 | 最後更新：2026-04-12

---

## 一、專案概述

Money Printer 是一套自動化股票分析系統，追蹤美股 + 台股，結合 SMC（Smart Money Concept）結構分析、動量技術指標、新聞情緒三層決策，產生買賣建議與倉位管理。

**核心能力：**
- 每日自動爬取價格 + 新聞，計算技術指標 + SMC 結構
- 根據多時間框架（MTF）趨勢對齊產生進出場計畫
- 三套回測引擎（v1 / v2 / v3）驗證策略表現
- Web UI 提供 Dashboard、持倉管理、K 線圖、開盤簡報

---

## 二、技術棧

| 層級 | 技術 |
|------|------|
| 後端 API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 async |
| 資料庫 | PostgreSQL 15 + asyncpg |
| 資料來源 | yfinance（美股/台股）、RSS feeds（新聞） |
| 分析計算 | pandas, numpy, ta（技術指標庫） |
| 前端 | Next.js 16 (App Router) + TypeScript + React 19 |
| 樣式 | Tailwind CSS v4 |
| 圖表 | lightweight-charts（K 線圖）|
| Python 環境 | conda env `money_printer`（Python 3.11）|
| 即時通訊 | Server-Sent Events (SSE) |

---

## 三、系統架構圖

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 16)                 │
│  Dashboard | 股票清單 | 個股頁面 | 策略回測 | 開盤簡報    │
│                   ↕ REST API + SSE                      │
├─────────────────────────────────────────────────────────┤
│                    Backend (FastAPI)                      │
│                                                          │
│  ┌─── v1 Routes ───┐  ┌── v2 Routes ──┐  ┌─ v3 Routes ─┐│
│  │ stocks, analysis │  │ smc_v2       │  │ backtest_v3  ││
│  │ portfolio, brief │  │ strategies   │  │              ││
│  │ scanner, ai_note │  │ backtest_v2  │  │              ││
│  └─────────────────┘  └──────────────┘  └──────────────┘│
│                                                          │
│  ┌─── Services ─────────────────────────────────────────┐│
│  │ fetcher → technical → smc_worker → recommender       ││
│  │ news_crawler → sentiment                             ││
│  │ decision/{entry, mtf_gate, position_sizer}           ││
│  │ smc/{structure, order_block, fvg, liquidity, fib}    ││
│  │ backtest_v3/{engine, strategies, metrics}            ││
│  └──────────────────────────────────────────────────────┘│
│                       ↕ SQLAlchemy async                 │
├─────────────────────────────────────────────────────────┤
│                  PostgreSQL 15                           │
│  stocks | price_history | analysis_results | news        │
│  portfolio_* | strategy_profiles | backtest_*            │
└─────────────────────────────────────────────────────────┘
```

---

## 四、資料流

### 4.1 資料進場（External → DB）

```
yfinance API ──→ [fetcher.py] fetch_and_store_prices()
                      │
                      ↓
               price_history 表（OHLCV，upsert by stock_id + date）

RSS feeds ────→ [news_crawler.py] crawl_and_store_news()
                      │
                      ↓
               news_articles 表 + [sentiment.py] 情緒分數 0-100
```

**觸發方式：** 手動 API 呼叫（排程已關閉）
- `POST /api/v1/stocks/batch-fetch` — 更新全部股票價格
- `POST /api/v1/analysis/run` — 完整分析 pipeline

### 4.2 分析 Pipeline（DB → 計算 → DB）

```
price_history DF (最近 2 年)
    │
    ├→ [technical.py] RSI, MACD, BB, MA, 量比
    ├→ [smc_worker.py]
    │     ├→ smc/structure.py    趨勢結構（上升/盤整/下降）
    │     ├→ smc/order_block.py  OB 偵測（bullish/bearish）
    │     ├→ smc/fvg.py          FVG 缺口偵測
    │     ├→ smc/liquidity.py    流動性叢集
    │     └→ smc/fibonacci.py    Fibonacci 回撤
    │
    ├→ [decision/mtf_gate.py]    多時間框架趨勢對齊
    ├→ [decision/entry.py]       進出場計畫（entry/stop/target/R:R）
    ├→ [decision/position_sizer.py] 倉位等級（核心/標準/探索）
    │
    └→ [recommender.py]          綜合分數 = 技術(40%) + 情緒(30%) + 倉位(30%)
         │
         ↓
    analysis_results 表（composite_score + smc_data JSONB + entry_plan JSONB）
```

### 4.3 API → 前端

**核心原則：API 只讀 DB，不做即時計算。** 所有分析結果預先算好存 JSONB。

```
GET /api/v1/analysis/latest     → 讀 analysis_results，回傳 Top Picks
GET /api/v2/smc/stocks/{ticker} → 讀 smc_data JSONB，附 stale flag（>24h 標記過期）
GET /api/v1/briefing/next-open  → 合併 holdings + analysis + ai_notes
```

---

## 五、資料庫 Tables

### 核心資料

| Table | 用途 | 關鍵欄位 |
|-------|------|---------|
| `users` | 使用者帳號 | email, password_hash, display_name |
| `stocks` | 追蹤股票清單 | ticker (unique), market (US/TW), is_active |
| `price_history` | OHLCV 日線 | stock_id + date (unique), open/high/low/close/volume |
| `analysis_results` | 分析結果 | stock_id + analysis_date (unique), composite_score, smc_data (JSONB), entry_plan (JSONB) |
| `news_articles` | 新聞 | stock_id, title, url, sentiment_score |

### 投資組合

| Table | 用途 | 關鍵欄位 |
|-------|------|---------|
| `portfolio_holdings` | 目前持倉 | user_id + stock_id (unique), total_shares, avg_cost |
| `portfolio_transactions` | 交易記錄 | user_id, stock_id, action (BUY/SELL), shares, price |

### 策略 & 回測

| Table | 用途 | 關鍵欄位 |
|-------|------|---------|
| `strategy_profiles` | v2 策略設定 | name, params (JSONB), is_active |
| `backtest_results_v2` | v2 回測結果 | profile_id, metrics (JSONB), strategy_hash |
| `backtest_trades` | 回測個別交易 | backtest_id, ticker, fill_price, exit_price, pnl_pct |
| `backtest_equity` | 權益曲線 | backtest_id, date, equity_value |

### AI 筆記

| Table | 用途 | 關鍵欄位 |
|-------|------|---------|
| `ai_analysis_notes` | AI 深度分析 | stock_id, recommendation, action, summary (Markdown) |

---

## 六、API 完整列表

### v1 Routes（prefix: `/api/v1`）

#### Auth (`auth.py`)
| Method | Path | 說明 |
|--------|------|------|
| POST | `/auth/register` | 註冊 |
| POST | `/auth/login` | 登入，回傳 JWT |
| GET | `/auth/me` | 取得當前使用者 |
| PUT | `/auth/me` | 更新個人資料 |

#### Stocks (`stocks.py`)
| Method | Path | 說明 |
|--------|------|------|
| GET | `/stocks` | 所有追蹤股票 |
| GET | `/stocks/{ticker}` | 單支股票資訊 |
| GET | `/stocks/realtime` | 全部即時報價 |
| GET | `/stocks/{ticker}/realtime` | 單支即時報價 |
| GET | `/stocks/{ticker}/prices` | 歷史價格（支援 daily/weekly/monthly）|
| GET | `/stocks/{ticker}/analysis` | 最新分析結果 |
| GET | `/stocks/{ticker}/news` | 相關新聞 |
| GET | `/stocks/smc-trends` | 全部股票 SMC 趨勢 |
| GET | `/stocks/{ticker}/smc` | SMC 分析詳細（OB/FVG/結構）|
| POST | `/stocks` | 新增追蹤股票 |
| POST | `/stocks/batch-fetch` | 批次更新價格（背景執行）|
| POST | `/stocks/{ticker}/fetch` | 更新單支價格 |
| POST | `/stocks/{ticker}/analyze` | 觸發分析（async）|
| POST | `/stocks/{ticker}/analyze/sync` | 同步分析（回傳結果）|
| DELETE | `/stocks/{ticker}` | 停止追蹤 |

#### Analysis (`analysis.py`)
| Method | Path | 說明 |
|--------|------|------|
| POST | `/analysis/run` | 觸發全批次分析（新聞 + v1 評分 + SMC v2）|
| GET | `/analysis/status` | 分析執行狀態 |
| GET | `/analysis/top-picks` | Top N 推薦 |
| GET | `/analysis/latest` | 最新分析完整結果 |

#### Portfolio (`portfolio.py`)
| Method | Path | 說明 |
|--------|------|------|
| POST | `/portfolio/buy` | 買入交易 |
| POST | `/portfolio/sell` | 賣出交易 |
| GET | `/portfolio` | 目前持倉 |
| GET | `/portfolio/transactions` | 交易歷史 |

#### Briefing (`briefing.py`)
| Method | Path | 說明 |
|--------|------|------|
| GET | `/briefing/next-open` | 開盤簡報（持倉健檢 + watchlist）|

#### Scanner (`scanner.py`)
| Method | Path | 說明 |
|--------|------|------|
| GET | `/scanner` | 最新掃描結果 |
| GET | `/scanner/tracked` | 僅掃描追蹤股票（同步）|
| POST | `/scanner/run` | 完整掃描（背景執行）|
| GET | `/scanner/status` | 掃描狀態 |

#### AI Notes (`ai_notes.py`)
| Method | Path | 說明 |
|--------|------|------|
| POST | `/ai-notes` | 建立 AI 筆記 |
| GET | `/ai-notes` | 列出筆記（可按 ticker 過濾）|
| GET | `/ai-notes/latest` | 每支股票的最新筆記 |
| GET | `/ai-notes/{id}` | 單筆筆記 |
| DELETE | `/ai-notes/{id}` | 刪除筆記 |

#### Telegram (`telegram.py`)
| Method | Path | 說明 |
|--------|------|------|
| GET | `/telegram/test` | 測試 Bot 連線 |
| GET | `/telegram/me` | 取得 chat_id |

### v2 Routes（prefix: `/api/v2`）

#### SMC v2 (`smc_v2.py`)
| Method | Path | 說明 |
|--------|------|------|
| GET | `/smc/stocks/{ticker}` | 完整 SMC v2 結果 |
| GET | `/smc/stocks/{ticker}/entry` | 進場計畫 |
| GET | `/smc/stocks/{ticker}/summary` | 快速摘要 |
| POST | `/smc/analysis/run` | 觸發 SMC 批次分析 |

#### Strategies (`strategies.py`)
| Method | Path | 說明 |
|--------|------|------|
| POST | `/strategies` | 建立策略 |
| GET | `/strategies` | 列出策略 |
| GET | `/strategies/{id}` | 策略詳情 |
| PUT | `/strategies/{id}` | 更新策略 |
| DELETE | `/strategies/{id}` | 刪除策略 |
| POST | `/strategies/{id}/activate` | 啟用策略 |

#### Backtest v2 (`backtest_v2.py`)
| Method | Path | 說明 |
|--------|------|------|
| POST | `/backtest/run` | 執行 v2 回測 |
| GET | `/backtest/results` | 列出回測結果 |
| GET | `/backtest/results/{id}` | 回測詳情 |
| GET | `/backtest/compare` | 比較多次回測 |

### v3 Routes（prefix: `/api/v3`）

#### Backtest v3 (`backtest_v3.py`)
| Method | Path | 說明 |
|--------|------|------|
| POST | `/backtest-v3/run` | 執行 v3 回測（多策略引擎）|
| GET | `/backtest-v3/status` | 回測狀態 |
| GET | `/backtest-v3/result` | 最新完整結果 |
| GET | `/backtest-v3/result/summary` | 輕量摘要 |
| GET | `/backtest-v3/result/trades` | 交易紀錄（支援分頁 + 策略/倉位過濾）|
| GET | `/backtest-v3/result/equity` | 權益曲線 |
| GET | `/backtest-v3/splits` | 資料切割列表（train/validation/test）|

### SSE（prefix: `/sse`）
| Method | Path | 說明 |
|--------|------|------|
| GET | `/sse/progress` | 即時進度串流（分析/回測/掃描）|

---

## 七、Services 模組說明

### 資料取得

| 模組 | 功能 | 即時/排程 |
|------|------|----------|
| `fetcher.py` | yfinance 爬取 OHLCV，upsert 到 price_history | 手動觸發 |
| `news_crawler.py` | RSS 爬取新聞，存 news_articles | 手動觸發 |
| `sentiment.py` | 新聞情緒分數（關鍵字 + 規則，0-100）| 隨新聞爬取 |

### 分析引擎

| 模組 | 功能 |
|------|------|
| `technical.py` | MACD (30%) + MA (25%) + RSI (20%) + Vol (15%) + BB (10%) 加權技術分 |
| `smc_v1.py` | 舊版 SMC（結構 + OB + FVG），已被 v2 取代 |
| `smc_worker.py` | SMC v2 主控：price DF → 多時間框架 SMC → EntryPlan → 存 DB |
| `recommender.py` | v1 綜合分數 = 技術 + 情緒 + 倉位分層 |
| `scanner.py` | 爆擊掃描：放量 + 連漲 + 新高 → explosion_score (0-100) |

### SMC 子模組（`smc/`）

| 模組 | 功能 |
|------|------|
| `structure.py` | 趨勢結構辨識（swing high/low, BOS, CHoCH）|
| `order_block.py` | Order Block 偵測（bullish/bearish OB，含 score + retest）|
| `fvg.py` | Fair Value Gap 偵測（缺口，含 freshness + grade）|
| `liquidity.py` | 流動性叢集（BSL/SSL，含 sweep 偵測）|
| `fibonacci.py` | Fibonacci 回撤計算 |
| `config.py` | SMC 參數設定 |

### 決策系統（`decision/`）

| 模組 | 功能 |
|------|------|
| `entry.py` | 進場計畫：選最佳買入價（OB > FVG > Swing Low）+ 停損 + 目標 |
| `mtf_gate.py` | 多時間框架門檻：月線/週線/日線趨勢對齊檢查 |
| `position_sizer.py` | 倉位分級：4 條件=核心(15-20%) / 3=標準(8-12%) / 2=探索(3-5%) |
| `sentiment_gate.py` | 情緒門檻：正面(>=65)加速 / 負面(<=35)警告 |

### 回測引擎

| 引擎 | 檔案 | 特色 |
|------|------|------|
| v1 | `backtester.py` | 簡單回測，composite_score 觸發 |
| v2 | `backtester_v2.py` | 策略 profile，可重複執行（hash 去重），結果存 DB |
| v3 | `backtest_v3/` | 多策略引擎，Signal→Decision→Order→Fill→Position pipeline |

### V3 回測引擎詳細（`backtest_v3/`）

```
engine.py       事件循環：逐日掃描所有股票 → 策略產生 Signal → 決策 → 下單 → 成交
strategy.py     策略基底 class（abstract generate_signals）
models.py       Signal / Decision / Order / Position / Fill dataclass
provider.py     歷史資料 provider + DATA_SPLITS (train/validation/test)
metrics.py      績效計算（Sharpe/Sortino/Calmar/CAGR/MDD/PF/WR/CVaR）

strategies/
  smc_strategy.py        SMC 驅動策略（趨勢 + OB/FVG 進場）
  momentum_breakout.py   N 日新高突破 + 放量確認
  explosion_scanner.py   爆擊掃描（score >= threshold 觸發）
```

**V3 回測驗證結果（2023-2024 Validation）：**

| 策略 | CAGR | Sharpe | MDD | Trades |
|------|------|--------|-----|--------|
| Explosion Scanner (score>=50) | +19.5% | 1.69 | 7.8% | 45 |
| Momentum Breakout (20d) | +16.9% | 1.09 | 10.9% | 177 |
| SMC v2 | +6.6% | 0.57 | 12.2% | 189 |

---

## 八、前端頁面

| 路由 | 頁面 | 功能 |
|------|------|------|
| `/` | Dashboard | 追蹤股票數、Top 3 推薦、持倉摘要、批次操作 |
| `/login` | 登入 | 註冊 / 登入表單 |
| `/stocks` | 股票清單 | 所有追蹤股票表格、即時報價、新增/刪除 |
| `/stocks/[ticker]` | 個股頁面 | K 線圖 + SMC overlay + 技術指標 + 新聞 + AI 筆記 |
| `/portfolio` | 投資組合 | 持倉表格、買入/賣出 modal、交易歷史 |
| `/briefing` | 開盤簡報 | 持倉健檢（趨勢變化、停損接近）+ watchlist 推薦 |
| `/strategies` | 策略回測 | V3 回測引擎面板 + V2 策略管理 |
| `/strategies/[id]` | 策略詳情 | 策略參數編輯 + 回測歷史 |
| `/scanner` | 爆擊掃描 | 掃描結果、分數排序、觸發掃描 |
| `/backtest` | 回測 v1 | 舊版回測介面 |
| `/analysis` | 系統說明 | 分析策略架構說明頁 |

### 前端組件結構

```
src/
├── app/                          # Next.js App Router 頁面
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx           # 左側導航
│   │   ├── TopBar.tsx            # 頂部欄 + 策略 badge
│   │   ├── StrategyPanel.tsx     # 右側策略切換面板
│   │   ├── UserMenu.tsx          # 使用者選單
│   │   └── Providers.tsx         # Context 包裝（Auth + Strategy）
│   ├── dashboard/
│   │   ├── TopPickCard.tsx       # 推薦卡片
│   │   ├── HoldingsSection.tsx   # 持倉區塊
│   │   ├── AnalyzeButton.tsx     # 觸發分析按鈕
│   │   └── BatchFetchButton.tsx  # 批次更新價格
│   ├── stock/
│   │   ├── StockChart.tsx        # K 線圖 + SMC overlay
│   │   ├── ChartControls.tsx     # 時間框架切換
│   │   ├── VolumeProfile.tsx     # 成交量分佈
│   │   ├── AiNotes.tsx           # AI 筆記顯示/建立
│   │   └── StockActions.tsx      # 爬取/分析按鈕
│   ├── stocks/
│   │   ├── StocksTable.tsx       # 股票清單表格
│   │   ├── AddStockModal.tsx     # 新增股票
│   │   └── RemoveStockButton.tsx # 移除股票
│   ├── portfolio/
│   │   ├── PortfolioClient.tsx   # 持倉主組件
│   │   ├── BuyModal.tsx          # 買入 modal
│   │   └── SellModal.tsx         # 賣出 modal
│   └── strategy/
│       ├── BacktestV3Panel.tsx   # V3 回測引擎面板
│       ├── StrategyList.tsx      # 策略列表 CRUD
│       └── StrategyDetail.tsx    # 策略詳情
├── contexts/
│   ├── AuthContext.tsx           # 登入狀態（JWT）
│   └── StrategyContext.tsx       # 全站策略狀態（single/multi 模式）
├── hooks/
│   └── useSSE.ts                 # SSE 連線 hook
└── lib/
    └── api.ts                    # API client + 所有 TypeScript type 定義
```

---

## 九、設定檔

### `.env`（後端，根目錄）
```
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=<密碼>
DB_NAME=money_printer
SECRET_KEY=<secrets.token_urlsafe(64)>
ACCESS_TOKEN_EXPIRE_MINUTES=1440
TELEGRAM_BOT_TOKEN=<optional>
TELEGRAM_CHAT_ID=<optional>
ALLOWED_ORIGINS=http://localhost:3000
ENVIRONMENT=development
```

### `frontend/.env.local`
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 啟動方式
```bash
# 後端
conda activate money_printer
cd backend && python -m uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
/opt/homebrew/bin/node node_modules/.bin/next dev --webpack

# API 文件
http://localhost:8000/docs
```

---

## 十、分層決策架構

```
Layer 1: SMC 結構（方向門檻）
  上升結構 → 通過
  盤整     → 降級（最高標準倉位）
  下降結構 → 排除（不做多）

Layer 2: 動量確認
  MACD 30% + MA 25% + RSI 20% + Vol 15% + BB 10%
  RSI 高=好, 布林突破上軌=好, 量價配合

Layer 3: 催化劑（新聞情緒）
  正面(>=65) → 加速信號，倉位升級
  中性       → 不影響
  負面(<=35) → 警告，倉位降級

分層結果：
  4 條件滿足 → 強力推薦 + 核心持倉 (15-20%)
  3 條件滿足 → 推薦 + 標準倉位 (8-12%)
  2 條件滿足 → 觀察 + 探索倉位 (3-5%)
  <2 條件    → 不推薦
```

---

## 十一、即時 vs 手動觸發

| 功能 | 觸發方式 | 說明 |
|------|---------|------|
| 價格更新 | 手動 `POST /api/v1/stocks/batch-fetch` | 排程已關閉 |
| 全批次分析 | 手動 `POST /api/v1/analysis/run` | 爬新聞 + 技術分 + SMC v2 |
| 單股分析 | 手動 `POST /api/v1/stocks/{ticker}/analyze/sync` | 同步回傳 |
| 爆擊掃描 | 手動 `POST /api/v1/scanner/run` | 背景執行 |
| V3 回測 | 手動 `POST /api/v3/backtest-v3/run` | 背景執行，SSE 追蹤進度 |
| 即時報價 | 即時 `GET /api/v1/stocks/realtime` | yfinance 即時查詢 |

所有背景任務透過 SSE `/sse/progress` 串流進度。

---

## 十二、目前進度 & 未完成功能

### 已完成
- [x] v1 分析 pipeline（技術 + 情緒 + 推薦）
- [x] v2 SMC 分析（結構 + OB + FVG + 流動性 + MTF）
- [x] v2 決策系統（進場計畫 + 倉位分級）
- [x] v3 回測引擎（Signal→Decision→Order→Fill→Position）
- [x] 3 個 V3 策略（SMC v2 / Momentum / Explosion）
- [x] 前端完整 UI（Dashboard / 股票 / 持倉 / 回測 / 簡報）
- [x] 使用者認證（JWT）
- [x] AI 筆記系統
- [x] 策略面板（Phase A：StrategyContext + StrategyPanel）

### 進行中（Strategy UX 改善計畫）
- [ ] Phase B：即時信號 API（`GET /api/v3/signals/{ticker}`）+ 個股頁面策略卡片
- [ ] Phase D：Trade Detail 展開 + 交易解釋
- [ ] Phase E：回測結果歷史 + 策略比較視圖
- [ ] Phase C：Dashboard / 股票清單 策略整合
- [ ] Phase F：開盤簡報策略整合

### 已知限制
- 排程已關閉，所有分析需手動觸發
- V3 回測結果僅存記憶體（重啟後遺失）
- SSE 狀態存記憶體（單 process）
- 新聞情緒用規則，非 ML 模型
- 無 WebSocket，僅 SSE

---

## 十三、檔案數量統計

```
後端:
  routers/     15 files    API 路由
  services/    25+ files   商業邏輯
  models/       8 files    DB Model
  共計 ~6,000 行 Python

前端:
  app/         12 pages    路由頁面
  components/  20+ files   UI 組件
  contexts/     2 files    狀態管理
  lib/          1 file     API client (~810 行，含完整 type 定義)
  共計 ~4,000 行 TypeScript
```
