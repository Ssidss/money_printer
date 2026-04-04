# Money Printer v2 — 開發進度追蹤

> 最後更新：2026-04-04

## 狀態說明
- ⬜ 未開始
- 🔲 進行中
- ✅ 完成
- ❌ 取消 / 擱置

---

## Phase 1：Backend 基礎建設

| # | 任務 | 狀態 |
|---|------|------|
| 1.1 | backend/ 目錄骨架 + FastAPI app factory | ✅ |
| 1.2 | SQLAlchemy 2.0 async engine + session | ✅ |
| 1.3 | 所有 DB models (stock, price, analysis, news, portfolio, backtest) | ✅ |
| 1.4 | Alembic 初始化 + 初始 migration | ✅ |
| 1.5 | FetcherService — 抓股價寫入 DB | ✅ |
| 1.6 | NewsCrawlerService — 爬新聞寫入 DB | ✅ |
| 1.7 | TechnicalService — 技術分析 | ✅ |
| 1.8 | SentimentService — 情緒分析 | ✅ |
| 1.9 | RecommenderService — 推薦引擎 | ✅ |
| 1.10 | BacktesterService — 回測引擎 | ✅ |
| 1.11 | Scheduler — APScheduler 定時任務 | ✅ |
| 1.12 | SSE EventManager | ✅ |
| 1.13 | Startup 自動補齊股價邏輯 | ✅ |

---

## Phase 2：API Routers

| # | 任務 | 狀態 |
|---|------|------|
| 2.1 | /api/v1/stocks CRUD | ⬜ |
| 2.2 | /api/v1/stocks/{ticker}/prices | ⬜ |
| 2.3 | /api/v1/analysis/run + SSE 進度 | ⬜ |
| 2.4 | /api/v1/analysis/top-picks + history | ⬜ |
| 2.5 | /api/v1/portfolio buy/sell/holdings/pnl | ⬜ |
| 2.6 | /api/v1/backtest/run + results | ⬜ |
| 2.7 | /sse/progress 即時推送 | ⬜ |

---

## Phase 3：前端 MVP

| # | 任務 | 狀態 |
|---|------|------|
| 3.1 | Next.js 初始化 + Tailwind + shadcn/ui | ⬜ |
| 3.2 | 全域 Layout (Sidebar + 深色主題) | ⬜ |
| 3.3 | API Client + TypeScript 型別 | ⬜ |
| 3.4 | useSSE hook | ⬜ |
| 3.5 | Dashboard — Top Picks 卡片 + 分析進度條 | ⬜ |
| 3.6 | Dashboard — 市場概覽 + 持倉快照 + 警報 | ⬜ |
| 3.7 | 股票列表頁（表格 + 排序 + 篩選）| ⬜ |

---

## Phase 4：圖表與詳情

| # | 任務 | 狀態 |
|---|------|------|
| 4.1 | Lightweight Charts — K 線 + 成交量 | ⬜ |
| 4.2 | 技術指標疊圖 (MA / BB / RSI / MACD) | ⬜ |
| 4.3 | 股票詳情頁完整整合 | ⬜ |
| 4.4 | 分析分數歷史趨勢圖 | ⬜ |

---

## Phase 5：投資組合

| # | 任務 | 狀態 |
|---|------|------|
| 5.1 | 持倉總覽頁面 | ⬜ |
| 5.2 | 交易紀錄頁面 | ⬜ |
| 5.3 | 買入/賣出表單 Modal | ⬜ |
| 5.4 | 停損/停利警報顯示 | ⬜ |

---

## Phase 6：回測視覺化

| # | 任務 | 狀態 |
|---|------|------|
| 6.1 | 回測觸發頁面 + 參數表單 | ⬜ |
| 6.2 | 回測結果圖表（資金曲線、勝率） | ⬜ |
| 6.3 | 策略最佳化（權重 grid search 結果） | ⬜ |

---

## Phase 7：收尾部署

| # | 任務 | 狀態 |
|---|------|------|
| 7.1 | Docker Compose (PG + Backend + Frontend) | ⬜ |
| 7.2 | 設定頁面（股票管理 / 參數） | ⬜ |
| 7.3 | 錯誤處理 + Loading states | ⬜ |

---

## 技術決策紀錄

| 日期 | 決策 | 原因 |
|------|------|------|
| 2026-04-04 | Next.js 14 + TypeScript | SSR + 成熟生態 |
| 2026-04-04 | FastAPI + asyncpg | Python 基礎 + async |
| 2026-04-04 | SSE 即時推送 | 單向推送足夠，比 WS 簡單 |
| 2026-04-04 | PostgreSQL 15 | JSONB + 擴展性 |
| 2026-04-04 | Lightweight Charts | TradingView K 線，免費開源 |
| 2026-04-04 | APScheduler | 輕量排程，不需 Celery |
| 2026-04-04 | 回測整合至核心 | 驗證推薦系統有效性 |
