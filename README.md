# Money Printer — SMC 股票分析系統

自動化美股 / 台股分析系統，基於 Smart Money Concepts (SMC) + 多時間框架 (MTF) 結構分析，提供分層決策與倉位管理建議。整合 KingArmy Trade Memory Engine，將每次回測結果轉化為可查詢的交易記憶。


## 功能特色

- **SMC 結構分析** — Order Block、Fair Value Gap、市場結構自動辨識
- **多時間框架 (MTF)** — 日線 / 週線 / 月線趨勢對齊，高時間框架否決權
- **分層決策引擎** — 5 條件計數（SMC + 動量 + 催化劑 + R:R + MTF），決定推薦等級
- **綜合分 v3** — 條件分(0\~50) + 風報比分(0\~30) + 位置分(0\~20) = 真實交易品質
- **即時報價** — 手動觸發 yfinance 盤中報價
- **持倉管理** — 買入 / 賣出 / 損益追蹤 / 自動停損停利
- **新聞情緒** — RSS 自動抓取 + 情緒分析作為催化劑
- **AI 分析筆記** — 儲存每次分析記錄，追蹤歷史推薦、勝率追蹤（`actual_return_pct`）
- **VectorBT 回測** — Dashboard 內建策略回測（SMC、動量突破、爆發掃描），向量化引擎
- **回測迭代 Pipeline** — 多輪訓練/驗證週期，自動收斂，支援即時停止
- **Trade Memory Engine** — VBT 回測結果自動轉換為交易記憶，向量查詢勝率統計
- **記憶儀表板** — 前端可視化記憶摘要、跨市場統計、決策表
- **Telegram 通知** — 推送分析結果到手機

## 技術棧

| 層級 | 技術 |
|------|------|
| 後端 | FastAPI + SQLAlchemy 2.0 (async) + asyncpg |
| 資料庫 | PostgreSQL 15（共用 `~/.kingarmy/db/`，port 54330）|
| 前端 | Next.js 16 + TypeScript + Tailwind CSS v4 |
| 資料源 | yfinance（美股）+ TWSE 官方 API（台股歷史數據）|
| 回測引擎 | VectorBT（向量化，防前視偏誤）|
| 記憶引擎 | KingArmy Trade Memory Engine（HTTP Client）|
| Python | 3.11（建議用 conda 管理）|

## 系統架構

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend                               │
│                  Next.js 16 (:3000)                           │
│   K線圖 / SMC / 即時報價 / 持倉 / Pipeline / 記憶儀表板      │
└──────────────────────┬───────────────────────────────────────┘
                       │ REST API
┌──────────────────────▼───────────────────────────────────────┐
│                        Backend                                │
│                  FastAPI (:8000)                               │
│                                                               │
│  ┌─────────┐ ┌──────────┐ ┌───────────┐ ┌────────────────┐  │
│  │ SMC     │ │ 動量分析  │ │ 新聞情緒  │ │ 回測 Pipeline  │  │
│  │ 結構    │ │ RSI/MACD │ │ Sentiment │ │ VBT 多輪迭代   │  │
│  │ OB/FVG  │ │ MA/BB    │ │           │ │ stop/cancel    │  │
│  └────┬────┘ └────┬─────┘ └─────┬─────┘ └───────┬────────┘  │
│       └───────────┼─────────────┘               │            │
│                   ▼                             │            │
│          ┌────────────────┐                     ▼            │
│          │  分層決策引擎   │         ┌────────────────────┐   │
│          │  5 條件計數     │         │  Memory Converter  │   │
│          │  綜合分 v3     │         │  VBT → 記憶格式     │   │
│          └────────────────┘         └─────────┬──────────┘   │
└──────────────────────┬──────────────────────────┼────────────┘
                       │                          │ HTTP
                ┌──────▼──────┐          ┌────────▼───────────┐
                │ PostgreSQL  │          │ Trade Memory Engine │
                │ 15 (:54330) │          │ KingArmy (:8001)    │
                │ ~/.kingarmy │          │ 向量查詢 + 決策表    │
                └─────────────┘          └────────────────────┘
```

## 分析策略

```
Layer 0: MTF 多時間框架（門檻）
  三重下降 / 逆勢反彈 → 直接排除

Layer 1: SMC 日線結構（方向）
  上升結構 → 通過
  盤整     → 降級
  下降結構 → 排除（高時間框架上升則觀察）

Layer 2: 動量確認
  MACD 30% + MA 25% + RSI 20% + Vol 15% + BB 10%

Layer 3: 催化劑（新聞情緒）
  正面(≥65) → +1 條件
  負面(≤35) → -1 條件

Layer 4: R:R 風報比
  ≥ 2.0 → +1 條件

Layer 5: MTF 對齊
  高信心 + 正面 → +1 條件

條件計數 → 推薦等級：
  5 條件 → 強力推薦 / 核心持倉 (15-20%)
  4 條件 → 強力推薦 / 核心持倉
  3 條件 → 推薦 / 標準倉位 (8-12%)
  2 條件 → 觀察 / 探索倉位 (3-5%)
  < 2    → 不推薦
```

## 安裝指南

### 1. 前置需求

- Python 3.11+
- Node.js 20+
- Conda（建議）或 venv

> **不需要手動安裝 PostgreSQL。** 系統預設會自動啟動內建的 PostgreSQL（資料存放於 `~/.kingarmy/db/`，port 54330，與 KingArmy Trade Memory Engine 共用）。如需連接外部資料庫，請見「進階設定」。

### 2. Clone 專案

```bash
git clone https://github.com/Ssidss/money_printer.git money_printer
cd money_printer
```

### 3. 建立 Python 環境

```bash
# 用 conda（推薦）
conda create -n money_printer python=3.11 -y
conda activate money_printer

# 安裝後端依賴
pip install -r backend/requirements.txt
```

### 4. 安裝前端依賴

```bash
cd frontend
npm install
cd ..
```

### 5. 啟動

開兩個 terminal：

```bash
# Terminal 1: 後端（首次啟動會自動建立 DB + 資料表）
conda activate money_printer
python main.py

# Terminal 2: 前端
cd frontend
npm run dev
```

啟動後：
- **後端 API**：http://localhost:8000
- **API 文件**：http://localhost:8000/docs
- **前端 UI**：http://localhost:3000

> **首次啟動說明**：後端啟動時會自動完成以下步驟：
> 1. 偵測系統 PostgreSQL，若找不到則啟動內建版本
> 2. 建立 `money_printer` 資料庫
> 3. 建立所有資料表並執行遷移
> 4. 匯入預設股票清單

### 進階設定（選填）

預設情況下不需要任何環境變數。如需自訂，在專案根目錄建立 `.env`：

```env
# 使用外部 PostgreSQL（設定後不啟動內建 DB）
DB_HOST=your-db-host
DB_PORT=5432
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=money_printer

# Telegram 通知
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Discord 通知
DISCORD_WEBHOOK_URL=

# 生產環境必須設定
SECRET_KEY=your-secret-key
ENVIRONMENT=production
```

> **AUTO_DB 邏輯**：當 `DB_HOST` 為空或未設定時，系統自動啟動內建 PostgreSQL（`~/.kingarmy/db/`，port 54330）。設定外部 `DB_HOST` 後即停用 AUTO_DB。

## 操作指南

### 初次使用

啟動後系統會自動建立資料表並初始化股票清單。接下來需要手動觸發股價抓取：

```bash
# 抓取所有股票的歷史股價（5 年）
curl -X POST "http://localhost:8000/api/v1/stocks/batch-fetch?days=1825"

# 或只抓單支（快速測試）
curl -X POST "http://localhost:8000/api/v1/stocks/NVDA/fetch?days=365"
```

### 執行分析

```bash
# 分析全部股票
curl -X POST http://localhost:8000/api/v1/analysis/run

# 分析單支（同步，等結果回傳）
curl -X POST http://localhost:8000/api/v1/stocks/NVDA/analyze/sync

# 取得最新分析結果
curl http://localhost:8000/api/v1/analysis/latest
```

### 即時報價

```bash
# 單支即時報價
curl http://localhost:8000/api/v1/stocks/NVDA/realtime

# 全部追蹤股票即時報價
curl http://localhost:8000/api/v1/stocks/realtime
```

### 持倉管理

```bash
# 買入
curl -X POST http://localhost:8000/api/v1/portfolio/buy \
  -H "Content-Type: application/json" \
  -d '{"ticker": "NVDA", "shares": 5, "price": 180.00}'

# 賣出
curl -X POST http://localhost:8000/api/v1/portfolio/sell \
  -H "Content-Type: application/json" \
  -d '{"ticker": "NVDA", "shares": 2, "price": 200.00}'

# 查看持倉
curl http://localhost:8000/api/v1/portfolio
```

### 開盤速報

```bash
# 取得開盤速報（含 MTF 分析 + 持倉健檢）
curl http://localhost:8000/api/v1/briefing/morning
```

### 前端 UI 操作

在個股頁面可以：
- **⚡ 即時報價** — 點擊查詢盤中價格
- **📥 更新股價** — 補齊最新日線資料
- **📅 自訂回補** — 選擇回補 7 天 ~ 5 年的歷史股價
- **🔄 重新分析** — 觸發分析並刷新頁面
- **日線 / 週線 / 月線** — K 線圖切換時間框架
- **3M / 6M / 1Y / 2Y / 5Y** — K 線圖切換顯示區間

### SMC 圖表標記

K 線圖上會自動標記：
- 🟢 **Bullish OB**（綠色區域）— 機構買入區，支撐
- 🔴 **Bearish OB**（紅色區域）— 機構賣出區，壓力
- 🟣 **FVG**（紫色區域）— 價值缺口，市場有機率回補
- 📍 **HH / HL / LH / LL** — 結構高低點標記

## API 端點一覽

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/v1/stocks` | GET | 所有追蹤的股票 |
| `/api/v1/stocks/{ticker}` | GET | 單支股票資訊 |
| `/api/v1/stocks/{ticker}/prices` | GET | 歷史股價（支援 `?timeframe=weekly`) |
| `/api/v1/stocks/{ticker}/smc` | GET | SMC 結構分析 |
| `/api/v1/stocks/{ticker}/realtime` | GET | 即時報價 |
| `/api/v1/stocks/realtime` | GET | 全部即時報價 |
| `/api/v1/stocks/smc-trends` | GET | 所有股票 MTF 趨勢 |
| `/api/v1/stocks/{ticker}/fetch` | POST | 抓取股價 |
| `/api/v1/stocks/{ticker}/analyze/sync` | POST | 同步分析 |
| `/api/v1/stocks/batch-fetch` | POST | 批次抓取股價 |
| `/api/v1/analysis/latest` | GET | 最新分析結果 |
| `/api/v1/analysis/run` | POST | 執行全部分析 |
| `/api/v1/portfolio` | GET | 查看持倉 |
| `/api/v1/portfolio/buy` | POST | 買入 |
| `/api/v1/portfolio/sell` | POST | 賣出 |
| `/api/v1/briefing/morning` | GET | 開盤速報 |
| `/api/v1/ai-notes` | POST | 儲存 AI 分析筆記 |
| `/api/v1/ai-notes/{ticker}` | GET | 查看 AI 筆記（含勝率追蹤）|
| `/api/v1/backtest/vbt/run` | POST | 執行 VectorBT 策略回測 |
| `/api/v1/backtest/vbt/strategies` | GET | 查詢可用回測策略清單 |
| `/api/v1/pipeline/run` | POST | 啟動回測迭代 Pipeline |
| `/api/v1/pipeline/status` | GET | 查詢 Pipeline 執行狀態 |
| `/api/v1/pipeline/report` | GET | 取得 Pipeline 驗證報告 |
| `/api/v1/pipeline/stop` | POST | 停止執行中的 Pipeline |

## 自訂股票清單

編輯 `backend/app/config.py` 中的 `US_STOCKS` 和 `TW_STOCKS`：

```python
US_STOCKS: list[str] = [
    "AAPL", "NVDA", "TSLA",  # 加入你想追蹤的
]
TW_STOCKS: list[str] = [
    "2330", "2454",  # 台股用代號
]
```

重啟後端即可生效。

## 綜合分解讀

| 分數 | 等級 | 倉位 | 含義 |
|------|------|------|------|
| 80-100 | 強力推薦 | 核心 15-20% | 條件全中，極佳機會 |
| 60-79 | 推薦 | 標準 8-12% | 條件 + R:R 不錯 |
| 40-59 | 觀察 | 探索 3-5% | 部分條件缺失 |
| 20-39 | 不推薦 | 不碰 | 結構不對或 R:R 太差 |
| 0-19 | 危險 | 快跑 | 三重下降 / 已破停損 |

## 每日操作流程

```
1. 盤前：跑一次 /analysis/run 更新全部分析
2. 看綜合分排名，找推薦 + 標準倉位以上的股票
3. 用即時報價確認現價是否接近買入區
4. 碰到關鍵價位才操作，沒碰到就不動
5. 每週跑一次完整 MTF 分析確認大趨勢
```

## 性能優化 (KINA-246)

### 開盤速報 (briefing) 查詢最佳化

**問題**：`/api/v1/briefing/morning` 端點存在 N+1 查詢問題
- 每個持倉觸發多次序列查詢
- 10 支持倉 = 30+ 次獨立 DB 查詢
- 影響開盤速報載入速度

**解決方案**：
- ✅ 採用 batch fetch + window function 重構查詢邏輯
- ✅ 市場指標查詢改用 `ROW_NUMBER() OVER (PARTITION BY stock_id)` 實現每支股票獨立取前 2 筆
- ✅ AI 筆記採用 subquery join，一次性載入所有相關記錄

**效果**：
- 查詢次數：30+ → ≤10 次（減少 67% 以上）
- 端點響應時間：顯著縮短
- 資料準確性：保持不變

**驗證**：
```bash
# 使用 test_briefing_perf.py 驗證查詢計數 ≤ 10
python -m pytest tests/test_briefing_perf.py -v
```

相關 commit：
- 5ad2ae3: 技術審查員反饋修正
- 721cfec: 測試 fixture 補充

## License

Private — 僅供內部使用
