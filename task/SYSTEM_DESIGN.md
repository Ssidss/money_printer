# Money Printer v2 — 系統設計文件

> 前後端分離的即時股票分析平台

## 1. 技術棧總覽

| 層級 | 技術 | 說明 |
|------|------|------|
| **前端** | Next.js 14 + TypeScript | App Router, RSC |
| **UI 元件** | shadcn/ui + Tailwind CSS | 一致的深色主題 |
| **圖表** | Lightweight Charts (TradingView) | K 線圖、技術指標疊圖 |
| **後端** | FastAPI (Python 3.11+) | 非同步 API + SSE |
| **ORM** | SQLAlchemy 2.0 + Alembic | 資料模型 + 遷移管理 |
| **資料庫** | PostgreSQL 15+ | 股價、分析結果、組合持倉 |
| **即時推送** | SSE (Server-Sent Events) | 分析進度、股價更新 |
| **任務排程** | APScheduler / Celery (optional) | 定時抓取、定時分析 |

---

## 2. 系統架構

```
┌──────────────────────────────────────────────────────────┐
│                     Next.js Frontend                     │
│  ┌────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │Dashboard│  │Stock     │  │Portfolio │  │Settings   │  │
│  │Overview │  │Detail    │  │Manager   │  │Panel      │  │
│  └────┬───┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│       └──────────┬┴─────────────┴───────────────┘        │
│            REST API calls + SSE subscription              │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────┴───────────────────────────────────┐
│                    FastAPI Backend                        │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐            │
│  │ API Router│  │SSE Stream │  │ Scheduler │            │
│  │ /api/v1/* │  │ /sse/*    │  │ (cron)    │            │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘            │
│        └───────────────┼──────────────┘                  │
│                   Service Layer                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│  │AnalysisSvc│ │FetcherSvc│  │PortfolioS│  │ReportSvc│  │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └────┬────┘  │
│        └──────────────┼─────────────┼────────────┘       │
│                  Data Access Layer (SQLAlchemy)           │
└──────────────────────┬───────────────────────────────────┘
                       │ SQL
                ┌──────┴──────┐
                │ PostgreSQL  │
                │  - stocks   │
                │  - prices   │
                │  - analysis │
                │  - portfolio│
                │  - news     │
                └─────────────┘
```

---

## 3. 資料庫 Schema 設計

### 3.1 stocks（股票基本資料）

```sql
CREATE TABLE stocks (
    id          SERIAL PRIMARY KEY,
    ticker      VARCHAR(20) UNIQUE NOT NULL,  -- e.g. "AAPL", "2330.TW"
    name        VARCHAR(100),                  -- e.g. "Apple Inc.", "台積電"
    market      VARCHAR(10) NOT NULL,          -- "US" | "TW"
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.2 price_history（歷史股價 OHLCV）

```sql
CREATE TABLE price_history (
    id          SERIAL PRIMARY KEY,
    stock_id    INTEGER REFERENCES stocks(id),
    date        DATE NOT NULL,
    open        NUMERIC(12,4),
    high        NUMERIC(12,4),
    low         NUMERIC(12,4),
    close       NUMERIC(12,4),
    volume      BIGINT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stock_id, date)
);
CREATE INDEX idx_price_stock_date ON price_history(stock_id, date DESC);
```

### 3.3 analysis_results（分析結果）

```sql
CREATE TABLE analysis_results (
    id                SERIAL PRIMARY KEY,
    stock_id          INTEGER REFERENCES stocks(id),
    analysis_date     DATE NOT NULL,
    -- 綜合分數
    composite_score   NUMERIC(5,2),
    technical_score   NUMERIC(5,2),
    sentiment_score   NUMERIC(5,2),
    recommendation    VARCHAR(20),        -- "強力推薦" | "推薦" | "觀察" | "不推薦"
    -- 技術指標快照
    rsi               NUMERIC(6,2),
    macd              NUMERIC(10,4),
    macd_signal       NUMERIC(10,4),
    ma5               NUMERIC(12,4),
    ma20              NUMERIC(12,4),
    ma60              NUMERIC(12,4),
    bb_upper          NUMERIC(12,4),
    bb_lower          NUMERIC(12,4),
    volume_ratio      NUMERIC(6,2),
    -- 交易訊號 (JSON array)
    signals           JSONB DEFAULT '[]',
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stock_id, analysis_date)
);
```

### 3.4 news_articles（新聞資料）

```sql
CREATE TABLE news_articles (
    id            SERIAL PRIMARY KEY,
    stock_id      INTEGER REFERENCES stocks(id),
    title         TEXT NOT NULL,
    url           TEXT,
    source        VARCHAR(50),
    published_at  TIMESTAMPTZ,
    sentiment     NUMERIC(5,2),       -- 單篇情緒分數
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.5 portfolio_transactions（交易紀錄）

```sql
CREATE TABLE portfolio_transactions (
    id            SERIAL PRIMARY KEY,
    stock_id      INTEGER REFERENCES stocks(id),
    action        VARCHAR(10) NOT NULL,  -- "BUY" | "SELL"
    shares        NUMERIC(12,4) NOT NULL,
    price         NUMERIC(12,4) NOT NULL,
    total_cost    NUMERIC(14,4),
    note          TEXT,
    transacted_at TIMESTAMPTZ DEFAULT NOW(),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.6 portfolio_holdings（當前持倉，由 transactions 計算的 materialized view）

```sql
CREATE TABLE portfolio_holdings (
    id              SERIAL PRIMARY KEY,
    stock_id        INTEGER REFERENCES stocks(id) UNIQUE,
    total_shares    NUMERIC(12,4),
    avg_cost        NUMERIC(12,4),
    highest_price   NUMERIC(12,4),     -- for trailing stop
    status          VARCHAR(20),        -- "持有獲利" | "持有觀察" | "停利" | "停損" | "追蹤停損"
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. API 端點設計

### 4.1 股票資料

| Method | Path | 說明 |
|--------|------|------|
| GET | `/api/v1/stocks` | 取得所有追蹤的股票清單 |
| GET | `/api/v1/stocks/{ticker}` | 取得單一股票詳細資料 |
| POST | `/api/v1/stocks` | 新增追蹤股票 |
| DELETE | `/api/v1/stocks/{ticker}` | 移除追蹤股票 |
| GET | `/api/v1/stocks/{ticker}/prices` | 取得歷史股價 (支援 query: ?from=&to=&interval=) |
| GET | `/api/v1/stocks/{ticker}/analysis` | 取得最新分析結果 |
| GET | `/api/v1/stocks/{ticker}/news` | 取得相關新聞 |

### 4.2 分析與排行

| Method | Path | 說明 |
|--------|------|------|
| POST | `/api/v1/analysis/run` | 觸發一次完整分析（回傳 task_id） |
| GET | `/api/v1/analysis/latest` | 取得最新一次分析的完整結果 |
| GET | `/api/v1/analysis/history` | 取得歷史分析結果列表 |
| GET | `/api/v1/analysis/top-picks` | 取得今日 Top N 推薦 |

### 4.3 投資組合

| Method | Path | 說明 |
|--------|------|------|
| GET | `/api/v1/portfolio` | 取得當前持倉總覽 |
| POST | `/api/v1/portfolio/buy` | 記錄買入 |
| POST | `/api/v1/portfolio/sell` | 記錄賣出 |
| GET | `/api/v1/portfolio/transactions` | 取得交易紀錄 |
| GET | `/api/v1/portfolio/pnl` | 取得損益統計 |

### 4.4 SSE 即時推送

| Method | Path | 說明 |
|--------|------|------|
| GET | `/sse/analysis-progress` | 分析進度推送（進度條用） |
| GET | `/sse/price-updates` | 股價即時更新推送 |

**SSE 事件格式：**

```
// 分析進度
event: progress
data: {"task_id": "abc123", "phase": "fetching_prices", "current": 5, "total": 30, "ticker": "AAPL", "message": "正在抓取 AAPL 股價..."}

// 分析完成
event: analysis_complete
data: {"task_id": "abc123", "top_picks": [...], "summary": {...}}

// 股價更新
event: price_update
data: {"ticker": "2330.TW", "price": 850.00, "change": +1.2, "updated_at": "..."}
```

---

## 5. 前端頁面規劃

### 5.1 頁面結構 (Next.js App Router)

```
app/
├── layout.tsx              # 全域 Layout (深色主題, Sidebar)
├── page.tsx                # Dashboard 首頁 (今日總覽)
├── stocks/
│   ├── page.tsx            # 股票列表 (全部追蹤的股票)
│   └── [ticker]/
│       └── page.tsx        # 股票詳情 (K線圖 + 技術指標 + 新聞)
├── analysis/
│   ├── page.tsx            # 分析歷史 / 觸發新分析
│   └── [date]/
│       └── page.tsx        # 特定日期分析報告
├── portfolio/
│   ├── page.tsx            # 持倉總覽 + 損益
│   └── transactions/
│       └── page.tsx        # 交易紀錄
└── settings/
    └── page.tsx            # 設定 (追蹤股票管理, 參數調整)
```

### 5.2 Dashboard 首頁功能

- **今日 Top Picks 卡片** — 前 3 名推薦，帶分數進度條
- **分析狀態指示器** — 上次分析時間 + 一鍵觸發按鈕
- **分析進度條** — SSE 即時顯示分析進度
- **市場概覽** — 美股 / 台股各自平均分數趨勢
- **持倉快照** — 當前持倉的即時損益
- **最新警報** — 停損 / 停利提醒

### 5.3 股票詳情頁功能

- **TradingView K 線圖** — OHLCV 蠟燭圖 + 成交量
- **技術指標疊圖** — MA5/20/60 線、布林通道、RSI 副圖、MACD 副圖
- **分析分數歷史** — 折線圖顯示近期分數變化
- **交易訊號時間軸** — 買賣點標記在 K 線上
- **相關新聞列表** — 最新新聞 + 情緒標記

---

## 6. 啟動時自動補齊資料流程

當 `python main.py` 啟動 FastAPI 伺服器時：

```
startup 事件觸發
    │
    ├── 1. 連接 PostgreSQL，執行 Alembic migration
    │
    ├── 2. 檢查 stocks 表是否有資料
    │      └── 若空 → 從 config/settings.py 匯入初始股票清單
    │
    ├── 3. 對每支股票檢查 price_history 最新日期
    │      └── 計算缺失天數 → 批次抓取缺失的股價
    │      └── 透過 SSE 推送補齊進度
    │
    ├── 4. 檢查今天是否已有 analysis_results
    │      └── 若無且為交易日 → 自動觸發今日分析
    │      └── 透過 SSE 推送分析進度
    │
    └── 5. 啟動定時排程
           ├── 每日 18:00 (台股收盤後) 自動分析
           └── 每日 06:00 (美股收盤後) 自動分析
```

---

## 7. 專案目錄結構 (v2)

```
money_printer/
├── backend/                        # FastAPI 後端
│   ├── main.py                     # FastAPI app 入口 + startup
│   ├── requirements.txt
│   ├── alembic/                    # DB migration
│   │   └── versions/
│   ├── alembic.ini
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py               # 設定 (from .env)
│   │   ├── database.py             # SQLAlchemy engine + session
│   │   ├── models/                 # SQLAlchemy models
│   │   │   ├── stock.py
│   │   │   ├── price.py
│   │   │   ├── analysis.py
│   │   │   ├── news.py
│   │   │   └── portfolio.py
│   │   ├── schemas/                # Pydantic schemas (request/response)
│   │   │   ├── stock.py
│   │   │   ├── analysis.py
│   │   │   └── portfolio.py
│   │   ├── routers/                # API endpoints
│   │   │   ├── stocks.py
│   │   │   ├── analysis.py
│   │   │   ├── portfolio.py
│   │   │   └── sse.py
│   │   ├── services/               # 業務邏輯 (重構自 v1)
│   │   │   ├── fetcher.py          # 股價抓取 (from data/fetcher.py)
│   │   │   ├── news_crawler.py     # 新聞爬取 (from data/news_crawler.py)
│   │   │   ├── technical.py        # 技術分析 (from analysis/technical.py)
│   │   │   ├── sentiment.py        # 情緒分析 (from analysis/sentiment.py)
│   │   │   ├── recommender.py      # 推薦引擎 (from strategy/recommender.py)
│   │   │   └── portfolio.py        # 組合管理 (from portfolio/tracker.py)
│   │   └── sse/                    # SSE 事件管理
│   │       └── event_manager.py
│   └── tests/
│       └── ...
│
├── frontend/                       # Next.js 前端
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── app/                    # App Router pages
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx            # Dashboard
│   │   │   ├── stocks/
│   │   │   ├── analysis/
│   │   │   ├── portfolio/
│   │   │   └── settings/
│   │   ├── components/             # 共用元件
│   │   │   ├── ui/                 # shadcn/ui
│   │   │   ├── charts/             # TradingView chart wrappers
│   │   │   ├── layout/             # Sidebar, Header, etc.
│   │   │   └── stocks/             # 股票相關元件
│   │   ├── hooks/                  # Custom hooks
│   │   │   ├── useSSE.ts           # SSE 連線 hook
│   │   │   └── useStocks.ts        # SWR/React Query hooks
│   │   ├── lib/                    # 工具函式
│   │   │   ├── api.ts              # API client
│   │   │   └── utils.ts
│   │   └── types/                  # TypeScript 型別
│   │       └── index.ts
│   └── public/
│
├── docker-compose.yml              # PostgreSQL + Backend + Frontend
├── .env.example
├── task/                           # 開發管理
│   ├── SYSTEM_DESIGN.md            # ← 本文件
│   ├── ARCHITECTURE.mermaid        # 架構圖
│   └── TODO.md                     # 開發進度追蹤
│
└── legacy/                         # v1 原始碼 (保留參考)
    ├── analysis/
    ├── config/
    ├── data/
    ├── notify/
    ├── portfolio/
    └── strategy/
```

---

## 8. 開發階段規劃

### Phase 1：基礎建設 (Backend Core)
- [ ] FastAPI 專案骨架 + 目錄結構
- [ ] PostgreSQL + SQLAlchemy models + Alembic migration
- [ ] 將 v1 的 fetcher / technical / sentiment 重構為 service
- [ ] 基本 CRUD API (stocks, prices)
- [ ] Startup 自動補齊資料邏輯

### Phase 2：分析引擎 API 化
- [ ] `/api/v1/analysis/run` — 觸發分析 + SSE 進度推送
- [ ] `/api/v1/analysis/latest` + `/top-picks`
- [ ] SSE event manager 實作
- [ ] 定時排程整合

### Phase 3：前端 MVP
- [ ] Next.js 專案初始化 + Tailwind + shadcn/ui
- [ ] 全域 Layout (Sidebar + 深色主題)
- [ ] Dashboard 首頁 (Top Picks + 分析狀態)
- [ ] SSE hook + 進度條元件
- [ ] 股票列表頁

### Phase 4：圖表與詳情頁
- [ ] Lightweight Charts 整合 (K 線圖元件)
- [ ] 技術指標疊圖 (MA, BB, RSI, MACD)
- [ ] 股票詳情頁完整功能
- [ ] 分析分數歷史趨勢圖

### Phase 5：投資組合
- [ ] Portfolio API (buy/sell/holdings/pnl)
- [ ] 持倉總覽頁面
- [ ] 交易紀錄頁面
- [ ] 停損 / 停利警報整合

### Phase 6：收尾
- [ ] Docker Compose 整合部署
- [ ] 設定頁面 (股票管理, 參數調整)
- [ ] 錯誤處理 + Loading states
- [ ] 效能優化 + 快取策略
