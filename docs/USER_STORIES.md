# Multi-Strategy System — User Stories & I/O Spec

> 每個 Story 定義明確的 Input / Output，作為實作完成的驗收標準
> 對應設計文件：`MULTI_STRATEGY_DESIGN.md` v3.1

---

## Phase 1A：最小可回測引擎

### US-1A-01：Signal 產生

```
身為：策略開發者
我要：任何策略都能產出標準化 Signal
以便：不同策略的輸出可以被同一個 Decision Engine 消費

Input:
  - ticker: "NVDA"
  - provider: HistoricalProvider（日期 = 2024-03-15）
  - strategy: SMCStrategy

Output (Signal):
  - signal_id: UUID（非空）
  - ticker: "NVDA"
  - side: "long"
  - action: "buy" | "sell" | "hold" | "watch"
  - confidence: 0.0 ~ 1.0
  - strategy_name: "smc_v2"
  - strategy_type: "trend"
  - timeframe: "1d"
  - timestamp: 2024-03-15
  - expiry: 2024-03-18（3 天後）
  - price_hint: {"entry": 880.0, "stop": 850.0, "target": 950.0, "rr_ratio": 2.33}
    或 None（watch/hold 信號）

驗收：
  ✅ Signal 所有必填欄位非空
  ✅ confidence 在 [0, 1] 範圍內
  ✅ strategy_type 是 enum: trend | breakout | mean_reversion | sentiment
  ✅ expiry > timestamp
  ✅ 沒有 price_hint 的 signal，action 不能是 "buy"
```

### US-1A-02：DataProvider 時間隔離

```
身為：回測引擎
我要：HistoricalProvider 嚴格控制可見數據範圍
以便：策略不可能看到未來數據（防 lookahead bias）

Input:
  - provider = HistoricalProvider(start="2024-01-01", end="2024-12-31")
  - provider.current_date() → 2024-06-15
  - strategy 呼叫 provider.get_ohlcv("NVDA", lookback=60)

Output:
  - DataFrame 最後一行日期 ≤ 2024-06-15
  - DataFrame 行數 ≤ 60
  - 不包含 2024-06-16 之後的任何數據

驗收：
  ✅ get_ohlcv 回傳的 max(date) == current_date
  ✅ advance_day() 後 current_date 前進一個交易日
  ✅ 策略無法直接存取 DB（沒有 session/connection 參數）
  ✅ get_latest_price() 回傳 current_date 的 close
  ✅ current_date 在 end 之後 → raise StopIteration 或回傳 None
```

### US-1A-03：DataProvider 股票池過濾

```
身為：回測引擎
我要：Provider 能過濾掉不可交易的股票
以便：策略不會對停牌/低流動性股票產生信號

Input:
  - provider.is_tradable("NVDA") → 正常股票
  - provider.is_tradable("DELIST") → 已下市
  - provider.is_tradable("LOWVOL") → 近 5 日均量 < 100,000

Output:
  - "NVDA" → True
  - "DELIST" → False
  - "LOWVOL" → False

驗收：
  ✅ 價格資料不足 lookback 天 → False
  ✅ 近 5 天平均成交量 < 100,000 → False
  ✅ 近 5 天有缺資料 → False
  ✅ get_universe() 只回傳 is_tradable == True 的 tickers
```

### US-1A-04：BaseStrategy Interface

```
身為：策略開發者
我要：所有策略共用同一個 interface
以便：回測引擎不需要知道策略內部邏輯

Input:
  - class SMCStrategy(BaseStrategy)
  - strategy.generate_signals("NVDA", provider) 

Output:
  - list[Signal]（可能 0~N 個）

驗收：
  ✅ BaseStrategy 是 ABC，定義 generate_signals(ticker, provider) → list[Signal]
  ✅ BaseStrategy 定義 strategy_name / strategy_type 屬性
  ✅ SMCStrategy 繼承 BaseStrategy 並實作所有 abstract methods
  ✅ generate_signals 不接受 DB session 參數（只能透過 provider）
```

### US-1A-05：SizingModel 固定風險計算

```
身為：決策引擎
我要：根據風險預算計算應買股數
以便：每筆交易的最大虧損被控制在固定比例

Input:
  sizing = SizingModel(risk_per_trade_pct=1.0, max_position_pct=20.0)
  
  Case A: equity=100000, entry=100, stop=95
  Case B: equity=100000, entry=500, stop=475
  Case C: equity=100000, entry=10, stop=5（極寬停損）
  Case D: entry=100, stop=100（無效停損）
  Case E: entry=100, stop=105（stop > entry，做多不合理）

Output:
  Case A: risk_amount=1000, risk_per_share=5, shares=200
          max_by_position = 100000*20%/100 = 200 → min(200,200) = 200
  Case B: risk_amount=1000, risk_per_share=25, shares=40
          max_by_position = 100000*20%/500 = 40 → min(40,40) = 40
  Case C: risk_amount=1000, risk_per_share=5, shares=200
          max_by_position = 100000*20%/10 = 2000 → min(200,2000) = 200
  Case D: 0 股（除以零保護）
  Case E: 0 股（stop >= entry 不合理）

驗收：
  ✅ 正常 case 計算正確
  ✅ entry <= stop → return 0
  ✅ 不超過 max_position_pct 上限
  ✅ 回傳 int（無條件捨去）
```

### US-1A-06：最小回測循環

```
身為：交易者
我要：用新引擎對 SMC v2 跑回測
以便：驗證新引擎的正確性，並補算 CAGR/Sharpe

Input:
  - strategy: SMCStrategy
  - tickers: ["NVDA", "AMD", "TSM"]（或完整追蹤股票池）
  - period: 2023-01-01 ~ 2024-12-31
  - initial_capital: 100,000
  - sizing: SizingModel(risk_per_trade_pct=1.0)
  - execution: ExecutionModel(fill_type="next_open")

Output:
  - total_return_pct: float
  - total_trades: int
  - win_rate: float
  - equity_curve: list[{date, equity, drawdown_pct}]
  - trade_log: list[Position]（closed trades）

每日循環步驟：
  1. provider.advance_day()
  2. 更新所有 open positions 的 current_price / unrealized_pnl
  3. 檢查出場條件（stop/target/expiry）→ 平倉
  4. for ticker in universe: strategy.generate_signals(ticker, provider)
  5. 過濾過期 signals（current_date > signal.expiry → 丟棄）
  6. signals → decisions（Phase 1A 用單策略直通）
  7. decisions → orders → execution（T+1 open fill）
  8. 記錄 equity curve

Mark-to-market 規則：
  - Execution 用當日 open price（T+1 fill）
  - Valuation 用當日 close price（equity curve / unrealized_pnl）
  - 信號在 close 後產生，所以 close 是最合理的估值基準

驗收：
  ✅ 新引擎 SMC 回測的 total_return 與舊引擎誤差 < 5%
  ✅ 新引擎 SMC 回測的 win_rate 與舊引擎誤差 < 5%
  ✅ equity_curve 每天一筆，日期連續（跳過非交易日）
  ✅ trade_log 每筆都有完整的 entry/exit 資訊
  ✅ cash + position_value == equity（每天都平衡）
  ✅ 補算出 CAGR / Sharpe / Sortino
  ✅ 過期 signal（current_date > expiry）不得轉為 decision
  ✅ position.current_price 用 close（不是 open / mid）
```

---

## Phase 1B：風控骨架

### US-1B-01：T+1 Open 執行

```
身為：回測引擎
我要：信號在下一個交易日開盤價執行
以便：消除 lookahead bias

Input:
  - Day T (2024-03-15) close: strategy 產出 Signal(action="buy", entry_hint=880)
  - Day T+1 (2024-03-18, 跳過週末) open: 885

Output:
  - fill_price = 885 × (1 + slippage) = 885.44（0.05% slippage）
  - fill_date = 2024-03-18
  - 不是 Day T 的 close

驗收：
  ✅ fill_date > signal.timestamp
  ✅ fill_price 基於 T+1 open（不是 T close）
  ✅ slippage 已扣除
  ✅ commission 已扣除（如果有）
```

### US-1B-02：Gap 進場保護

```
身為：回測引擎
我要：跳空過大時取消進場
以便：避免在異常價格開倉

Input:
  - Signal on Day T: entry_hint = 100
  - Day T close = 100
  - Day T+1 open = 108（+8% gap）
  - gap_threshold = 5%

Output:
  - 取消進場，不開倉
  - log: "Gap 8.0% > threshold 5.0%, order cancelled"

Input 2:
  - Day T close = 100
  - Day T+1 open = 103（+3% gap）

Output 2:
  - 正常開倉，fill_price = 103 × (1 + slippage)

驗收：
  ✅ gap > threshold → 不開倉
  ✅ gap ≤ threshold → 正常開倉
  ✅ gap 計算 = abs(T+1_open - T_close) / T_close
```

### US-1B-03：保守 Intraday Path（Long）

```
身為：回測引擎
我要：用 Open→Low→High→Close 的保守路徑判斷出場
以便：不高估績效

Input:
  - Open position: entry=100, stop=95, target=115
  - Day candle: open=102, low=94, high=116, close=110

Output:
  - 先檢查 low ≤ stop → 94 ≤ 95 ✅ → exit at stop_price = 95
  - 不檢查 target（因為保守路徑假設 low 先到）
  - exit_reason = "stop"
  - realized_pnl = (95 - 100) × shares

Input 2:（只觸及 target）
  - Day candle: open=102, low=96, high=116, close=110

Output 2:
  - low=96 > stop=95 → 不觸發 stop
  - high=116 > target=115 → exit at target_price = 115
  - exit_reason = "target"

Input 3:（都沒觸及）
  - Day candle: open=102, low=96, high=113, close=110

Output 3:
  - 持倉繼續
  - 更新 MAE = min(MAE, 96 - 100) = -4
  - 更新 MFE = max(MFE, 113 - 100) = 13

驗收：
  ✅ 同天 stop 和 target 都觸及 → 觸發 stop（不是 target）
  ✅ 只觸及 target → 觸發 target
  ✅ 都沒觸及 → 持倉繼續 + 更新 MAE/MFE
  ✅ exit_price 是 stop_price 或 target_price（不是 low/high）
```

### US-1B-04：Gap Stop 出場（致命重要）

```
身為：回測引擎
我要：跳空穿越停損時用 open price 出場
以便：反映真實市場的滑價

Input:
  - Open position: entry=100, stop=95, target=115
  - Day T+5 candle: open=92, low=90, high=98, close=93

Output:
  - open=92 < stop=95 → Gap Stop 觸發
  - exit_price = 92（open price，不是 95！）
  - exit_reason = "gap_stop"
  - realized_pnl = (92 - 100) × shares = -8 per share

Input 2:（Gap Up 穿越 target）
  - Day candle: open=118, low=116, high=122, close=120

Output 2:
  - open=118 > target=115 → Gap Profit 觸發
  - exit_price = 118（open price，不是 115）
  - exit_reason = "gap_profit"

驗收：
  ✅ open < stop → exit at open_price（不是 stop_price）
  ✅ open > target → exit at open_price（不是 target_price）
  ✅ 正常觸及（非 gap）→ exit at stop_price 或 target_price
  ❌ 絕對不能出現 gap down 但用 stop_price 出場的情況
```

### US-1B-05：Order 建立與狀態管理

```
身為：回測引擎
我要：Decision 和 Position 之間有 Order 層
以便：gap cancel / partial fill / 狀態追蹤有明確歸屬

Input:
  - Decision(action="open", ticker="NVDA", size_pct=10%)
  - SizingModel 算出 requested_shares = 50

Output (Order):
  - order_id: UUID
  - ticker: "NVDA"
  - side: "long"
  - order_type: "market"（v1 只做 market）
  - requested_shares: 50
  - status: "pending"
  - created_date: Day T
  - linked_decision_id / linked_signal_ids

狀態流轉：
  pending → filled     （T+1 open 正常成交）
  pending → cancelled  （gap > threshold / 資金不足 / signal 過期）
  pending → partial    （Phase 4+ 預留，v1 不實作）

驗收：
  ✅ 每個 Decision 產生恰好 1 個 Order
  ✅ gap cancel → order.status = "cancelled"，不產生 Position
  ✅ fill 成功 → order.status = "filled"，產生 Position
  ✅ Order 記錄 fill_price / fill_date / fill_shares（成交後填入）
  ✅ 回測報表可查詢：cancelled orders 數量 + 原因分布
  ✅ Order 不可跨天 pending（當天沒成交 = cancelled）
```

### US-1B-06：Portfolio Risk Cap（原 1B-05）

```
身為：風控系統
我要：所有持倉的同時停損風險不超過 5%
以便：尾部風險受控

Input:
  - equity = 100,000
  - max_portfolio_risk_pct = 5.0（最大同時風險 = 5,000）
  - 已持倉：
    Position A: entry=100, stop=95, 100 shares → risk = 500
    Position B: entry=50, stop=47, 200 shares → risk = 600
  - current_total_risk = 1,100
  - 新信號：entry=200, stop=190 → risk_per_share = 10
  - SizingModel 計算 shares = 1000 / 10 = 100 股

Output:
  - remaining_risk_budget = 5,000 - 1,100 = 3,900
  - risk_amount = 100 × 10 = 1,000 ≤ 3,900 → 允許，100 股

Input 2:（接近上限）
  - current_total_risk = 4,600
  - remaining = 5,000 - 4,600 = 400
  - 原本想買 100 股（risk=1,000）

Output 2:
  - 縮減到 400 / 10 = 40 股

驗收：
  ✅ 新倉 + 既有倉的總風險 ≤ max_portfolio_risk_pct
  ✅ 超出時縮減股數，不是直接跳過
  ✅ trailing stop 上移後，既有倉 risk 降低 → 釋放 budget
  ✅ 浮盈超過 1R + 保本停損 → risk 視為 0
```

### US-1B-07：三層回測報表（原 1B-06）

```
身為：交易者
我要：回測完成後看到三層結構化報表
以便：從不同粒度評估策略表現

Input:
  - 回測完成的 Portfolio 物件

Output Level 1 — Portfolio Summary:
  {
    "total_return_pct": 15.3,
    "cagr_pct": 7.8,
    "max_drawdown_pct": -12.5,
    "sharpe_ratio": 1.2,
    "sortino_ratio": 1.8,
    "calmar_ratio": 0.624,        # CAGR / MDD
    "profit_factor": 2.1,
    "win_rate_pct": 65.0,
    "total_trades": 48,
    "avg_holding_days": 12,
    "expectancy": 1.5,            # win% × avg_win - loss% × avg_loss
    "avg_exposure_pct": 45.0,
    "max_consecutive_losses": 4,
    "tail_risk_cvar_5pct": -3.2,  # 最差 5% 交易的平均虧損%
  }

Output Level 2 — Strategy Breakdown:
  {
    "smc_v2": { ...same metrics... },
    "momentum_breakout": { ...same metrics... },
    "by_regime": { "trending": {...}, "ranging": {...} },
    "by_tier": { "核心": {...}, "標準": {...}, "探索": {...} },
    "correlation_matrix": { "smc_v2 × momentum": 0.35 }
  }

Output Level 3 — Trade Log:
  [
    {
      "signal_id": "uuid-xxx",
      "strategy_name": "smc_v2",
      "ticker": "NVDA",
      "entry_date": "2024-01-15",
      "entry_price": 550.0,
      "exit_date": "2024-02-10",
      "exit_price": 620.0,
      "exit_reason": "target",
      "gross_pnl": 1430.0,
      "commission": 0.0,
      "slippage_cost": 30.0,
      "net_pnl": 1400.0,
      "pnl_pct": 12.7,
      "mae": -15.0,
      "mfe": 75.0,
      "holding_days": 26,
      "confidence": 0.85
    },
    ...
  ]

驗收：
  ✅ Level 1 所有 14 個 metrics 都有值
  ✅ Level 2 按策略拆分（Phase 1B 只有 SMC，但結構要支援多策略）
  ✅ Level 3 每筆 trade 有完整 entry/exit/pnl/mae/mfe
  ✅ Level 3 每筆 trade 拆分 gross_pnl / commission / slippage_cost / net_pnl
  ✅ 可回答「策略本身好不好 vs 交易成本吃掉多少」
  ✅ Sharpe 用 daily returns 年化（× √252）
  ✅ Calmar = CAGR / abs(MDD)
  ✅ CVaR 5% = 最差 5% 交易的平均 pnl_pct
```

### US-1B-08：Train/Validation/Test 切分（原 1B-07）

```
身為：交易者
我要：回測引擎強制執行資料切分
以便：防止過擬合

Input:
  - 使用者指定 split = "train" | "validation" | "test"
  - 或指定自訂日期範圍

Output:
  - train:      2018-01-01 ~ 2022-12-31
  - validation:  2023-01-01 ~ 2024-12-31
  - test:        2025-01-01 ~ now

驗收：
  ✅ 預設三段日期範圍正確
  ✅ 回測報表標明使用的 split
  ✅ API 回傳包含 split 資訊
  ✅ 自訂日期範圍也可以（但報表標 "custom"）
```

### US-1B-09：Kill Switch 熔斷（原 1B-08）

```
身為：風控系統
我要：回測中觸發熔斷條件時自動停止開倉
以便：模擬真實的系統保護機制

Input:
  - 回測進行中
  - 當前 drawdown = 31%（> 30% 門檻）

Output:
  - kill_switch 觸發
  - 從此日起不開新倉
  - 已持倉正常按 stop/target 出場
  - 報表記錄：kill_switch_triggered = true, trigger_date, trigger_reason

Input 2:
  - 連續虧損 = 16 筆

Output 2:
  - kill_switch 觸發
  - trigger_reason = "連續虧損 16 > 15"

驗收：
  ✅ MDD > 30% → 觸發
  ✅ 連續虧損 > 15 → 觸發
  ✅ 單日虧損 > 5% → 觸發
  ✅ 觸發後不開新倉，但不強制平倉
  ✅ 報表有 kill switch 資訊
  ✅ kill_switch.enabled = False → 不觸發（可關閉做研究用）
```

---

## Phase 2：新策略

### US-2-01：Momentum Breakout 策略

```
身為：交易者
我要：追蹤突破 N 日高點 + 放量的股票
以便：捕捉趨勢啟動的機會

Input:
  - ticker: "SMCI"
  - provider: 提供 OHLCV + indicators
  - breakout_period: 20（日）
  - volume_ratio_min: 1.5

Output (Signal):
  - action: "buy"（如果今日 close > 20 日最高 + 成交量 > 1.5× 均量）
  - confidence: 基於突破幅度 + 放量程度
  - price_hint:
    entry: 下一日 open
    stop: entry - 2 × ATR(14)
    target: entry + 3 × ATR(14)（或 trailing）
  - strategy_name: "momentum_breakout"
  - strategy_type: "breakout"

驗收：
  ✅ 突破 + 放量 → buy signal
  ✅ 沒突破 or 沒放量 → hold/watch signal 或空
  ✅ price_hint 包含 ATR-based stop/target
  ✅ 繼承 BaseStrategy interface
  ✅ Validation Sharpe > 0.5（Research Gate）
```

### US-2-02：Explosion Scanner 策略 Wrapper

```
身為：交易者
我要：把已完成的爆擊掃描器包成標準策略
以便：接入回測引擎比較

Input:
  - 現有 scanner.py 的 explosion_score + 6 指標
  - 包成 ExplosionStrategy(BaseStrategy)

Output (Signal):
  - action: "buy"（explosion_score ≥ 60）
  - confidence: explosion_score / 100
  - price_hint:
    entry: 下一日 open
    stop: entry × 0.92（固定 -8%）
    target: entry × 1.25（固定 +25%）
  - strategy_name: "explosion_scanner"
  - strategy_type: "breakout"

驗收：
  ✅ 複用現有 scanner 邏輯
  ✅ 遵循 BaseStrategy interface
  ✅ explosion_score < 40 → 不產生 buy signal
```

### US-2-03：Re-entry Cooldown（Phase 2 再決定是否實作）

```
身為：交易者
我要：同一 ticker 出場後有冷卻期
以便：避免 whipsaw 連續打臉

Input:
  - NVDA: Day T breakout → buy
  - Day T+1: stop hit → exit
  - Day T+2: 又 breakout signal

Output（cooldown_days=3）:
  - Day T+2 的 signal 被過濾掉（距上次 exit 只過 1 天 < 3 天）
  - Day T+4 的 signal 可以執行

驗收：
  ✅ 同 ticker exit 後 N 天內不產生 buy decision
  ✅ cooldown 只針對同策略（SMC exit 不影響 Momentum re-entry）
  ✅ cooldown_days = 0 → 不啟用（預設）

備註：此 story 為可選項。Phase 2 回測時若出現頻繁 whipsaw，再啟用。
```

### US-2-04：策略相關性分析（原 2-03）

```
身為：交易者
我要：比較不同策略的報酬相關性
以便：確認分散效果

Input:
  - SMC daily_returns: [0.5%, -0.3%, 1.2%, ...]
  - Momentum daily_returns: [0.8%, -0.1%, 0.9%, ...]

Output:
  - correlation_matrix:
    {
      "smc_v2 × momentum_breakout": 0.45,
      "smc_v2 × explosion_scanner": 0.30,
      "momentum × explosion": 0.72
    }

驗收：
  ✅ 相關性在 [-1, 1] 範圍
  ✅ 同類策略（momentum × explosion）相關性預期較高
  ✅ 報表 Level 2 包含此矩陣
  ✅ 相關性 > 0.7 → 警告標記
```

---

## Phase 3：分帳戶

### US-3-01：Split Account 回測

```
身為：交易者
我要：用分帳戶模式同時跑多個策略
以便：比較組合 vs 單獨的表現

Input:
  - total_capital: 100,000
  - allocation:
    core (smc_v2): 70% → 70,000
    momentum: 20% → 20,000
    explosion: 10% → 10,000
  - 各帳戶獨立運作

Output:
  - 各帳戶獨立 equity curve
  - 組合 equity curve = sum(各帳戶 equity)
  - 組合 metrics vs 各帳戶 metrics

驗收：
  ✅ 各帳戶資金互不影響（A 虧損不影響 B 的可用資金）
  ✅ Decision.capital_pool 正確分流
  ✅ 組合 MDD < max(各帳戶 MDD)（分散有效）
  ✅ 同類策略合計曝險 ≤ 60%
  ✅ 報表按 capital_pool 拆分
```

---

## 跨 Phase 通用驗收

### US-X-01：不可竄改已完成交易

```
驗收：
  ✅ closed trade 的 exit_price / exit_date / exit_reason 不可被修改
  ✅ trade_log 只增不改
  ✅ 回測完成後 sum(realized_pnl) + unrealized_pnl + cash = equity
```

### US-X-02：同天多信號優先順序

```
Input:
  - Day T+1 有 3 個 decisions:
    close NVDA (exit signal)
    open AMD (confidence=0.8)
    open TSLA (confidence=0.6)
  - 資金只夠開 1 個新倉

Output:
  1. 先執行 close NVDA → 釋放資金
  2. 再開 AMD（confidence 較高）
  3. TSLA → 縮小倉位到剩餘資金，或跳過（< 最低門檻）

驗收：
  ✅ 出場優先於進場
  ✅ 進場按 confidence 降序
  ✅ 資金不足 → 縮小，不是直接跳過
  ✅ 縮小後 < min_trade_value → 才跳過
```

### US-X-03：Equity Balance 恆等式

```
每日回測循環結束後：

  cash + sum(position.current_price × position.size) == equity

  equity_curve[-1]["equity"] == portfolio.equity

  sum(all closed_trades realized_pnl) + sum(all open unrealized_pnl) 
    == equity - initial_capital - total_commission - total_slippage

驗收：
  ✅ 每天都通過 balance check（回測引擎內建 assertion）
  ✅ 如果不平衡 → raise error，不是 silent
```

---

## 驗收總表

| Phase | Story | 核心驗收點 | 優先級 |
|-------|-------|-----------|--------|
| 1A | US-1A-01 | Signal 標準化 | P0 |
| 1A | US-1A-02 | Provider 時間隔離 | P0 |
| 1A | US-1A-03 | Provider 股票池過濾 | P1 |
| 1A | US-1A-04 | BaseStrategy interface | P0 |
| 1A | US-1A-05 | SizingModel 計算 | P0 |
| 1A | US-1A-06 | 最小回測循環 | P0 |
| 1B | US-1B-01 | T+1 Open 執行 | P0 |
| 1B | US-1B-02 | Gap 進場保護 | P0 |
| 1B | US-1B-03 | 保守 Intraday Path | P0 |
| 1B | US-1B-04 | Gap Stop 出場 | P0（致命） |
| 1B | US-1B-05 | Order 建立與狀態 | P0 |
| 1B | US-1B-06 | Portfolio Risk Cap | P1 |
| 1B | US-1B-07 | 三層報表（含 cost breakdown） | P1 |
| 1B | US-1B-08 | Train/Valid/Test 切分 | P0 |
| 1B | US-1B-09 | Kill Switch | P1 |
| 2 | US-2-01 | Momentum Breakout | P0 |
| 2 | US-2-02 | Explosion Wrapper | P2 |
| 2 | US-2-03 | Re-entry Cooldown | P2（可選）|
| 2 | US-2-04 | 策略相關性 | P1 |
| 3 | US-3-01 | Split Account | P0 |
| X | US-X-01 | 不可竄改交易 | P0 |
| X | US-X-02 | 多信號優先序 | P0 |
| X | US-X-03 | Equity Balance | P0（回測正確性基石）|
