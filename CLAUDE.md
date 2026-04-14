# Money Printer — Claude 分析指南

## 專案概述

自動化股票分析系統（FastAPI + Next.js + PostgreSQL），追蹤美股/台股，使用 SMC + 趨勢動量做分層決策。

## 技術棧

- **後端**: FastAPI + SQLAlchemy 2.0 async + asyncpg + PostgreSQL 15
- **前端**: Next.js 16 + TypeScript + Tailwind CSS v4 + Webpack (NOT Turbopack)
- **Python**: conda env `money_printer` (Python 3.11)
- **前端啟動**: `/opt/homebrew/bin/node node_modules/.bin/next dev --webpack`
- **Tailwind v4**: 用 `@import "tailwindcss"` (不是 v3 的 `@tailwind`)

## 分析策略架構（分層決策）

```
Layer 1: SMC 結構（方向門檻）
  上升結構 → 通過
  盤整     → 降級（最高標準倉位）
  下降結構 → 排除（不做多）

Layer 2: 動量確認（趨勢追蹤版 technical.py）
  MACD 30% + MA 25% + RSI 20% + Vol 15% + BB 10%
  重點：RSI 高=好, 布林突破上軌=好, 量價配合

Layer 3: 催化劑（新聞情緒）
  正面(≥65) → 加速信號，倉位升級
  中性      → 不影響
  負面(≤35) → 警告，倉位降級

分層決策（條件計數）：
  4 條件滿足 → 強力推薦 + 核心持倉 (15-20%)
  3 條件滿足 → 推薦 + 標準倉位 (8-12%)
  2 條件滿足 → 觀察 + 探索倉位 (3-5%)
  <2 條件    → 不推薦
```

## 倉位等級

| 等級 | 佔總資金 | 條件 |
|------|---------|------|
| 核心持倉 | 15-20% | SMC上升 + 動量≥60 + 正面催化劑 + R:R≥2.0 |
| 標準倉位 | 8-12%  | SMC上升 + 動量≥60 + R:R≥1.8 |
| 探索倉位 | 3-5%   | 盤整偏多 或 動量50-60 或 條件不完全 |

## SMC 進出場

- **買入價**: Bullish OB 上緣 > FVG 底部 > Swing Low > POC
- **停損**: OB 底部 / FVG 下方 / 結構支撐下方（動態）
- **目標**: Bearish OB 底部 / Swing High / 壓力位（動態）
- **風報比**: (target - entry) / (entry - stop)，≥2.0 才算優秀

---

# 當用戶說「幫我分析」時的執行流程

## Step 1: 讀取系統資料

讀取以下 API 數據（用 curl 或直接讀 DB）：
```bash
# 最新分析結果（所有股票）
curl http://localhost:8000/api/v1/analysis/latest

# 持倉
curl http://localhost:8000/api/v1/portfolio

# SMC 趨勢
curl http://localhost:8000/api/v1/stocks/smc-trends
```

## Step 2: 推薦總覽

列出系統前 10 名推薦股票，格式：

```
排名 | 股票 | 動量分 | SMC趨勢 | 催化劑 | R:R | 倉位建議 | 買入價
```

只列推薦等級 ≥「觀察」的股票。

## Step 3: 持倉健檢

對每支持有的股票逐一分析：
- 當前損益%
- SMC 趨勢是否改變（相對買入時）
- 是否接近停損 / 目標
- 建議操作：加碼 / 持有 / 減倉 / 出場
- 一句話理由

## Step 4: 風險檢查

- **集中度**: 單一產業 > 40% 要警告
- **大盤狀態**: SPY/QQQ 的 SMC 趨勢（如果有追蹤）
- **近期事件**: FOMC、財報季、重大經濟數據
- **總曝險**: 所有持倉合計佔總資金比例

## Step 5: 具體操作建議

最多給 3 個操作建議：
```
動作：買入 / 賣出 / 加碼 / 減倉
股票：XXXX
倉位：核心 / 標準 / 探索
價位：買入 XX / 停損 XX / 目標 XX (R:R Xx)
理由：一句話說明為什麼
```

## Step 6: 儲存 AI 分析筆記

每次分析完個股或批次推薦後，**必須** 呼叫 API 儲存分析記錄：

```bash
curl -X POST http://localhost:8000/api/v1/ai-notes \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "ARM",
    "analysis_type": "individual",        # individual / top_pick / portfolio / watchlist
    "recommendation": "推薦",             # 強力推薦 / 推薦 / 觀察 / 不推薦
    "action": "觀望",                     # 買入 / 加碼 / 持有 / 減倉 / 出場 / 觀望
    "summary": "## Markdown 分析內容...",
    "price_at_analysis": 149.11,
    "composite_score": 66.51,
    "smc_trend": "上升趨勢",
    "entry_price": 142.00,
    "stop_price": 135.50,
    "target_price": 166.69,
    "rr_ratio": 3.80,
    "scenarios": {"A": {"condition": "...", "action": "..."}}
  }'
```

這樣用戶可以在個股頁面看到 AI 分析歷史記錄、時間戳、和上次推薦。

## Step 6.5: 載入歷史記憶 context（可選，用於調整信心度）

在分析前或分析過程中，可以查詢該市況 + 推薦等級的歷史績效，自動調整信心度：

```bash
curl "http://localhost:8000/api/v1/ai-notes/memory-context?smc_trend=上升趨勢&recommendation_hint=推薦" \
  -H "Content-Type: application/json"
```

**回傳範例：**
```json
{
  "has_memory": true,
  "confidence_adjustment": 0.15,
  "warnings": [],
  "historical_pattern": {
    "smc_trend": "上升趨勢",
    "recommendation": "推薦",
    "win_rate": 0.75,
    "avg_return_pct": 4.2,
    "sample_count": 20
  },
  "context_summary": "在此市況下此推薦等級的歷史績效良好（勝率 75%，平均回報 4.20%，樣本 20 筆）"
}
```

**邏輯説明：**
- `has_memory`: 樣本數 ≥ 5 時為 true（資料足夠）
- `confidence_adjustment`: (win_rate - 0.5) × 0.3（用於調整 AI 推薦的信心度）
  - 勝率 75% → 調整值 +0.075（增強信心）
  - 勝率 30% → 調整值 -0.06（降低信心）
- `warnings`: 勝率 < 40% 或平均回報 < -3% 時觸發警告
- `context_summary`: 人類可讀的市況總結

## 重要原則

1. **不追高** — 如果現價已遠離建議買入價（>5%），建議等回調
2. **不抄底** — 下降結構直接排除，不管基本面多好
3. **倉位管理** — 同時持倉不超過 8-10 支，單支不超過 20%
4. **止損紀律** — 跌破 SMC 結構停損價就出，不猶豫
5. **讓利潤奔跑** — 上升結構 + 動量健康就繼續持有，不急著獲利了結
