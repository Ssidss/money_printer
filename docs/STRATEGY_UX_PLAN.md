# Multi-Strategy UX Improvement Plan — v2

> 目標：讓使用者能方便切換策略、理解每個信號的原因、比較不同策略表現
> v2: 整合 GPT Review 的 6 個缺口修正

---

## 一、現狀盤點

### 已完成
- **V3 回測引擎**：Signal → Decision → Order → Fill → Position 完整 pipeline
- **3 個策略**：SMC v2 (trend) / Momentum Breakout (breakout) / Explosion Scanner (breakout)
- **回測 UI**：策略 checkbox 選擇 + 參數設定 + 14 個 metrics + 拆分報表
- **API**：7 個 v3 endpoints (run/status/result/trades/equity/splits)

### 回測表現 (Validation 2023-2024)
| 策略 | CAGR | Sharpe | MDD | Trades |
|------|------|--------|-----|--------|
| Explosion (score≥50) | +26.9% | 1.84 | 8.8% | 76 |
| Momentum (10d breakout) | +24.6% | 1.49 | 12.1% | 192 |
| SMC v2 (baseline) | +6.6% | 0.57 | 12.2% | 189 |

### 現有頁面
1. **Dashboard** — 市場概覽 + 持倉摘要（目前用 v1 分析系統）
2. **股票清單** — 34 支追蹤股票列表 + SMC 趨勢
3. **個股頁面** — K 線圖 + SMC OB/FVG 標記 + 分析歷史
4. **策略回測** — V3 回測引擎 UI（只有回測，沒有即時分析）
5. **開盤簡報** — 每日持倉 + watchlist 彙整

---

## 二、問題定義

### P0 — 使用者不知道「現在用什麼策略」
- 沒有全站策略狀態
- Dashboard 和股票清單永遠顯示 v1 分析結果
- V3 的三個策略只能在回測頁面切換，無法應用到即時分析

### P1 — 不知道「為什麼在這個點買」
- Trade log 只顯示 ticker、entry/exit price、PnL
- Signal 的 meta data（突破幅度、量比、爆擊分數、SMC 條件數）沒有暴露給使用者
- 回測結果無法追溯單筆交易的決策邏輯

### P2 — 無法比較策略
- 回測結果只保留最後一次，跑新的就覆蓋
- 沒有 A/B 比較視圖
- 不知道同一支股票在不同策略下的推薦差異

### P3 — 策略和即時分析是兩個世界
- 回測引擎 (V3) 和即時分析 (V1/V2 SMC) 是完全獨立的系統
- 使用者無法用回測驗證過的策略來做即時決策
- 開盤簡報只用 V1 的 composite_score

---

## 三、解題方案

### 3.1 策略面板（Strategy Panel）— 解決 P0

**概念**：全站右側浮動面板，類似左側導航欄

```
┌─────────────────────────────────┐
│ 📊 當前策略                    │ ← 可收合
│                                 │
│ ● Explosion Scanner        ✓   │ ← 選中的策略
│   score ≥ 50, stop 8%, target 25% │
│   CAGR +26.9% | Sharpe 1.84   │
│                                 │
│ ○ Momentum Breakout            │
│   10d breakout, vol ≥ 1.5x    │
│   CAGR +24.6% | Sharpe 1.49   │
│                                 │
│ ○ SMC v2                       │
│   min_cond=3, rr≥2.0          │
│   CAGR +6.6%  | Sharpe 0.57   │
│                                 │
│ [管理策略...]                   │
└─────────────────────────────────┘
```

**策略狀態模型**（GPT Review #1 修正：支援多策略模式）：
```typescript
type StrategyState = {
  mode: "single" | "multi"          // 單策略 or 多策略視角
  selectedStrategies: string[]       // 已選策略列表
  primaryStrategy: string            // 主策略（排序/過濾依據）
  panelOpen: boolean                 // 面板開關
}
```
- `single` 模式：全站按 primaryStrategy 顯示，最常用
- `multi` 模式：個股頁面同時顯示所有 selectedStrategies 的分析，Dashboard 用組合視角

**實作方式**：
- React Context: `StrategyContext` 提供策略狀態給全站
- UI 狀態（面板開關、排序方式）→ localStorage
- 使用者策略偏好（預設策略、模式）→ 後端 user preference（GPT Review #2：跨裝置同步）
- 策略定義（名稱 + 參數 + metrics）從 API 讀取

### 3.2 即時信號分析（Live Signal）— 解決 P0 + P3

**核心問題**：回測引擎的策略邏輯如何用於即時分析？

**方案**：新增 API endpoint，用 V3 策略對單支股票產生當日 Signal

```
GET /api/v3/signals/{ticker}?strategy=explosion_scanner
```

**Response**（GPT Review #3+#4 修正：加入資料新鮮度 + EOD/盤中區分）:
```json
{
  "ticker": "NVDA",
  "strategy": "explosion_scanner",
  "date": "2026-04-11",
  "signal_mode": "eod",              // "eod"=收盤驗證(可信) | "intraday_preview"=盤中預估(參考)
  "data_as_of": "2026-04-11T16:00:00",
  "market_session": "close",         // "pre_market" | "intraday" | "close"
  "source": "live",                  // "live"=即時計算 | "cache"=快取
  "cache_age_sec": 0,
  "signal": {
    "action": "buy",
    "confidence": 0.75,
    "entry": 115.20,
    "stop": 106.00,
    "target": 144.00,
    "rr_ratio": 3.13,
    "position_tier": "探索",
    "explanation": {
      "headline": "爆擊分數 72 — 放量突破 20 日高點",
      "factors": [
        {"name": "量比", "value": "3.2x", "score": 18, "max": 30},
        {"name": "單日漲幅", "value": "+5.3%", "score": 10, "max": 20},
        {"name": "連漲天數", "value": "3天", "score": 10, "max": 15},
        {"name": "突破新高", "value": "20日新高", "score": 8, "max": 15},
        {"name": "量加速", "value": "1.8x", "score": 5, "max": 10},
        {"name": "低價優勢", "value": "$115", "score": 0, "max": 10}
      ],
      "total_score": 72
    }
  },
  "stale": false
}
```

**計算速度**：
- Momentum/Explosion: <0.1 秒/支，可以即時算
- SMC: ~2-3 秒/支，需要 cache

**資料儲存方案**：
```sql
CREATE TABLE strategy_signal_cache (
  id SERIAL PRIMARY KEY,
  ticker VARCHAR(20),
  strategy_name VARCHAR(50),
  signal_date DATE,
  signal_data JSONB,        -- 完整 signal + explanation
  computed_at TIMESTAMP,
  UNIQUE(ticker, strategy_name, signal_date)
);
```
- 34 stocks × 3 strategies × 1 天 = 102 rows/天
- 保留 30 天 = 3,060 rows — 完全不是問題
- Momentum/Explosion 即時計算不需 cache
- SMC 用 cache，TTL 1 天

### 3.3 交易解釋（Trade Explanation）— 解決 P1

**在 Trade Log 中加入 `explanation` 欄位**

每筆交易展開後顯示：

```
NVDA | 2024-03-15 買入 $880.00 → 2024-04-02 賣出 $950.00 | +7.95%
─────────────────────────────────────────────────
📊 策略：Momentum Breakout
🔍 信號原因：
   • 突破 10 日高點 (+3.2%)
   • 放量確認 (量比 2.1x)
   • RSI 62.3 (健康區間)
🎯 ATR-based 規劃：
   • Entry $880 → Stop $850 (2×ATR) → Target $950 (3×ATR)
   • R:R = 2.33 → 標準倉位
🏁 出場原因：目標價達成
```

**實作**：
- Signal.meta 已經存了所有資訊（breakout_pct, volume_ratio, explosion_score 等）
- Position.to_trade_record() 已包含 meta
- 前端只需展開 trade row 時渲染 meta

### 3.4 結果歷史 & 比較（Result History）— 解決 P2

**方案**：在記憶體中保留最近 N 次回測結果

```typescript
// 前端 state
type BacktestHistoryItem = {
  id: string              // timestamp-based
  strategy: string        // "explosion_scanner"
  params: Record<string, any>
  summary: BacktestV3Summary
  timestamp: string
}

// 最多保留 10 筆
const [history, setHistory] = useState<BacktestHistoryItem[]>([])
```

**比較視圖**：
```
┌─────────────────────────────────────────────────┐
│ 策略比較                                         │
│                                                   │
│           Explosion  Momentum   SMC v2            │
│ CAGR      +26.9%     +24.6%     +6.6%            │
│ Sharpe    1.84       1.49       0.57              │
│ MDD       8.8%       12.1%      12.2%            │
│ Trades    76         192        189               │
│ Win Rate  43.4%      52.6%      46.6%            │
│ PF        2.07       1.55       1.20              │
└─────────────────────────────────────────────────┘
```

v1 先用前端暫存（localStorage + state）；若需持久比較，再升級為後端 backtest_runs 表。（GPT Review #5）

---

## 四、影響範圍

### 新增
| 項目 | 描述 |
|------|------|
| `StrategyContext` | React Context，管理全站策略狀態 |
| `StrategyPanel` | 右側浮動面板組件 |
| `TradeDetail` | Trade log 展開詳情組件 |
| `StrategyCompare` | 比較視圖組件 |
| `GET /api/v3/signals/{ticker}` | 即時信號 API |
| `GET /api/v3/signals/batch` | 批次信號 API（for Dashboard） |
| `strategy_signal_cache` table | 信號快取表 |

### 修改
| 項目 | 改什麼 |
|------|--------|
| Dashboard | 加入策略選擇，按當前策略排序 |
| 股票清單 | 加入策略信號欄位 |
| 個股頁面 | 顯示所有策略的分析卡片 |
| 開盤簡報 | 按當前策略的信號排序 |
| BacktestV3Panel | 加入結果歷史 + 比較 + trade detail |

### 不改
- 回測引擎 (engine.py) — 不動
- 策略邏輯 (strategies/) — 不動
- 現有 v1/v2 API — 不動（向下相容）

---

## 五、實作順序（GPT Review 修正版）

| 階段 | 內容 | 預估工作量 |
|------|------|-----------|
| **Phase A** | StrategyContext + StrategyPanel + localStorage | 小 |
| **Phase B** | 即時信號 API + 個股頁面策略卡片 + fallback UI | 中 |
| **Phase D** | Trade Detail 展開 + explanation | 小 |
| **Phase E** | 結果歷史 + 比較視圖 | 小 |
| **Phase C** | Dashboard/股票清單 策略整合 | 中 |
| **Phase F** | 開盤簡報策略整合 | 小 |

**順序：A → B → D → E → C → F**（GPT 建議：先打通資料流再擴 UI）

理由：
- A 是基礎設施，全站策略狀態
- **B 緊接 A**（原本排第4）：沒有 Live Signal API，Strategy Panel 只是空殼
- D + E 補可解釋性與比較
- C/F 最後擴散到更多頁面

---

## 六、錯誤與不可用狀態處理（GPT Review #6）

每個 Signal response 和策略卡片都必須支援：
```json
{
  "status": "ok|unavailable|insufficient_data|computing|error",
  "message": "資料不足，需至少 60 根 K 棒"
}
```

**前端 fallback 規則**：
- `ok` → 正常渲染
- `computing` → skeleton + loading spinner
- `insufficient_data` → 灰色卡片 + 說明文字
- `unavailable` → 隱藏或顯示「策略不適用」
- `error` → 紅色警告 + retry 按鈕

---

## 七、待討論的設計決策

1. **策略參數是否讓使用者自訂？**
   - 目前是 hardcode 最佳參數
   - 要不要讓使用者自己調 breakout_period, score_threshold 等？
   - 建議：提供 2-3 個 preset（保守/標準/積極），不開放完全自訂

2. **即時信號要不要自動跑？**
   - 選項 A：使用者手動點「分析」才跑
   - 選項 B：切換策略時自動跑全部 34 支
   - 建議：Momentum/Explosion 自動跑（< 4 秒），SMC 手動觸發

3. **信號是否要發通知？**
   - 例如 Explosion score > 60 自動推 Telegram
   - 建議：Phase F 之後再考慮，不在此範圍內

4. **策略面板的位置？**
   - 右側浮動（類似 Notion 的 sidebar）
   - 頂部 toolbar dropdown
   - 建議：右側浮動，可收合，因為需要顯示參數和 metrics
