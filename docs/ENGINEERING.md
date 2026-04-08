# Money Printer 工程重構規格書

> 版本：v1.2 | 2026-04-08
> 對應策略書：STRATEGY.md v5.0
> 決策：**後端 SMC 引擎打掉重練 + 前端大幅重構**
> v1.1 變更：新增 §十~§十九，解決 10 項工程問題（統一 Schema、時間對齊、快取、回測一致性、狀態管理、錯誤處理、前端效能、Intraday 安全、測試計畫、決策優先級）
> v1.2 變更：新增 §廿一~§三十，解決 10 項 production 工程問題（Analysis Pipeline、Async Job、分層快取、增量更新、資料版本控制、Decision 確定性、Chart 效能強化、Correlation 批次、回測 slippage/fee、Observability）

---

## 一、重構 vs 重練判斷

### 後端各模組判斷

| 模組 | 現有代碼 | 決策 | 理由 |
|------|---------|------|------|
| `smc.py` (872行) | OB 門檻 1%、無 Fibonacci、無流動性、無 CHoCH/MSS、trend 只看 2 點 | ❌ **打掉重練** | 核心邏輯完全不符合 v5.0 策略，改不如重寫 |
| `technical.py` (254行) | RSI/MACD/MA/BB 加權評分 | ❌ **刪除** | v5.0 策略不使用傳統 TA 指標 |
| `recommender.py` (430行) | 分層決策但依賴 technical score | ❌ **打掉重練** | 需要改為純 SMC + 情緒的決策引擎 |
| `fetcher.py` (310行) | yfinance 抓歷史+即時報價 | ✅ **保留** | 資料抓取邏輯正確，加 intraday 支援即可 |
| `sentiment.py` (58行) | 情緒聚合 | ⚠️ **改寫** | 需要加 EMA slope、反向指標邏輯 |
| `news_crawler.py` (144行) | 新聞爬取 | ✅ **保留** | 功能正常 |
| `backtester.py` (389行) | 回測引擎 | ⚠️ **大改** | 保留框架，改為 SMC 信號驅動 |
| `telegram.py` (133行) | 通知推送 | ✅ **保留** | 不影響 |
| 資料模型 | Stock, PriceHistory, Analysis, Portfolio, Backtest, AiNote | ⚠️ **擴展** | 保留現有表，新增 SMC 相關欄位 |
| API 路由 | 完整 CRUD | ⚠️ **擴展** | 保留現有端點，新增 SMC v2 端點 |

### 前端判斷

| 模組 | 決策 | 理由 |
|------|------|------|
| `StockChart.tsx` | ⚠️ **大改** | 需要支援多時間框架、SMC 標記開關、Fibonacci 繪製 |
| `ChartControls.tsx` | ⚠️ **大改** | 需要更多時間框架、圖層開關面板 |
| Dashboard (`page.tsx`) | ⚠️ **改寫** | 改為 SMC 驅動的 Dashboard |
| 股票列表 | ⚠️ **改寫** | 加排序、篩選、SMC 趨勢顯示 |
| 其他組件 | ✅ **保留** | Portfolio、Backtest、AI Notes 框架可用 |

### 結論

```
打掉重練：smc.py, technical.py（刪除）, recommender.py
大改/擴展：backtester.py, sentiment.py, 前端圖表, 前端列表, Dashboard
保留：fetcher.py, news_crawler.py, telegram.py, 資料模型（擴展）, API 路由（擴展）
```

---

## 二、新架構設計

### 後端模組架構

```
backend/app/services/
├── smc/                          # ← 全新 SMC 引擎（拆分模組）
│   ├── __init__.py               # run_smc_analysis_v2() 整合入口
│   ├── structure.py              # Swing Points + Trend + BOS/CHoCH/MSS
│   ├── order_block.py            # OB 偵測（連續評分+去重+decay）
│   ├── fvg.py                    # FVG 偵測（6 級狀態+CE+decay）
│   ├── liquidity.py              # EQH/EQL + Sweep（ATR 自適應+liq_score）
│   ├── fibonacci.py              # Premium/Discount/OTE（leg scoring）
│   ├── regime.py                 # Market Regime Detection
│   └── helpers.py                # ATR 計算、resample、共用工具
│
├── decision/                     # ← 全新決策引擎
│   ├── __init__.py               # run_decision() 入口
│   ├── entry.py                  # 進場建議（整合 SMC 全模組）
│   ├── sentiment_gate.py         # 情緒紅綠燈（EMA slope + 反向指標）
│   ├── mtf_gate.py               # 多時間框架決策矩陣
│   ├── position_sizer.py         # 倉位計算（regime-aware）
│   └── portfolio_risk.py         # Correlation + Portfolio Heat
│
├── fetcher.py                    # 保留，擴展 intraday
├── sentiment.py                  # 改寫
├── news_crawler.py               # 保留
├── backtester.py                 # 大改
└── telegram.py                   # 保留
```

### 前端頁面架構

```
frontend/src/app/
├── page.tsx                      # Dashboard（重寫）
├── layout.tsx                    # 保留
├── stocks/
│   ├── page.tsx                  # 股票列表（重寫）
│   └── [ticker]/
│       └── page.tsx              # 個股詳情（大改）
├── portfolio/
│   └── page.tsx                  # 保留
├── backtest/
│   └── page.tsx                  # 保留（改接 SMC 信號）
└── briefing/
    └── page.tsx                  # 保留

frontend/src/components/
├── chart/                        # ← 全新圖表組件
│   ├── SmcChart.tsx              # 主圖表（取代 StockChart.tsx）
│   ├── ChartToolbar.tsx          # 時間框架 + 圖層開關
│   ├── overlays/
│   │   ├── OrderBlockOverlay.tsx # OB 繪製（帶評分星級）
│   │   ├── FvgOverlay.tsx        # FVG 繪製（帶 CE 中線）
│   │   ├── FibonacciOverlay.tsx  # Fibonacci + OTE 區域
│   │   ├── LiquidityOverlay.tsx  # EQH/EQL + Sweep 標記
│   │   ├── StructureOverlay.tsx  # BOS/CHoCH/MSS 標記
│   │   └── VolumeProfile.tsx     # Volume Profile（保留改進）
│   └── FullscreenWrapper.tsx     # 全螢幕容器（保留改進）
│
├── dashboard/                    # 重寫
│   ├── MarketOverview.tsx        # 大盤 SMC 結構一覽
│   ├── TopPicks.tsx              # SMC 驅動的推薦卡片
│   ├── PortfolioHealth.tsx       # 持倉健檢 + Portfolio Heat
│   ├── RegimeBadge.tsx           # 市場狀態徽章
│   └── AiBriefing.tsx            # AI 盤前/盤後分析區塊
│
├── stocks/                       # 重寫
│   ├── StockList.tsx             # 股票列表（排序+篩選+搜尋）
│   ├── StockRow.tsx              # 單行顯示（SMC 趨勢+信號）
│   ├── StockFilters.tsx          # 篩選器（台/美股、趨勢、推薦等級）
│   └── AddStockModal.tsx         # 保留
│
├── stock/                        # 大改
│   ├── StockDetail.tsx           # 個股總覽（整合所有 SMC 資訊）
│   ├── SmcSummary.tsx            # SMC 結構摘要卡片
│   ├── EntryPlan.tsx             # 進場計畫卡片（進場/停損/目標/R:R）
│   ├── SentimentGauge.tsx        # 情緒紅綠燈
│   └── AiNotes.tsx               # 保留
│
├── portfolio/                    # 保留 + 擴展
│   ├── PortfolioClient.tsx
│   ├── CorrelationMatrix.tsx     # ← 新增
│   └── SectorExposure.tsx        # ← 新增
│
└── layout/
    └── Sidebar.tsx               # 保留
```

---

## 三、時間框架與數據需求

### 時間框架對照表

| 時間框架 | 代號 | 數據來源 | K 棒數量 | 用途 |
|---------|------|---------|---------|------|
| **月線** | `monthly` | 日線 resample | 60 根（5 年） | HTF 大方向 |
| **週線** | `weekly` | 日線 resample | 104 根（2 年） | HTF 趨勢確認 |
| **日線** | `daily` | yfinance EOD | 500 根（2 年） | MTF 主要分析 |
| **4 小時** | `4h` | yfinance intraday | 120 根（20 天） | LTF 進場精確 |
| **1 小時** | `1h` | yfinance intraday | 200 根（8 天） | LTF MSS 觸發 |
| **30 分鐘** | `30m` | yfinance intraday | 200 根（4 天） | LTF 精確進場 |
| **15 分鐘** | `15m` | yfinance intraday | 200 根（2 天） | LTF 極精確 |

### SMC 各模組所需時間框架

```
結構趨勢 (Structure):
  分析: 月線 + 週線 + 日線（MTF 決策矩陣）
  圖表顯示: 用戶選擇的任一時間框架

Fibonacci / OTE:
  計算: 用戶當前查看的時間框架
  顯示: 標注在該時間框架的圖表上

Order Block:
  偵測: 每個時間框架獨立計算
  顯示: 當前時間框架 + 可選顯示 HTF OB（用不同透明度）

FVG:
  偵測: 每個時間框架獨立計算
  顯示: 當前時間框架

Liquidity (EQH/EQL):
  偵測: 日線為主（流動性池在較大時間框架更有意義）
  顯示: 所有時間框架（水平線穿越）

LTF Entry Trigger:
  日線標記 Demand Zone → 切到 1H/4H 等 MSS
  需要: 1H 數據（P2 優先級，初版可不做）
```

### yfinance Intraday 限制

```
yfinance intraday 數據限制：
  1m:  最多 7 天
  2m:  最多 60 天
  5m:  最多 60 天
  15m: 最多 60 天
  30m: 最多 60 天
  60m: 最多 730 天（2 年）
  90m: 最多 60 天

建議策略：
  P0: 日線 + 週線 + 月線（resample，無額外 API 需求）
  P1: 加 1H（yfinance 支援 2 年回溯，足夠）
  P2: 加 4H（從 1H resample）
  P3: 加 15m / 30m（用於 LTF entry trigger）

儲存策略：
  日線: 存 DB（已有）
  週線/月線: 從日線 resample，不存 DB
  1H: 存 DB（新增 PriceHistoryIntraday 表，或用 timeframe 欄位區分）
  15m/30m: 不存 DB，按需抓取
```

---

## 四、圖表功能規格

### 4.1 時間框架切換

```
工具列排列：
  [15m] [30m] [1H] [4H] | [日] [週] [月]
  ─────────────────────   ───────────────
  LTF（P2，初版可隱藏）    MTF（P0，必須有）

  日/週/月 預設顯示
  15m~4H 初版可用 coming soon 灰色標記，P1/P2 實作
```

### 4.2 SMC 圖層開關面板

```
圖表右上角的圖層面板（checkbox 列表）：

  📊 SMC 圖層
  ┌────────────────────────────────────┐
  │ ☑ Order Block（多頭 / 空頭）       │  ← 綠色/紅色半透明矩形
  │   顯示評分: ☑                      │  ← OB 上方標注 score
  │ ☑ FVG（多頭 / 空頭）              │  ← 藍色/橙色半透明矩形
  │   顯示 CE 中線: ☑                  │  ← FVG 中間的虛線
  │ ☑ Fibonacci / OTE                 │  ← 水平線 + OTE 半透明色帶
  │ ☑ 流動性 (EQH/EQL)               │  ← 虛線 + 觸及次數標注
  │ ☐ Sweep 標記                      │  ← ⚡ 圖標（預設關）
  │ ☑ BOS / CHoCH / MSS              │  ← 箭頭 + 文字標記
  │ ☑ Volume Profile                  │  ← 右側直方圖
  │ ☐ Premium / Discount 背景色       │  ← 紅/綠半透明背景（預設關）
  └────────────────────────────────────┘

  每個圖層獨立開關
  設定保存在 localStorage，下次開啟記住偏好
```

### 4.3 圖層視覺規格

```
Order Block:
  Bullish: 綠色半透明矩形 rgba(34,197,94,0.15)
           上方標注 "OB 7.2★" 或 "OB ★★★☆"
           mitigated 的用灰色虛線框
  Bearish: 紅色半透明矩形 rgba(239,68,68,0.15)

FVG:
  Bullish: 藍色半透明 rgba(99,102,241,0.12)
           CE 中線用藍色虛線
           狀態標注: Active / Respected / Violated
  Bearish: 橙色半透明 rgba(249,115,22,0.12)

Fibonacci:
  水平線: 0.0, 0.236, 0.382, 0.5, 0.618, 0.705, 0.786, 1.0
  OTE 區域: 金色半透明帶 rgba(245,158,11,0.10)
  Equilibrium (0.5): 黃色虛線，標注「均衡」
  各水位標注比例數字

EQH/EQL:
  水平虛線 + 標注 "EQH ×3" 或 "EQL ×2"（觸及次數）
  BSL 用紅色虛線（上方），SSL 用綠色虛線（下方）
  已被 swept 的用半透明 + 刪除線

BOS/CHoCH/MSS:
  BOS: 小箭頭 + "BOS" 文字（順勢方向顏色）
  CHoCH: 三角警告 + "CHoCH" 文字（黃色）
  MSS: 大箭頭 + "MSS" 文字（紅色或綠色）

Premium/Discount 背景:
  Premium 區: 淡紅色背景 rgba(239,68,68,0.05)
  Discount 區: 淡綠色背景 rgba(34,197,94,0.05)
  分界線 Equilibrium 加重顯示

Volume Profile:
  保留現有邏輯
  POC 線加粗 + 標注
  Value Area 範圍標注
```

### 4.4 圖表交互

```
放大/縮小:
  滑鼠滾輪 zoom in/out
  拖拽平移
  雙擊重置視野

全螢幕:
  保留現有 ⛶ 按鈕 + ESC 退出
  全螢幕時圖層面板保持可用

Crosshair 資訊:
  十字游標移動時，右側/下方顯示：
  - 日期、OHLCV
  - 所在 Fibonacci 區域（Premium/Discount/OTE）
  - 所在 OB/FVG 資訊（如果有）

點擊 OB/FVG:
  點擊圖表上的 OB/FVG 區塊 → 彈出小 tooltip：
  - OB: score, confirmations, 回測次數, 形成日期
  - FVG: 狀態, CE 價位, displacement 強度, 形成日期
```

---

## 五、頁面功能規格

### 5.1 Dashboard（首頁）

```
┌─────────────────────────────────────────────────────────┐
│  Money Printer Dashboard                                 │
├─────────────┬───────────────┬───────────┬───────────────┤
│ 市場狀態     │ 持倉數 / 追蹤數 │ Portfolio │ 最後分析時間   │
│ Trending 🟢 │ 4 / 38        │ Heat 3.2% │ 2 小時前      │
├─────────────┴───────────────┴───────────┴───────────────┤
│                                                          │
│  📊 大盤 SMC 結構                                        │
│  ┌──────────┬──────────┬──────────┐                     │
│  │ SPY      │ QQQ      │ 台加權    │                     │
│  │ 日↑ 週↑  │ 日↑ 週↑  │ 日↑ 週↑  │                     │
│  │ BOS 4/3  │ BOS 4/5  │ BOS 4/2  │                     │
│  └──────────┴──────────┴──────────┘                     │
│                                                          │
│  ⭐ Top 3 推薦                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 1. MRVL  OB@105.20  R:R 3.8  核心倉  情緒 62 ↑  │   │
│  │ 2. TSM   OB@328.50  R:R 2.4  標準倉  情緒 55 →  │   │
│  │ 3. ARM   等回調     -        觀望    情緒 71 →   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  💼 持倉健檢                                             │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 股票 │ 成本  │ 現價  │ P&L%  │ SMC結構│ 動作建議  │   │
│  │ AMD  │ 217.8 │ 222.1 │ +2.0% │ ↑ BOS │ 持有     │   │
│  │ NVDA │ 179.7 │ 185.3 │ +3.1% │ ↑ BOS │ 持有     │   │
│  │ MRVL │ 108.6 │ 110.2 │ +1.5% │ ↑ OB  │ 等加倉   │   │
│  │ TSM  │ 340.0 │ 335.5 │ -1.3% │ 盤整  │ 觀察     │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  🤖 AI 分析                                              │
│  ┌──────────────────────────────────────────────────┐   │
│  │ [盤前速看] [盤後分析] [觸發完整分析]               │   │
│  │                                                    │   │
│  │ 最新 AI 分析摘要顯示區...                           │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 5.2 股票列表頁

```
┌──────────────────────────────────────────────────────────┐
│  追蹤股票                                    [+ 新增股票] │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  篩選: [全部 ▼] [美股 | 台股]  [上升 | 盤整 | 下降]      │
│  搜尋: [輸入代號或名稱...]                                │
│  排序: [SMC 評分 ▼] [名稱] [趨勢] [R:R] [情緒]          │
│                                                          │
│  ┌────┬───────┬───────┬──────┬────┬──────┬─────┬──────┐ │
│  │排名│ 代號   │ 現價   │ SMC  │趨勢│ R:R  │情緒 │ 推薦  │ │
│  ├────┼───────┼───────┼──────┼────┼──────┼─────┼──────┤ │
│  │ 1  │ MRVL  │ 110.2 │ 7.8  │ ↑  │ 3.8  │ 62↑│ 核心  │ │
│  │ 2  │ TSM   │ 335.5 │ 6.2  │ ─  │ 2.4  │ 55→│ 標準  │ │
│  │ 3  │ ARM   │ 149.1 │ 5.5  │ ↑  │ -    │ 71→│ 觀望  │ │
│  │ 4  │ NVDA  │ 185.3 │ 4.8  │ ↑  │ 1.9  │ 58→│ 觀望  │ │
│  │ ...│       │       │      │    │      │    │      │ │
│  │ 38 │ 2330  │ 890   │ 3.2  │ ─  │ -    │ 45↓│ 不推薦│ │
│  └────┴───────┴───────┴──────┴────┴──────┴─────┴──────┘ │
│                                                          │
│  SMC 評分 = entry_quality（0-10）                         │
│  趨勢: ↑(上升) ↗(弱上升) ─(盤整) ↓(下降)                │
│  情緒: 數字 + 方向箭頭（↑回升 →穩定 ↓惡化）              │
│  推薦: 根據決策矩陣輸出（核心/標準/探索/觀望/不推薦）      │
│                                                          │
│  點擊任一行 → 進入個股詳情頁                              │
└──────────────────────────────────────────────────────────┘
```

### 5.3 個股詳情頁

```
┌──────────────────────────────────────────────────────────┐
│  ← 返回  MRVL - Marvell Technology     ⚡ 即時報價 $110.2│
│  ┌──────────────────────────────────────────────────┐   │
│  │ [📥 更新股價] [📅 回補] [🔄 重新分析]              │   │
│  └──────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─ SMC 摘要卡片 ──────────────────────────────────────┐│
│  │ 結構: 上升 ↑ (HH+HL 3/4) │ Regime: Trending        ││
│  │ 最近事件: Bullish BOS (4/3) │ MTF: 月↑ 週↑ 日↑     ││
│  │ 區域: Discount (Fib 0.42) │ 倉位上限: 核心 20%      ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  ┌─ 進場計畫卡片 ──────────────────────────────────────┐│
│  │ 進場: $105.20 (OB 上緣, score 7.8/10)               ││
│  │ 停損: $103.10 (OB 底部 - ATR buffer)                ││
│  │ 目標1: $128.50 (BSL/EQH ×3)  │ 目標2: $132 (Bear OB)││
│  │ R:R: 11.1  │ 風險: 2.0%  │ 獲利潛力: 22.1%         ││
│  │ 情緒: 62/100 ↑ (利空消化中)  │ 紅綠燈: 🟢 可執行     ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  ┌─ 圖表 ──────────────────────────────────── [⛶ 放大]┐│
│  │ [15m][30m][1H][4H] | [日][週][月]  │ 📊 圖層 ▼     ││
│  │ [3M][6M][1Y][2Y][5Y][全部]         │               ││
│  │                                                      ││
│  │  ┌──────────────────────────────────────────────┐   ││
│  │  │                                              │   ││
│  │  │         K 線圖 + SMC 標記                     │   ││
│  │  │         (OB / FVG / Fib / EQH / BOS...)      │   ││
│  │  │                                              │   ││
│  │  │                                              │   ││
│  │  └──────────────────────────────────────────────┘   ││
│  │  成交量柱狀圖                                        ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  ┌─ AI 分析筆記 ───────────────────────────────────────┐│
│  │ [最新] 2026-04-08 14:30                              ││
│  │ 推薦: 核心倉  │  動作: 等回調買入                     ││
│  │ 摘要: ...                                            ││
│  └──────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────┘
```

### 5.4 Briefing 頁（盤前速看 / 盤後分析）

```
由 LLM（Claude / GPT）讀取系統數據後生成，保存為 AI Note。

盤前速看內容：
  1. 大盤 SMC 結構 + 昨日事件
  2. 持倉健檢（誰接近停損/目標）
  3. 今日要注意的進場機會
  4. 重大事件提醒（FOMC、財報等）

盤後分析內容：
  1. 今日 SMC 結構變化（新 BOS/CHoCH/MSS？）
  2. OB/FVG 被 mitigated 的情況
  3. 流動性目標被 swept 的情況
  4. 持倉 P&L 更新
  5. 明日操作建議

存儲：調用 POST /api/v1/ai-notes 保存
顯示：在 Dashboard 和 Briefing 頁面顯示最新的
```

---

## 六、資料模型擴展

### 新增 / 修改的表

```sql
-- 擴展 AnalysisResult（或新建 SmcAnalysisResult）
ALTER TABLE analysis_results ADD COLUMN smc_version INTEGER DEFAULT 1;
ALTER TABLE analysis_results ADD COLUMN smc_data JSONB;  -- 完整 SMC 分析結果
ALTER TABLE analysis_results ADD COLUMN regime VARCHAR(20);  -- trending/ranging/high_vol/low_vol
ALTER TABLE analysis_results ADD COLUMN fibonacci_data JSONB;  -- Fibonacci 水位
ALTER TABLE analysis_results ADD COLUMN liquidity_data JSONB;  -- 流動性偵測結果
ALTER TABLE analysis_results ADD COLUMN entry_quality FLOAT;  -- 0-10 連續分

-- 新增 Intraday 數據表（如果要做 LTF）
CREATE TABLE price_history_intraday (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    timeframe VARCHAR(5),  -- '1h', '4h', '30m', '15m'
    datetime TIMESTAMP WITH TIME ZONE,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    volume BIGINT,
    UNIQUE(stock_id, timeframe, datetime)
);

-- Portfolio Correlation 快取（避免每次重算）
CREATE TABLE correlation_cache (
    id SERIAL PRIMARY KEY,
    date DATE,
    ticker_a VARCHAR(20),
    ticker_b VARCHAR(20),
    correlation FLOAT,
    window_days INTEGER DEFAULT 60,
    UNIQUE(date, ticker_a, ticker_b)
);
```

### API 新增端點

```
SMC v2:
  GET  /api/v2/stocks/{ticker}/smc          # 完整 SMC v2 分析（含 Fibonacci + 流動性 + regime）
  GET  /api/v2/stocks/{ticker}/smc/entry     # 只取進場建議
  GET  /api/v2/stocks/{ticker}/fibonacci     # Fibonacci 水位
  GET  /api/v2/stocks/{ticker}/liquidity     # 流動性偵測
  GET  /api/v2/stocks/{ticker}/structure     # 結構分析（BOS/CHoCH/MSS）
  GET  /api/v2/stocks/{ticker}/regime        # Market Regime

Decision:
  POST /api/v2/analysis/run                  # 觸發 v2 分析
  GET  /api/v2/analysis/top-picks            # SMC 驅動的推薦
  GET  /api/v2/analysis/mtf-matrix           # MTF 決策矩陣結果

Portfolio:
  GET  /api/v2/portfolio/correlation         # 相關性矩陣
  GET  /api/v2/portfolio/heat                # Portfolio Heat
  GET  /api/v2/portfolio/sector-exposure     # 產業曝險

Intraday (P1):
  POST /api/v2/stocks/{ticker}/fetch-intraday?timeframe=1h
  GET  /api/v2/stocks/{ticker}/prices-intraday?timeframe=1h&limit=200
```

---

## 七、實作優先級

### P0 — 核心 SMC 引擎（必須，2-3 週）

```
後端:
  Week 1:
    ☐ smc/helpers.py     — ATR, resample, 共用工具
    ☐ smc/structure.py   — Swing Points（含容差+去重）+ Trend（硬規則+弱趨勢）+ BOS/CHoCH/MSS
    ☐ smc/order_block.py — 嚴格 OB（連續評分+去重+decay+nested）

  Week 2:
    ☐ smc/fvg.py         — 嚴格 FVG（6 級狀態+CE+decay+分級）
    ☐ smc/liquidity.py   — EQH/EQL（ATR 自適應）+ Sweep + liq_score
    ☐ smc/fibonacci.py   — Premium/Discount/OTE（leg scoring）
    ☐ smc/__init__.py    — run_smc_analysis_v2() 整合

  Week 3:
    ☐ decision/entry.py          — 進場建議（整合全模組）
    ☐ decision/sentiment_gate.py — 情緒紅綠燈（EMA slope + 反向指標）
    ☐ decision/mtf_gate.py       — MTF 決策矩陣
    ☐ decision/position_sizer.py — 倉位計算
    ☐ API v2 端點

  驗證:
    ☐ 用 3 支股票人工驗證 SMC 輸出是否合理
    ☐ 與圖表工具（TradingView）交叉比對 OB/FVG 位置
```

### P1 — 前端圖表 + 列表（必須，2 週）

```
  Week 4:
    ☐ SmcChart.tsx        — 新版圖表組件（取代 StockChart）
    ☐ ChartToolbar.tsx    — 時間框架 + 圖層開關面板
    ☐ OrderBlockOverlay   — OB 繪製
    ☐ FvgOverlay          — FVG 繪製
    ☐ FibonacciOverlay    — Fibonacci + OTE 區域
    ☐ LiquidityOverlay    — EQH/EQL + Sweep

  Week 5:
    ☐ StructureOverlay    — BOS/CHoCH/MSS 標記
    ☐ StockList.tsx       — 新版列表（排序+篩選+搜尋）
    ☐ StockFilters.tsx    — 篩選器
    ☐ Dashboard 重寫      — MarketOverview + TopPicks + PortfolioHealth
    ☐ SmcSummary + EntryPlan + SentimentGauge 卡片
```

### P2 — Backtest + 進階（可選，2 週）

```
  Week 6:
    ☐ backtester.py 大改  — 改為 SMC 信號驅動
    ☐ smc/regime.py       — Market Regime Detection
    ☐ decision/portfolio_risk.py — Correlation + Portfolio Heat
    ☐ CorrelationMatrix.tsx / SectorExposure.tsx

  Week 7:
    ☐ Intraday 數據支援   — fetcher 擴展 + DB 表 + API
    ☐ 1H/4H 時間框架      — 圖表 + SMC 計算
    ☐ Visual Debug        — 交易覆盤標記
```

### P3 — 高級功能（未來）

```
  ☐ LTF Entry Integration（1H MSS trigger）
  ☐ ML ranking / adaptive tuning
  ☐ Execution Layer 實作
  ☐ Portfolio correlation dashboard
  ☐ 自動 Briefing 排程
```

---

## 八、技術選型確認

```
後端:
  語言: Python 3.11（conda env: money_printer）
  框架: FastAPI + SQLAlchemy 2.0 async + asyncpg
  資料庫: PostgreSQL 15
  數據源: yfinance（EOD + intraday）
  計算: NumPy / Pandas（SMC 引擎內部）
  測試: pytest + pytest-asyncio

前端:
  框架: Next.js 16 + TypeScript
  樣式: Tailwind CSS v4
  圖表: lightweight-charts（TradingView 開源版）
  打包: Webpack（非 Turbopack）
  啟動: /opt/homebrew/bin/node node_modules/.bin/next dev --webpack

部署:
  開發: 本地 Docker Compose（PostgreSQL）+ conda + next dev
  未來: Docker 全容器化
```

---

## 九、遷移策略

```
Step 1: 新建 smc/ 目錄，不動現有代碼
  - 新引擎在 /api/v2/ 下跑
  - 現有 /api/v1/ 保持運作
  - 前端可以同時調用 v1 和 v2

Step 2: 前端逐步切換
  - 圖表先接 v2 SMC 數據
  - 列表先接 v2 推薦數據
  - Dashboard 最後切

Step 3: 驗證 v2 輸出合理性
  - 人工比對至少 10 支股票
  - 與 TradingView 交叉驗證

Step 4: 清理
  - 確認 v2 穩定後刪除 technical.py
  - 將 v1 端點標記 deprecated
  - 最終移除 v1 相關代碼

好處：
  - 不會中斷現有功能
  - 可以 A/B 比較 v1 vs v2 的推薦品質
  - 出問題可以立刻回退到 v1
```

---

## 十、統一數據 Schema（SmcResult）

> 問題：各模組各自回傳 dict，沒有統一型別，下游消費者（decision engine、API、前端）無法信任欄位存在。

### 解法：定義 Pydantic 模型鏈

```python
# backend/app/schemas/smc.py

from pydantic import BaseModel
from enum import Enum
from typing import Optional

# ── 結構 ──
class TrendDirection(str, Enum):
    UP = "uptrend"
    WEAK_UP = "weak_uptrend"
    RANGING = "ranging"
    DOWN = "downtrend"

class SwingPoint(BaseModel):
    index: int
    date: str
    price: float
    type: str  # "HH" | "HL" | "LH" | "LL"

class StructureEvent(BaseModel):
    type: str  # "BOS" | "CHoCH" | "MSS"
    direction: str  # "bullish" | "bearish"
    date: str
    price: float
    displacement: Optional[float] = None

class StructureResult(BaseModel):
    trend: TrendDirection
    swing_points: list[SwingPoint]
    events: list[StructureEvent]
    latest_event: Optional[StructureEvent] = None
    hh_hl_ratio: str  # "3/4"

# ── Order Block ──
class OrderBlock(BaseModel):
    type: str  # "bullish" | "bearish"
    top: float
    bottom: float
    date: str
    score: float  # 0.0-10.0
    confirmations: list[str]
    retest_count: int = 0
    mitigated: bool = False
    nested: bool = False

class OrderBlockResult(BaseModel):
    blocks: list[OrderBlock]
    active_bullish: list[OrderBlock]  # mitigated=False, type=bullish
    active_bearish: list[OrderBlock]

# ── FVG ──
class FvgStatus(str, Enum):
    ACTIVE = "active"
    CE_TOUCHED = "ce_touched"
    RESPECTED = "respected"
    DEEPLY_FILLED = "deeply_filled"
    FULLY_FILLED = "fully_filled"
    INVERTED = "inverted"

class FairValueGap(BaseModel):
    type: str  # "bullish" | "bearish"
    top: float
    bottom: float
    ce: float  # CE midline
    date: str
    status: FvgStatus
    gap_pct: float
    freshness: float  # 0.0-1.0 decay

class FvgResult(BaseModel):
    gaps: list[FairValueGap]
    active: list[FairValueGap]

# ── 流動性 ──
class LiquidityLevel(BaseModel):
    type: str  # "EQH" | "EQL"
    price: float
    touches: int
    liq_score: float  # 0.0-1.0
    swept: bool = False
    sweep_date: Optional[str] = None

class LiquidityResult(BaseModel):
    levels: list[LiquidityLevel]
    bsl: list[LiquidityLevel]  # buy-side liquidity
    ssl: list[LiquidityLevel]  # sell-side liquidity

# ── Fibonacci ──
class FibonacciResult(BaseModel):
    swing_high: float
    swing_low: float
    leg_score: float  # leg quality
    levels: dict[str, float]  # {"0.0": 100, "0.236": 95.3, ...}
    current_zone: str  # "premium" | "discount" | "ote" | "equilibrium"
    current_fib: float  # 0.0-1.0

# ── Regime ──
class MarketRegime(str, Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    HIGH_VOL = "high_volatility"
    LOW_VOL = "low_volatility"

class RegimeResult(BaseModel):
    regime: MarketRegime
    atr_percentile: float
    adx: Optional[float] = None

# ── 整合 ──
class SmcResult(BaseModel):
    """統一 SMC 分析結果，所有下游模組只接受此型別"""
    ticker: str
    timeframe: str
    bar_count: int
    computed_at: str  # ISO datetime
    structure: StructureResult
    order_blocks: OrderBlockResult
    fvg: FvgResult
    liquidity: LiquidityResult
    fibonacci: FibonacciResult
    regime: RegimeResult
```

### 規則

```
1. smc/__init__.py 的 run_smc_analysis_v2() 必須回傳 SmcResult
2. decision/ 所有模組接收 SmcResult，不接受 dict
3. API v2 端點直接 return SmcResult（Pydantic → JSON 自動序列化）
4. 存入 DB 的 smc_data JSONB = SmcResult.model_dump()
5. 前端 TypeScript 對應產生同結構的 interface（由 API response 推導）
```

---

## 十一、時間對齊規則

> 問題：月線/週線/日線/1H 的時間戳格式不同（date vs datetime），多時間框架對齊容易出錯。

### 規範

```
時間戳統一規則：
  日線以上（月/週/日）: ISO date string "2026-04-08"
  日內（1H/4H/30m/15m）: ISO datetime string "2026-04-08T14:30:00-04:00"（帶時區）

Resample 對齊：
  週線: 以每週五收盤為基準（pandas resample("W-FRI")）
  月線: 以每月最後一個交易日收盤為基準（resample("ME")）
  4H: 從 1H resample，對齊到 [09:30, 13:30] 兩個 session（美股）

跨時間框架查詢規則：
  MTF 決策矩陣輸入格式：
    {
      "monthly": StructureResult,  // 最後完整月
      "weekly":  StructureResult,  // 最後完整週
      "daily":   StructureResult,  // 最新日線
    }
  每個時間框架獨立計算 SmcResult，不混用 bar 數據

台股 vs 美股時區：
  美股: America/New_York（UTC-4 / UTC-5 DST）
  台股: Asia/Taipei（UTC+8）
  DB 存 UTC，API 輸出帶時區
  前端顯示用戶本地時區
```

### helpers.py 必須提供

```python
def normalize_timestamp(dt, timeframe: str) -> str:
    """統一時間戳格式"""

def resample_bars(bars: list[PriceBar], target_tf: str) -> list[PriceBar]:
    """將日線 resample 到週線/月線"""

def align_timeframes(daily: SmcResult, weekly: SmcResult, monthly: SmcResult) -> dict:
    """將不同 TF 的結果對齊成 MTF 決策矩陣輸入"""
```

---

## 十二、快取策略

> 問題：SMC 計算（特別是 OB 評分、Fibonacci leg scoring、流動性掃描）運算量大，每次 API 請求都重算會壓垮後端。

### 三層快取架構

```
Layer 1: DB 快取（主要）
  ─ 每次分析完成，SmcResult 存入 analysis_results.smc_data (JSONB)
  ─ API 查詢時先查 DB，如果 computed_at 在今天收盤後 → 直接回傳
  ─ TTL: 日線 = 收盤後到隔日收盤前有效；日內 = 1 小時

Layer 2: 記憶體快取（per-request 防重複計算）
  ─ 同一支股票的同一個 request 中，structure/ob/fvg/liquidity/fibonacci
    計算完的中間結果用 dict 暫存，避免模組間重複計算
  ─ 例如：entry.py 需要 OB + FVG + Fibonacci → 只算一次

Layer 3: 前端快取（SWR / React Query）
  ─ 前端用 SWR 的 staleWhileRevalidate 模式
  ─ SMC 數據 staleTime = 5 分鐘
  ─ 即時報價 staleTime = 30 秒
  ─ 圖表切換時間框架時，已載入的 TF 數據保留在 cache
```

### 快取失效觸發

```
自動失效：
  ─ 新股價數據寫入 DB → 該股票所有 TF 的快取失效
  ─ 手動觸發「重新分析」→ 該股票快取失效
  ─ 每日定時分析（cron）→ 全部失效重算

API 端點加入快取控制：
  GET /api/v2/stocks/{ticker}/smc?force=true  → 跳過快取強制重算
  Response Header: X-Cache: HIT/MISS + X-Computed-At: ISO datetime
```

### DB 快取查詢邏輯

```python
async def get_smc_cached(ticker: str, timeframe: str, force: bool = False) -> SmcResult:
    if not force:
        cached = await db.query(AnalysisResult).filter(
            ticker=ticker, smc_version=2
        ).order_by(desc(computed_at)).first()

        if cached and cached.smc_data and is_still_valid(cached.computed_at, timeframe):
            return SmcResult.model_validate(cached.smc_data)

    # Cache miss → 重新計算
    result = await run_smc_analysis_v2(ticker, timeframe)
    await save_to_db(result)
    return result
```

---

## 十三、回測 = Live 一致性

> 問題：回測引擎和即時分析若用不同的邏輯/參數，回測結果無法代表真實表現。

### 核心原則：Single Engine, Two Modes

```
回測和即時分析共用同一套 SMC 引擎：
  ─ smc/__init__.py 的 run_smc_analysis_v2() 同時用於：
    1. 即時分析：輸入完整歷史 bars → 輸出最新狀態
    2. 回測：輸入截斷到某日期的 bars → 輸出該日期的狀態

  ─ 回測不允許 look-ahead：
    bars_up_to_date = bars[bars["date"] <= current_date]
    smc_result = run_smc_analysis_v2(bars_up_to_date)
    entry_signal = run_decision(smc_result, sentiment_at_date)

  ─ 決策引擎 decision/ 也共用：
    回測和即時用同一個 entry.py, sentiment_gate.py, position_sizer.py
```

### 回測引擎改造

```python
# backtester.py 改造

class SmcBacktester:
    def __init__(self, engine: SmcEngine, decision: DecisionEngine):
        self.engine = engine      # 同一個 SMC 引擎實例
        self.decision = decision  # 同一個決策引擎實例

    def run(self, ticker: str, bars: pd.DataFrame,
            sentiments: pd.DataFrame, start: str, end: str):
        """
        walk-forward 回測：每一天用 run_smc_analysis_v2(bars[:today])
        決策用 run_decision(smc_result, sentiment_today)
        不允許使用 bars[today+1:] 的任何資訊
        """
        results = []
        for date in trading_dates(start, end):
            historical = bars[bars["date"] <= date]
            smc = self.engine.analyze(historical)
            sentiment = sentiments.loc[date] if date in sentiments.index else None
            signal = self.decision.evaluate(smc, sentiment)
            results.append({"date": date, "signal": signal, "smc": smc})
        return BacktestResult(results)
```

### 參數一致性保障

```
所有可調參數集中管理在 smc/config.py：
  ─ ATR_PERIOD = 14
  ─ OB_SCORE_THRESHOLD = 4.0
  ─ FVG_MIN_GAP_PCT = 0.3
  ─ EQH_EQL_TOLERANCE_ATR_MULT = 0.15
  ─ ...

回測用同一份 config，不允許回測專用參數。
如果需要參數最佳化，用 walk-forward 分 in-sample / out-of-sample。
```

---

## 十四、狀態管理（OB Decay / FVG 狀態機）

> 問題：OB 的 retest decay、time decay、FVG 的 6 級狀態是跨時間的歷史狀態，不能每次從零計算。

### 解法：狀態隨 bar 遞進更新

```
核心原則：
  SMC 狀態不是「快照」而是「演進」。
  每次新的 bar 進來，更新現有狀態而非重建。

具體做法（每個模組）：

Order Block:
  1. 首次計算：掃描所有歷史 bar，建立 OB 列表 + 初始 score
  2. 新 bar 進來時：
     ─ 檢查每個 active OB 是否被 mitigated（價格穿透）
     ─ 被回測但守住 → score -= 0.5（retest decay）
     ─ 每 20 根 bar 無互動 → score -= 0.3（time decay）
     ─ score < 2.0 → 標記為 expired，從 active 移除
  3. 同時掃描新 bar 是否形成新 OB

FVG:
  1. 首次計算：掃描所有歷史 bar，建立 FVG 列表 + 初始狀態
  2. 新 bar 進來時：
     ─ 價格觸及 CE → 狀態從 Active → CE_Touched
     ─ 反彈離開 → CE_Touched → Respected
     ─ 填充 >75% → Deeply_Filled
     ─ 填充 100% → Fully_Filled
     ─ 反向突破 → Inverted
  3. 同時掃描新 bar 是否形成新 FVG

Liquidity:
  1. 首次計算：掃描所有歷史 bar，偵測 EQH/EQL
  2. 新 bar 進來時：
     ─ 新的 high 接近現有 EQH → touches += 1
     ─ 價格突破後回落 → swept = True，記錄 sweep_date
```

### 實作方式

```python
class OrderBlockTracker:
    """維護 OB 狀態，支援增量更新"""
    def __init__(self):
        self.blocks: list[OrderBlock] = []

    def initialize(self, bars: pd.DataFrame) -> None:
        """首次掃描建立所有 OB"""
        self.blocks = self._scan_all(bars)

    def update(self, new_bar: dict) -> None:
        """每根新 bar 更新狀態"""
        for ob in self.blocks:
            if ob.mitigated:
                continue
            self._check_mitigation(ob, new_bar)
            self._apply_retest_decay(ob, new_bar)
            self._apply_time_decay(ob)

        # 檢查是否有新 OB 形成
        new_obs = self._detect_new(new_bar)
        self.blocks.extend(new_obs)

    @property
    def active(self) -> list[OrderBlock]:
        return [ob for ob in self.blocks if not ob.mitigated and ob.score >= 2.0]
```

### 狀態持久化

```
首次分析（無歷史狀態）：
  → 全量掃描，建立初始狀態
  → SmcResult 存入 DB

後續分析（有歷史狀態）：
  → 從 DB 載入上次的 SmcResult
  → 用新增的 bar 增量更新（update）
  → 更新後的 SmcResult 存回 DB

回測模式：
  → 不從 DB 載入，每次從頭 initialize
  → 逐 bar update，模擬即時狀態演進
```

---

## 十五、錯誤處理與 Fallback

> 問題：沒有 Swing Point 怎麼辦？沒有 OB 怎麼辦？沒有目標價怎麼辦？

### 分級處理策略

```
Level 1: 數據不足（bars < 需求量）
  ─ structure.py: bars < 50 → 回傳 trend=RANGING + empty events
  ─ fibonacci.py: 找不到 valid leg → 回傳 current_zone="unknown" + levels={}
  ─ 前端顯示「數據不足」灰色卡片

Level 2: 模組正常但無信號
  ─ order_block.py: 沒有 active OB → OrderBlockResult(blocks=[], active_bullish=[], active_bearish=[])
  ─ liquidity.py: 沒有 EQH/EQL → LiquidityResult(levels=[], bsl=[], ssl=[])
  ─ 決策引擎照常運行，缺少信號 = 該條件不計數

Level 3: 進場建議缺件
  場景：有上升結構但沒有 Bullish OB 也沒有 FVG
  ─ entry.py Fallback 順序：
    1. Bullish OB 上緣（首選）
    2. Bullish FVG 底部
    3. 最近 Swing Low（次選）
    4. Fibonacci OTE 區間中點
    5. 都沒有 → entry_price = None，recommendation = "觀望"

  場景：有進場但沒有停損
  ─ Fallback 順序：
    1. OB 底部 - ATR buffer
    2. FVG 下方
    3. 結構 Swing Low - ATR buffer
    4. 都沒有 → stop_price = None，不出進場建議（safety）

  場景：有進場但沒有目標
  ─ Fallback 順序：
    1. Bearish OB 底部
    2. EQH / BSL 價位
    3. Swing High
    4. 都沒有 → target_price = entry * 1.1（保守 10%），標注 "estimated"

Level 4: API / 數據源失敗
  ─ yfinance 抓取失敗 → retry 2 次 + 降級回傳 DB 中最新數據
  ─ 情緒 API 失敗 → sentiment_gate 回傳「中性」，不阻擋也不加速
  ─ 任一 SMC 模組拋異常 → 該模組回傳空結果 + 記錄 warning log
  ─ 不因單一模組失敗而整體崩潰
```

### 錯誤回傳格式

```python
class SmcResult(BaseModel):
    # ... 原有欄位 ...
    warnings: list[str] = []  # 例如 ["fibonacci: no valid leg found", "ob: bars < 50"]
    data_quality: str = "full"  # "full" | "partial" | "insufficient"
```

---

## 十六、前端 Overlay 效能

> 問題：同時顯示 OB + FVG + Fibonacci + Liquidity + BOS/CHoCH + Volume Profile，lightweight-charts 可能會卡。

### 效能策略

```
1. 可見範圍限制（viewport culling）
   ─ 只繪製當前圖表可見範圍內的標記
   ─ lightweight-charts 的 subscribeVisibleLogicalRangeChange() 監聽可見範圍
   ─ 滑動/縮放時動態增刪標記
   ─ 預載前後 20% 範圍避免閃爍

2. 數量上限
   ─ OB: 最多顯示 15 個 active（score 最高的）
   ─ FVG: 最多顯示 10 個 active
   ─ EQH/EQL: 最多顯示 8 個
   ─ 超出的部分只在 tooltip / 資訊面板中列出

3. 繪製方式分級
   ─ 輕量標記（priceLine）: OB top/bottom, FVG top/bottom, EQH/EQL — 效能好
   ─ 半透明區域（custom series / primitives）: OB 矩形, FVG 矩形 — 較重
   ─ 策略：預設用 priceLine，用戶勾選「顯示區塊填充」時才切換到 primitives

4. 圖層開關即卸載
   ─ 關閉某個圖層 → 立即 remove 所有該圖層的 series/primitives
   ─ 不只是 hide（display:none），而是真的移除 DOM/Canvas 元素
   ─ 重新開啟時再次創建

5. 延遲載入
   ─ 圖表初始只載入 candle + volume
   ─ SMC overlay 在 candle 渲染完成後 requestAnimationFrame 依序疊加
   ─ 順序：Structure → OB → FVG → Fibonacci → Liquidity（按重要性）
```

### 效能指標

```
目標：
  ─ 500 根 K 線 + 全部圖層開啟 → 首次渲染 < 500ms
  ─ 圖層開關切換 → 反應 < 100ms
  ─ 時間框架切換 → 新數據渲染 < 800ms
  ─ 捲動/縮放 → 60fps 不掉幀

監測：
  ─ 開發階段用 Performance.mark() 計時
  ─ 超過閾值的操作在 console 打 warning
```

---

## 十七、Intraday 數據安全

> 問題：yfinance 有 rate limit，大量抓取日內數據會被封鎖。

### 安全抓取策略

```
Rate Limit 保護：
  ─ 全局 semaphore: 同時最多 3 個 yfinance 並發請求
  ─ 請求間隔: 每支股票間最少 500ms
  ─ 單次最多抓取: 5 支股票的 intraday（避免批量觸發）

Retry 策略：
  ─ 失敗 → wait 2s → retry 1
  ─ 再失敗 → wait 5s → retry 2
  ─ 第 3 次失敗 → 放棄，回傳 DB 最新數據 + warning
  ─ HTTP 429 (rate limit) → wait 60s → retry（最多 1 次）

Fallback 層級：
  1. yfinance real-time → 成功
  2. yfinance 失敗 → DB 中最新 intraday 數據（可能是舊的）
  3. DB 也沒有 intraday → 只用日線分析，前端標注「日內數據暫無」

數據驗證：
  ─ 抓回的 bar 數量 < 預期 50% → 標記 data_quality = "partial"
  ─ OHLCV 有 NaN → 整根 bar 丟棄
  ─ 時間戳不連續（gap > 預期） → 記錄 warning 但不補洞

存儲策略：
  ─ 1H 數據: 存 DB，保留 60 天（自動清理 older）
  ─ 15m/30m: 不存 DB，每次按需抓取
  ─ DB 清理 cron: 每日 04:00 UTC 刪除 > 60 天的 intraday 數據
```

### fetcher.py 擴展

```python
class IntraDayFetcher:
    SEMAPHORE = asyncio.Semaphore(3)
    MIN_INTERVAL = 0.5  # seconds

    async def fetch(self, ticker: str, timeframe: str = "1h",
                    period: str = "60d") -> list[PriceBar]:
        async with self.SEMAPHORE:
            await self._rate_limit()
            for attempt in range(3):
                try:
                    data = await self._yfinance_fetch(ticker, timeframe, period)
                    return self._validate(data)
                except RateLimitError:
                    await asyncio.sleep(60)
                except Exception:
                    await asyncio.sleep(2 ** attempt)

            # All retries failed → fallback to DB
            return await self._fallback_db(ticker, timeframe)
```

---

## 十八、測試計畫

> 問題：沒有測試計畫，上線後無法保證 SMC 引擎正確性。

### 測試層級

```
Level 1: Unit Tests（每個 SMC 模組）
  位置: tests/unit/smc/

  test_structure.py:
    ─ test_swing_point_detection_basic: 明確的 HH/HL/LH/LL 序列
    ─ test_swing_point_tolerance: ATR 容差內的 equal high/low
    ─ test_trend_uptrend: 4 組 HH+HL, 3/4 滿足
    ─ test_trend_weak_uptrend: 3/4 但不含最新
    ─ test_trend_ranging: 無明確方向
    ─ test_trend_downtrend: LL+LH 一致
    ─ test_bos_detection: 價格突破前 swing high/low
    ─ test_choch_detection: 上升趨勢中出現 LL
    ─ test_mss_detection: CHoCH + displacement
    ─ test_insufficient_data: bars < 50

  test_order_block.py:
    ─ test_ob_detection_bullish: 急拉前的最後下跌 bar
    ─ test_ob_scoring: 5 項確認 → 分數 7-10
    ─ test_ob_dedup: 同一 leg 只保留 1 main + 1 nested
    ─ test_ob_retest_decay: 回測一次 score -= 0.5
    ─ test_ob_time_decay: 20 bar 無互動 score -= 0.3
    ─ test_ob_mitigation: 價格穿透 → mitigated = True

  test_fvg.py:
    ─ test_fvg_detection: bar2_low > bar0_high → bullish FVG
    ─ test_fvg_status_transition: Active → CE_Touched → Respected
    ─ test_fvg_fully_filled: 完全填充 → status = Fully_Filled
    ─ test_fvg_inverted: 反方向突破 → Inverted
    ─ test_fvg_min_gap: gap < 0.3% ATR → 不計

  test_liquidity.py:
    ─ test_eqh_detection: 3 個 high 在容差內 → EQH
    ─ test_eql_detection: 3 個 low 在容差內 → EQL
    ─ test_sweep_detection: 突破後 2 bar 內回落
    ─ test_liq_score: touches*0.4 + time_spread*0.3 + dwell_ratio*0.3

  test_fibonacci.py:
    ─ test_premium_discount_zone: 價格在 0.618 以上 = premium
    ─ test_ote_zone: 0.618-0.786 = OTE
    ─ test_leg_scoring: displacement * 0.4 + recency * 0.4 + range * 0.2
    ─ test_no_valid_leg: 找不到足夠 swing → fallback

  test_regime.py:
    ─ test_trending: ATR 穩定 + 明確方向
    ─ test_ranging: 無方向 + 低 ATR
    ─ test_high_vol: ATR percentile > 80

Level 2: Integration Tests（模組互動）
  位置: tests/integration/

  test_smc_pipeline.py:
    ─ test_full_analysis: 輸入真實股票 500 bar → SmcResult 結構完整
    ─ test_decision_with_smc: SmcResult → decision/entry.py → 有效進場建議
    ─ test_mtf_decision: 日+週+月的 SmcResult → mtf_gate → 正確決策
    ─ test_sentiment_gate: 正面/負面/極端 → 正確紅綠燈

  test_state_management.py:
    ─ test_ob_state_persistence: 分析 → 存 DB → 載入 → 增量更新 → 結果一致
    ─ test_fvg_state_evolution: 50 bar → FVG active → 再 50 bar → CE_Touched

  test_backtest_consistency.py:
    ─ test_backtest_matches_live:
      用歷史數據即時分析 vs 回測同段時間 → 結果一致
    ─ test_no_lookahead: 回測中 t 日的 SMC 結果不含 t+1 數據

Level 3: Golden File Tests（回歸保護）
  位置: tests/golden/

  ─ 選 5 支代表性股票（2 美股 + 1 台股 + 1 盤整 + 1 下跌）
  ─ 固定 500 bar 歷史數據 → 存為 test fixture（CSV）
  ─ 對應的預期 SmcResult → 存為 golden JSON
  ─ 每次 PR 都跑：assert result == golden（核心欄位）
  ─ 允許 OB score 有 ±0.1 浮動（浮點數精度）

Level 4: Visual Validation（人工 + 截圖對比）
  ─ 把 SmcResult 疊在 TradingView 上，人工比對
  ─ 至少 3 支股票在上線前做一次
  ─ 截圖存入 docs/validation/ 作為記錄
```

### 測試基礎設施

```
conftest.py 提供：
  ─ fixture: sample_bars_uptrend, sample_bars_downtrend, sample_bars_ranging
  ─ fixture: real_stock_bars(ticker) → 從 tests/fixtures/ 載入 CSV
  ─ fixture: async_db_session → 測試用 DB（in-memory 或 test DB）

CI（未來）：
  ─ pytest tests/unit/ → 每次 commit
  ─ pytest tests/integration/ → 每次 PR
  ─ pytest tests/golden/ → 每次 PR
```

---

## 十九、決策引擎優先級規則

> 問題：多個 OB / FVG / Liquidity 都存在時，decision engine 怎麼挑？nested 和 main 怎麼區分？

### 進場價選取優先級

```
情境：多個 Bullish OB 同時 active
  規則：
    1. 取 score 最高的（品質優先）
    2. score 相同 → 取離現價最近但仍在下方的（最先可能觸及）
    3. Nested OB 只在 main OB 範圍內有效 → 作為精確進場點
       ─ 進場建議: main OB 標記為「進場區間」，nested OB 標記為「精確進場點」
       ─ 停損: 基於 main OB 底部（而非 nested）

情境：Bullish OB 和 Bullish FVG 都存在
  規則：
    1. OB（score ≥ 6.0）> FVG（任何狀態）  ← OB 優先
    2. OB（score 4.0-6.0）+ FVG 重疊 → 信號加強，取交集區間
    3. 只有 FVG（無 OB 或 OB score < 4.0）→ FVG 作為進場區
    4. OB + FVG 不重疊且都有效 → 取離現價更近的

情境：多個 EQH/EQL 作為目標
  規則：
    1. 取 liq_score 最高的（最有吸引力的流動性池）
    2. liq_score 相同 → 取離現價更近的（較保守的目標）
    3. 目標1 = 最近的高分 EQH，目標2 = 次近的 Bearish OB

情境：Fibonacci OTE 區間和 OB 衝突
  規則：
    1. OB 在 OTE 區間內（0.618-0.786）→ 最強信號，信心 ×1.2
    2. OB 在 Discount 但不在 OTE → 正常信號
    3. OB 在 Premium → 降級或不進場（除非強勢 BOS）
    4. 無 OB，只有 OTE 區間 → 用 OTE midpoint 作為進場參考

情境：MTF 衝突（日線多頭但週線盤整）
  規則：
    按 MTF 決策矩陣（STRATEGY.md §5.3）→ 降級倉位，不排除
    月↑ 週─ 日↑ → 可進場但最高「標準倉位」
    月↑ 週↓ 日↑ → 只能「探索倉位」
    月↓ 任意 任意 → 不做多
```

### 停損選取優先級

```
停損是安全機制，選最保護的：
  1. Main OB 底部 - ATR * 0.5（buffer）
  2. FVG 底部 - ATR * 0.3
  3. 最近 Swing Low - ATR * 0.5
  4. Fibonacci 1.0 水位（完整回撤）

選取規則：
  ─ 取上述中「最緊密但合理」的
  ─ 合理 = 停損距離 ≥ 1.5 * ATR（避免被噪音掃掉）
  ─ 停損距離 < 1.0 * ATR → 太緊，用下一層 fallback
  ─ 停損距離 > 5.0 * ATR → 太寬，R:R 會太低，可能不進場
```

### 目標選取優先級

```
目標取決於做多/做空方向：

做多目標（由近到遠）：
  T1: 最近的 Bearish OB 底部（供應區下緣）
  T2: 最高分的 EQH / BSL 價位
  T3: 前高（Swing High）
  T4: 上方 FVG（Bearish）底部

選取規則：
  ─ 主目標 = T1 或 T2（取較近的）
  ─ 延伸目標 = T3 或 T4
  ─ R:R 計算用主目標
  ─ 部分獲利策略：50% 在 T1，30% 在 T2，20% trailing
```

### 綜合決策輸出

```python
class EntryPlan(BaseModel):
    recommendation: str  # "強力推薦" | "推薦" | "觀察" | "觀望" | "不推薦"
    action: str  # "買入" | "等回調" | "觀望" | "不操作"

    entry_zone: tuple[float, float] | None  # (low, high) 進場區間
    entry_price: float | None  # 建議精確進場價
    entry_source: str  # "OB(7.8)" | "FVG" | "SwingLow" | "OTE"

    stop_price: float | None
    stop_source: str  # "OB_bottom" | "FVG_bottom" | "SwingLow"
    stop_atr_distance: float  # 停損距離 / ATR

    target_1: float | None
    target_1_source: str
    target_2: float | None
    target_2_source: str

    rr_ratio: float | None  # (target_1 - entry) / (entry - stop)

    position_tier: str  # "核心" | "標準" | "探索"
    max_position_pct: float  # 佔總資金 %

    conditions_met: int  # 0-4
    conditions_detail: dict[str, bool]  # {"smc_structure": True, "momentum": True, ...}

    confidence: float  # 0.0-1.0
    warnings: list[str]  # ["OB in premium zone", "weak trend", ...]
```

---

## 二十、工程問題審計追蹤

| # | 問題 | 解決方案 | 對應章節 |
|---|------|---------|---------|
| 1 | 缺統一 Schema | SmcResult Pydantic 模型鏈 | §十 |
| 2 | 時間對齊不清 | 統一時間戳格式 + resample 規則 | §十一 |
| 3 | 無快取策略 | 三層快取（DB + 記憶體 + SWR） | §十二 |
| 4 | 回測≠即時 | Single Engine, Two Modes | §十三 |
| 5 | 狀態管理缺失 | 狀態隨 bar 遞進 + DB 持久化 | §十四 |
| 6 | 無錯誤處理 | 4 級 fallback + warning list | §十五 |
| 7 | 前端效能風險 | viewport culling + 數量上限 + 延遲載入 | §十六 |
| 8 | Intraday 抓取不安全 | semaphore + retry + fallback | §十七 |
| 9 | 無測試計畫 | 4 層測試（unit/integration/golden/visual） | §十八 |
| 10 | 決策優先級不明 | 完整 OB/FVG/Fibonacci/MTF 選取規則 | §十九 |

---

## 廿一、Analysis Pipeline（🔥 最關鍵缺口）

> 問題：API 端點直接觸發 SMC 計算 → 30 支股票 × 多人同時開頁面 → CPU 爆炸 + DB 爆炸。
> 核心原則：**API 不跑分析，API 只讀結果。**

### 架構：Scheduler → Worker → DB → API

```
                    ┌──────────────────────────────────┐
                    │         Analysis Pipeline         │
                    └──────────────────────────────────┘

  ┌─────────┐      ┌──────────────┐      ┌──────────┐      ┌─────────┐
  │ Scheduler│ ───→ │  Job Queue   │ ───→ │  Worker  │ ───→ │   DB    │
  │ (cron)   │      │ (Redis/RQ)   │      │ (SMC計算) │      │ (結果)   │
  └─────────┘      └──────────────┘      └──────────┘      └────┬────┘
                                                                 │
                                                                 ↓
                                                          ┌──────────┐
                                                          │   API    │
                                                          │ (只讀DB) │
                                                          └──────────┘
                                                                 ↑
                                                          ┌──────────┐
                                                          │  前端    │
                                                          └──────────┘
```

### 排程規則

```
定時排程（Scheduler）：

  每日收盤後（美股 16:30 ET / 台股 13:30 CST）：
    ─ 全量分析：所有追蹤中的股票
    ─ 觸發：cron job 或 APScheduler
    ─ 範圍：run_smc_analysis_v2() × 每支股票 × 日線/週線/月線
    ─ 結果存入 analysis_results

  每小時（交易時段內）：
    ─ 增量更新：有新 intraday 數據的股票
    ─ 範圍：只更新 1H/4H 的 SMC（如果 P2 已做）
    ─ 不重算日線以上

  手動觸發：
    ─ POST /api/v2/analysis/run → enqueue job → 非同步執行
    ─ API 立即回傳 job_id，不等計算完成
    ─ 前端用 SSE 或 polling 等結果

絕對禁止：
  ❌ GET /api/v2/stocks/{ticker}/smc 裡面跑 run_smc_analysis_v2()
  ✅ GET /api/v2/stocks/{ticker}/smc 只從 DB 讀取最新 SmcResult
```

### Pipeline 執行流程

```python
# backend/app/pipeline/scheduler.py

class AnalysisPipeline:
    """控制 SMC 分析的批次執行"""

    async def run_daily_batch(self):
        """收盤後全量分析"""
        stocks = await get_all_tracked_stocks()

        for stock in stocks:
            # 1. 先更新股價
            await fetcher.fetch_latest(stock.ticker)

            # 2. 排入分析隊列（不直接跑）
            await job_queue.enqueue(
                "smc_analysis",
                ticker=stock.ticker,
                timeframes=["daily", "weekly", "monthly"],
                priority="normal"
            )

        logger.info(f"Enqueued {len(stocks)} stocks for daily analysis")

    async def run_manual(self, ticker: str):
        """手動觸發單支股票分析"""
        job_id = await job_queue.enqueue(
            "smc_analysis",
            ticker=ticker,
            timeframes=["daily", "weekly", "monthly"],
            priority="high"  # 手動觸發優先
        )
        return job_id  # 前端用這個 polling

# backend/app/pipeline/worker.py

class SmcWorker:
    """執行 SMC 分析的 worker"""

    async def process(self, job: Job):
        ticker = job.params["ticker"]
        timeframes = job.params["timeframes"]

        for tf in timeframes:
            bars = await get_bars(ticker, tf)
            result = await run_smc_analysis_v2(ticker, bars, tf)
            await save_smc_result(ticker, tf, result)

        # 跑完 SMC 後跑 Decision
        decision = await run_decision(ticker)
        await save_decision_result(ticker, decision)

        logger.info(f"Completed analysis for {ticker}")
```

### API 端點改造

```python
# 改造前（❌ 危險）
@router.get("/api/v2/stocks/{ticker}/smc")
async def get_smc(ticker: str):
    bars = await get_bars(ticker)
    return await run_smc_analysis_v2(ticker, bars)  # ← 每次 request 都重算

# 改造後（✅ 安全）
@router.get("/api/v2/stocks/{ticker}/smc")
async def get_smc(ticker: str, db: AsyncSession = Depends(get_db)):
    result = await db.query(AnalysisResult).filter(
        ticker=ticker, smc_version=2
    ).order_by(desc(computed_at)).first()

    if not result:
        raise HTTPException(404, "尚未分析，請先觸發分析")

    return {
        "data": result.smc_data,
        "computed_at": result.computed_at,
        "is_stale": is_stale(result.computed_at),  # 超過 24 小時標記為 stale
    }

# 手動觸發（非同步）
@router.post("/api/v2/analysis/run")
async def trigger_analysis(ticker: str):
    job_id = await pipeline.run_manual(ticker)
    return {"job_id": job_id, "status": "queued"}

@router.get("/api/v2/analysis/job/{job_id}")
async def get_job_status(job_id: str):
    return await job_queue.get_status(job_id)  # pending / running / completed / failed
```

---

## 廿二、非同步任務系統（Async Job Queue）

> 問題：POST /analysis/run 同步跑 10 支股票 → request timeout。

### 技術選型

```
評估：
  ─ Celery: 太重，需要 RabbitMQ/Redis broker，對這個專案 overkill
  ─ Dramatiq: 輕量但需要 Redis
  ─ RQ (Redis Queue): 簡單，適合中小型專案
  ─ arq: async-native，基於 Redis，最符合 FastAPI async 架構
  ─ 內建 BackgroundTasks: 太簡單，無持久化、無 retry

✅ 選擇：arq（async + Redis）

理由：
  ─ 原生 async，和 FastAPI 一致
  ─ 基於 Redis，部署簡單（Docker Compose 加一個 Redis）
  ─ 支援 retry、timeout、cron、priority
  ─ 輕量，不需要額外的 broker
```

### 架構

```
Docker Compose 新增：
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

Python 新增依賴：
  pip install arq

目錄結構：
  backend/app/
  ├── pipeline/
  │   ├── __init__.py
  │   ├── scheduler.py    # APScheduler / cron 定義
  │   ├── worker.py        # arq worker（SMC 計算）
  │   ├── jobs.py          # 各種 job 定義
  │   └── config.py        # Redis 連線 + arq 設定
```

### Job 定義

```python
# backend/app/pipeline/jobs.py

async def job_smc_analysis(ctx, ticker: str, timeframes: list[str]):
    """SMC 全分析 job"""
    logger.info(f"[JOB] Starting SMC analysis for {ticker}")
    try:
        for tf in timeframes:
            bars = await get_bars(ticker, tf)
            result = await run_smc_analysis_v2(ticker, bars, tf)
            await save_smc_result(ticker, tf, result)
        await run_and_save_decision(ticker)
        logger.info(f"[JOB] Completed {ticker}")
    except Exception as e:
        logger.error(f"[JOB] Failed {ticker}: {e}")
        raise  # arq 會自動 retry

async def job_daily_batch(ctx):
    """每日批次分析"""
    stocks = await get_all_tracked_stocks()
    for stock in stocks:
        await ctx["redis"].enqueue_job(
            "job_smc_analysis",
            stock.ticker,
            ["daily", "weekly", "monthly"],
        )

async def job_fetch_prices(ctx, ticker: str):
    """更新股價 job"""
    await fetcher.fetch_latest(ticker)

# arq worker 設定
class WorkerSettings:
    functions = [job_smc_analysis, job_daily_batch, job_fetch_prices]
    redis_settings = RedisSettings(host="localhost", port=6379)
    max_jobs = 5  # 最多同時跑 5 個 job
    job_timeout = 300  # 單個 job 最多 5 分鐘
    max_tries = 3  # 失敗重試 3 次
    retry_delay = 10  # 10 秒後重試

    # 定時排程
    cron_jobs = [
        cron(job_daily_batch, hour=21, minute=0),  # UTC 21:00 = ET 17:00（收盤後 30 分）
    ]
```

### 啟動方式

```bash
# Terminal 1: FastAPI
uvicorn app.main:app --reload

# Terminal 2: arq worker
arq app.pipeline.jobs.WorkerSettings

# 或 Docker Compose
services:
  api:
    command: uvicorn app.main:app --host 0.0.0.0
  worker:
    command: arq app.pipeline.jobs.WorkerSettings
  redis:
    image: redis:7-alpine
```

---

## 廿三、分層快取強化

> 問題：§十二 的快取設計需要更具體的 TTL 分層。

### 快取 TTL 矩陣

```
| 數據類型 | L1 (in-memory) | L2 (Redis) | L3 (DB) |
|---------|----------------|------------|---------|
| SMC 結構 | 5 min | 1 hour | 收盤後重算 |
| OB/FVG | 5 min | 1 hour | 收盤後重算 |
| Fibonacci | 5 min | 1 hour | 收盤後重算 |
| 即時報價 | 10 sec | 30 sec | 不存 |
| 情緒分數 | 1 min | 10 min | 每次分析存 |
| Correlation | — | 24 hour | daily batch |
| Decision | 5 min | 1 hour | 每次分析存 |

in-memory 用 functools.lru_cache 或 cachetools.TTLCache
Redis 用 arq 自帶的 Redis 連線
DB 是 analysis_results 表
```

### Redis 快取實作

```python
# backend/app/pipeline/cache.py

import json
from arq.connections import RedisSettings, create_pool

class SmcCache:
    def __init__(self, redis):
        self.redis = redis

    async def get(self, ticker: str, timeframe: str) -> SmcResult | None:
        key = f"smc:{ticker}:{timeframe}"
        data = await self.redis.get(key)
        if data:
            return SmcResult.model_validate_json(data)
        return None

    async def set(self, ticker: str, timeframe: str, result: SmcResult, ttl: int = 3600):
        key = f"smc:{ticker}:{timeframe}"
        await self.redis.set(key, result.model_dump_json(), ex=ttl)

    async def invalidate(self, ticker: str):
        """清除某支股票所有 TF 的快取"""
        for tf in ["daily", "weekly", "monthly", "1h", "4h"]:
            key = f"smc:{ticker}:{tf}"
            await self.redis.delete(key)

    async def invalidate_all(self):
        """清除所有快取（daily batch 前）"""
        keys = await self.redis.keys("smc:*")
        if keys:
            await self.redis.delete(*keys)
```

---

## 廿四、增量更新（Incremental Update）強化

> 問題：§十四 定義了狀態管理概念，但缺少具體的增量 vs 全量判斷邏輯。

### 判斷邏輯

```
何時全量計算（initialize）：
  1. 首次分析（DB 無歷史 SmcResult）
  2. 手動強制重算（force=true）
  3. 策略版本變更（strategy_hash 不同）
  4. 歷史數據大量回補（新增 bar > 50）

何時增量更新（update）：
  1. 每日收盤後新增 1 根日線 bar
  2. 每小時新增 1 根 1H bar
  3. 新增 bar ≤ 5 → 增量

增量更新流程：
  1. 從 DB 載入上次的 SmcResult
  2. 取新增的 bar（last_computed_date 之後的）
  3. 逐 bar 呼叫各模組的 update()
  4. 重新計算 Fibonacci（因為 swing 可能改變）
  5. 重新跑 Decision
  6. 存回 DB

效能對比（預估）：
  全量（500 bar）: ~2-5 秒
  增量（1 bar）: ~0.1-0.3 秒
  批次 30 支全量: ~60-150 秒
  批次 30 支增量: ~3-9 秒 ← 10x 加速
```

### Worker 增量判斷

```python
async def job_smc_analysis(ctx, ticker: str, timeframes: list[str]):
    for tf in timeframes:
        # 查看上次分析
        last = await get_last_smc_result(ticker, tf)
        bars = await get_bars(ticker, tf)

        if should_full_recompute(last, bars):
            result = await run_smc_full(ticker, bars, tf)
        else:
            new_bars = bars_since(bars, last.computed_at)
            result = await run_smc_incremental(last, new_bars, tf)

        await save_smc_result(ticker, tf, result)

def should_full_recompute(last: SmcResult | None, bars) -> bool:
    if last is None:
        return True
    if last.strategy_hash != CURRENT_STRATEGY_HASH:
        return True
    new_bar_count = count_bars_since(bars, last.computed_at)
    if new_bar_count > 50:
        return True
    return False
```

---

## 廿五、資料版本控制

> 問題：改了 OB 算法或 FVG 規則 → 舊的 SmcResult 不相容。

### 版本策略

```
analysis_results 表新增欄位：
  smc_version INTEGER DEFAULT 2     ─ 大版本（v1→v2 = 打掉重練）
  strategy_hash VARCHAR(16)         ─ 策略配置的 hash
  engine_version VARCHAR(10)        ─ 引擎代碼版本 "2.0.1"

strategy_hash 計算：
  hash = md5(json.dumps(smc_config.dict(), sort_keys=True))[:16]

  smc_config 包含：
    ATR_PERIOD, OB_SCORE_THRESHOLD, FVG_MIN_GAP_PCT,
    EQH_TOLERANCE, FIBONACCI_LEG_WEIGHTS, ...

版本不匹配時的行為：
  ─ API 讀取結果時檢查 strategy_hash
  ─ hash 不同 → 標記 is_stale=True + 觸發重算 job
  ─ 前端顯示「分析版本已過期，正在重新計算...」
  ─ 舊結果仍然回傳（有數據比沒數據好），但加 warning

版本升級流程：
  1. 改了 smc/config.py 中的參數
  2. strategy_hash 自動變更
  3. 下次 daily batch → 偵測到 hash 不同 → 全量重算
  4. 手動觸發可以 force 立即重算
```

---

## 廿六、Decision Determinism（決策確定性）

> 問題：sentiment 即時變 + intraday 更新 → 同一分鐘查兩次可能得到不同 decision。

### 核心原則：Decision = Frozen at Analysis Time

```
規則：
  1. Decision 只在分析 pipeline 中計算一次
  2. 計算時的 inputs 全部快照保存：
     ─ smc_result（那個時刻的 SMC 狀態）
     ─ sentiment_at_analysis（那個時刻的情緒分）
     ─ price_at_analysis（那個時刻的價格）
  3. API 回傳的 decision 是「上次分析時的決策」，不是即時重算

  ❌ 錯誤做法：
    GET /decision → 即時抓 sentiment → 即時算 → 每次可能不同

  ✅ 正確做法：
    Pipeline 分析 → decision 存 DB → API 只讀 DB
    前端顯示「分析時間：2026-04-08 17:30」
```

### Decision 快照結構

```python
class DecisionSnapshot(BaseModel):
    """不可變的決策快照"""
    ticker: str
    analyzed_at: str  # ISO datetime
    price_at_analysis: float
    sentiment_at_analysis: float | None
    smc_version: int
    strategy_hash: str

    # 決策結果
    entry_plan: EntryPlan
    conditions_met: int
    conditions_detail: dict[str, bool]

    # 時效性
    valid_until: str  # 下次 daily batch 前有效
    is_actionable: bool  # 現價是否仍在進場區間
```

### 前端即時性補充

```
前端可以做「即時輔助判斷」但不改變 decision：
  ─ 即時報價 → 顯示「現價 vs 建議進場價」的距離
  ─ 即時報價 → 判斷「是否已觸及進場/停損/目標」
  ─ 這些是前端計算，不走 API

前端紅燈/黃燈/綠燈：
  🟢 現價在進場區間內 → 可執行
  🟡 現價距進場價 < 3% → 接近
  🔴 現價遠離進場價 > 5% → 等回調
  ⚫ 已觸及停損 → 此 decision 失效
```

---

## 廿七、Chart 效能強化（補充 §十六）

> 問題：§十六 定義了效能策略，但需要具體的「active + top N」規則。

### 圖表顯示數量硬上限

```
每個圖層的最大顯示數量：
  OB:           10 個 active（score 排序取 top 10）
  FVG:          8 個 active（freshness 排序取 top 8）
  EQH/EQL:     6 個（liq_score 排序取 top 6）
  BOS/CHoCH:   20 個（只顯示最近 20 個事件）
  Fibonacci:   1 組（當前最佳 leg）
  Volume Prof: 1 個（當前可見範圍）

圖層間互斥優化：
  ─ 如果同時開 OB + FVG → OB 降到 8 個, FVG 降到 6 個
  ─ 如果全開 → 各圖層再減 20%
  ─ 目的：控制 canvas 上的總元素 < 80 個

回收策略：
  ─ 用戶往左滑（看歷史）→ 右側超出 viewport 的標記先 remove
  ─ 用戶往右滑（看最新）→ 左側超出的標記先 remove
  ─ 保持 viewport + 20% buffer 範圍內的標記
```

---

## 廿八、Correlation 批次計算

> 問題：correlation_cache 的計算時機和範圍不清楚。

### 批次計算規則

```
計算時機：
  ─ 每日 daily batch 結束後自動計算
  ─ 只在持倉股票間計算（不是全部 30+ 支）
  ─ 新加入持倉時觸發一次增量計算

計算範圍：
  ─ 持倉 N 支 → 計算 N*(N-1)/2 對相關性
  ─ 例：持倉 8 支 → 28 對
  ─ window = 60 天滾動相關性
  ─ 數據源：日線 close price

存儲：
  ─ 每天存一筆（覆蓋前一天的結果）
  ─ 只保留最近 30 天的歷史（清理 older）

前端顯示：
  ─ 相關性矩陣只在 Portfolio 頁面顯示
  ─ corr > 0.75 → 紅色警告「同源風險」
  ─ corr < -0.3 → 綠色標記「分散效果好」
```

```python
# backend/app/pipeline/jobs.py

async def job_correlation_batch(ctx):
    """每日計算持倉間的相關性"""
    holdings = await get_portfolio_tickers()
    if len(holdings) < 2:
        return

    prices = {}
    for ticker in holdings:
        prices[ticker] = await get_close_prices(ticker, days=60)

    df = pd.DataFrame(prices)
    corr_matrix = df.corr()

    today = date.today().isoformat()
    for i, t1 in enumerate(holdings):
        for t2 in holdings[i+1:]:
            await save_correlation(today, t1, t2, corr_matrix.loc[t1, t2])
```

---

## 廿九、回測 Slippage & Fee

> 問題：回測沒有考慮滑點和手續費 → 結果過度樂觀。

### 成本模型

```python
# backend/app/services/backtester.py

class CostModel(BaseModel):
    """交易成本模型"""
    # 滑點
    slippage_pct: float = 0.10  # 0.10% 單邊（美股流動性好的大盤股）
    slippage_pct_illiquid: float = 0.25  # 小型股/流動性差

    # 手續費
    commission_per_trade: float = 0.0  # 多數美股券商免傭
    commission_tw_pct: float = 0.1425  # 台股手續費 0.1425%
    tax_tw_sell_pct: float = 0.30  # 台股賣出證交稅 0.3%

    # 融資成本（如果使用）
    margin_interest_annual: float = 0.0  # 年利率

def apply_costs(entry_price: float, exit_price: float,
                shares: int, market: str, cost: CostModel) -> dict:
    """計算含成本的真實損益"""
    if market == "TW":
        entry_cost = entry_price * (1 + cost.commission_tw_pct / 100 + cost.slippage_pct / 100)
        exit_revenue = exit_price * (1 - cost.commission_tw_pct / 100 - cost.tax_tw_sell_pct / 100 - cost.slippage_pct / 100)
    else:  # US
        slippage = cost.slippage_pct / 100
        entry_cost = entry_price * (1 + slippage) + cost.commission_per_trade
        exit_revenue = exit_price * (1 - slippage) - cost.commission_per_trade

    gross_pnl = (exit_price - entry_price) * shares
    net_pnl = (exit_revenue - entry_cost) * shares
    cost_drag = gross_pnl - net_pnl

    return {
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "cost_drag": cost_drag,
        "cost_drag_pct": (cost_drag / (entry_price * shares)) * 100,
    }
```

### 回測報告新增指標

```
回測報告必須同時顯示：
  ─ Gross P&L（不含成本）
  ─ Net P&L（含成本）
  ─ Total Cost Drag（成本吃掉多少利潤）
  ─ Cost Drag %（成本佔比）

前端 Backtest 頁面：
  ─ 兩條 equity curve：gross vs net
  ─ 醒目標注差距
  ─ 高頻交易策略的 cost drag 會更大 → 提醒用戶
```

---

## 三十、Observability（監控與可觀測性）

> 問題：SMC 算錯 / worker crash / job hang → 完全不知道。

### 三層監控

```
Layer 1: Structured Logging（必做）

  使用 structlog 或 loguru：
    ─ 每個 job 開始/結束記錄
    ─ 每個 SMC 模組計算耗時
    ─ 異常 + traceback
    ─ 數據品質 warning

  格式：JSON（方便未來接 ELK/Loki）

  範例：
    {"event": "smc_analysis_start", "ticker": "MRVL", "timeframe": "daily", "ts": "..."}
    {"event": "smc_module_done", "module": "structure", "duration_ms": 120, "ticker": "MRVL"}
    {"event": "smc_module_done", "module": "order_block", "duration_ms": 340, "ob_count": 8}
    {"event": "smc_analysis_done", "ticker": "MRVL", "total_ms": 1850, "warnings": ["fib: weak leg"]}
    {"event": "smc_analysis_error", "ticker": "TSM", "error": "insufficient bars", "traceback": "..."}

Layer 2: Health Metrics（建議做）

  暴露 /health 端點：
    GET /health → {
      "api": "ok",
      "db": "ok",
      "redis": "ok",
      "worker": "ok",  // 最後一個 job 完成時間 < 1 小時
      "last_batch": "2026-04-08T21:35:00Z",
      "stocks_analyzed": 30,
      "stale_count": 0,  // 超過 24 小時沒更新的股票
    }

  Dashboard 監控指標（存 DB 或 Redis）：
    ─ analysis_duration_seconds（每支股票分析耗時）
    ─ job_queue_depth（待處理 job 數量）
    ─ cache_hit_rate（快取命中率）
    ─ error_count_24h（過去 24 小時錯誤數）

Layer 3: Alerts（未來）

  Telegram 通知（現有 telegram.py 擴展）：
    ─ Worker 連續 3 個 job 失敗 → 通知
    ─ 某支股票分析耗時 > 30 秒 → 警告
    ─ DB 連線失敗 → 緊急通知
    ─ stale_count > 5 → 通知（太多股票沒更新）
```

### 分析審計日誌

```python
# 每次分析完成存一筆審計日誌

class AnalysisAuditLog(BaseModel):
    ticker: str
    timeframe: str
    started_at: str
    completed_at: str
    duration_ms: int
    engine_version: str
    strategy_hash: str
    mode: str  # "full" | "incremental"
    bar_count: int
    new_bars: int
    warnings: list[str]
    error: str | None
    modules: dict[str, int]  # {"structure": 120, "ob": 340, ...} ms

# 存入新表 analysis_audit_log，保留 90 天
# 可用來分析哪些股票算最久、哪些模組最慢
```

---

## 三一、Production 工程問題審計追蹤（v1.2）

| # | 問題 | 嚴重度 | 解決方案 | 對應章節 |
|---|------|-------|---------|---------|
| 1 | 無 Analysis Pipeline | 🔥 致命 | Scheduler → Job Queue → Worker → DB → API 只讀 | §廿一 |
| 2 | 無 Async Job System | 🔥 致命 | arq + Redis，API 不同步跑分析 | §廿二 |
| 3 | 快取分層不足 | ⚠️ 重要 | L1(memory) + L2(Redis) + L3(DB) + TTL 矩陣 | §廿三 |
| 4 | 無增量更新判斷 | ⚠️ 重要 | full vs incremental 自動判斷 + 10x 加速 | §廿四 |
| 5 | 無資料版本控制 | ⚠️ 重要 | strategy_hash + engine_version + 不匹配自動重算 | §廿五 |
| 6 | Decision 不確定性 | ⚠️ 重要 | Frozen at analysis time + DecisionSnapshot | §廿六 |
| 7 | Chart 效能補充 | ⚡ 中等 | 各圖層硬上限 + 互斥降級 + 回收策略 | §廿七 |
| 8 | Correlation 無排程 | ⚡ 中等 | daily batch job + 只算持倉間 | §廿八 |
| 9 | 回測無成本模型 | ⚡ 中等 | slippage 0.1-0.25% + 台股稅費 + gross vs net | §廿九 |
| 10 | 無 Observability | 🔥 致命 | structlog + /health + 審計日誌 + Telegram alerts | §三十 |

### P0 優先級調整（反映新增內容）

```
原 P0 Week 1-3 保持不變（SMC 引擎 + Decision）

新增 P0.5（在 SMC 引擎完成後，前端之前）：
  ☐ Redis + arq 基礎設施（Docker Compose）
  ☐ pipeline/scheduler.py + worker.py + jobs.py
  ☐ API 改為只讀模式（不直接跑分析）
  ☐ structlog 設定 + 基本 logging
  ☐ /health 端點
  ☐ strategy_hash + smc_config.py

這些是「讓系統能跑」的基礎，必須在前端之前做完。
```
