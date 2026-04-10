# Multi-Strategy Trading System — Design Document

> 目標：自己交易賺錢，先賺錢再說（工程夠用就好，不過度抽象）
> 狀態：設計階段，待 Review
> 最後更新：2026-04-10

---

## 一、現狀

### 目前有什麼

| 模組 | 狀態 | 說明 |
|------|------|------|
| 歷史股價 OHLCV | ✅ 完成 | yfinance → PostgreSQL |
| 新聞 + 情緒分析 | ✅ 完成 | 爬蟲 + sentiment scoring |
| SMC v2 結構分析 | ✅ 完成 | OB/FVG/BOS/CHoCH/Fib |
| 分層決策 | ✅ 完成 | SMC → 動量 → 催化劑 → 條件計數 |
| 回測 v2 | ✅ 完成 | 綁死 SMC 策略，close fill 74% 勝率 |
| 量價異常掃描器 | ✅ 完成 | 6 指標爆擊分數，追蹤股+外部池 |
| 多租戶/認證 | ✅ 完成 | JWT + per-user portfolio |

### 目前的問題

1. **只有一套策略**（SMC + 動量），無法比較、無法組合
2. **回測引擎綁死 SMC**，新策略無法直接接入回測
3. **Signal 沒有標準化**，不同模組的輸出格式不一致
4. **沒有 Position/Portfolio 抽象**，回測中的持倉管理是 ad-hoc 的
5. **數據取用沒有統一介面**，策略直接 call DB

### 現有回測基線（SMC Strategy D/G）

| 指標 | 數據 |
|------|------|
| Fill Model | close（收盤價成交） |
| Min Conditions | 3 |
| Total Return | +10.6% |
| Win Rate | 74% |
| Max Drawdown | -22% |
| Profit Factor | 2.76 |
| CAGR | 待補算 |
| Sharpe | 待補算 |

---

## 二、目標架構

```
┌──────────────────────────────────────────────────────────┐
│                    Data Layer（數據層）                    │
│                                                          │
│  DataProvider interface                                   │
│  ├── PriceProvider    → OHLCV, realtime                  │
│  ├── IndicatorProvider → MA, ATR, RSI, MACD, BB, Volume  │
│  ├── SentimentProvider → news score, social mentions     │
│  ├── MarketProvider   → VIX, SPY/QQQ trend, regime      │
│  └── (future) OptionsProvider, FundamentalProvider       │
│                                                          │
│  策略不直接碰 DB，全部透過 Provider 取數據                  │
│  Provider 可以 mock（回測用 historical）或 live（實盤用）    │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│                  Strategy Layer（策略層）                   │
│                                                          │
│  BaseStrategy interface:                                  │
│    generate_signals(ticker, provider) → list[Signal]      │
│                                                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │
│  │  SMC v2      │ │  Momentum    │ │  Explosion   │ ...  │
│  │  (現有改裝)   │ │  Breakout    │ │  Scanner     │      │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘      │
│         │                │                │              │
│         ▼                ▼                ▼              │
│                   Signal（統一格式）                       │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│                Decision Layer（決策層）                     │
│                                                          │
│  DecisionEngine:                                          │
│    signals[] → decisions[]                                │
│                                                          │
│  模式：                                                   │
│    A. 單策略直通（只聽某一個策略）                            │
│    B. 同類投票（同 type 的策略投票）                         │
│    C. 加權（按近期表現動態調權重）                            │
│    D. 分帳戶（每個策略獨立資金池）                            │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│              Execution Layer（執行層）                      │
│                                                          │
│  Decision → Order → Fill → Position                       │
│                                                          │
│  Portfolio:                                               │
│    cash, positions[], equity_curve                         │
│  Position:                                                │
│    ticker, size, entry_price, stop, current_pnl           │
│  ExecutionModel:                                          │
│    fill_model (market/limit/close)                         │
│    slippage, commission                                    │
│    T+1 rule（信號日 T → 執行日 T+1 開盤）                   │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│              Backtest Engine（回測引擎）                    │
│                                                          │
│  通用引擎，不綁任何策略：                                    │
│    輸入：Strategy + 股票池 + 時間範圍 + 初始資金              │
│    每天：provider.advance_day() → strategy.generate()      │
│          → decision → execution → position update          │
│    輸出：統一 metrics（return, MDD, Sharpe, PF, win_rate） │
│                                                          │
│  支援：                                                   │
│    - 單策略回測                                            │
│    - 多策略組合回測（Ensemble）                              │
│    - A vs B 策略比較                                       │
│    - 參數掃描（grid search）                                │
└──────────────────────────────────────────────────────────┘
```

---

## 三、Signal 設計（核心中的核心）

### 原則：Signal = Opinion，不是 Trade

```python
@dataclass
class Signal:
    # ── 必填 ──
    ticker: str
    action: str                     # "buy" | "sell" | "hold" | "watch"
    confidence: float               # 0.0 ~ 1.0
    strategy_name: str              # "smc_v2" | "momentum_breakout" | ...
    strategy_type: str              # "trend" | "mean_reversion" | "breakout" | "sentiment"
    timestamp: datetime             # 信號產生時間
    expiry: datetime                # 信號過期時間（超過就作廢）

    # ── 選填（策略自由填）──
    price_hint: Optional[dict] = None
    # {
    #     "entry": 142.00,          # 建議進場價
    #     "stop": 135.00,           # 建議停損
    #     "target": 166.00,         # 目標價
    #     "rr_ratio": 3.8,          # 風報比
    #     "position_tier": "標準",   # 倉位等級
    # }

    meta: dict = field(default_factory=dict)
    # 策略專屬資訊，格式自由
    # SMC: {"trend": "uptrend", "ob_level": 142.5, "fvg_zone": [140, 143]}
    # Momentum: {"breakout_level": 150, "volume_ratio": 3.5}
```

### 為什麼這樣設計

| 設計決策 | 原因 |
|---------|------|
| `price_hint` optional | 情緒策略沒有 entry/stop，不該強制 |
| `expiry` 必填 | 防止信號過期還在用，尤其是 breakout 信號時效很短 |
| `strategy_type` 必填 | 決策層要知道「這是趨勢類還是均值回歸類」，同類投票 |
| `confidence` 必填 | 決策層需要權重依據 |
| `meta` 自由格式 | 每個策略的內部資訊不同，不該強制統一 |

---

## 四、DataProvider 設計

### 原則：策略不碰 DB，不碰 API

```python
class DataProvider:
    """策略的唯一數據來源"""

    # 價格
    def get_ohlcv(self, ticker: str, lookback: int = 252) -> pd.DataFrame: ...
    def get_latest_price(self, ticker: str) -> float: ...

    # 技術指標（provider 算好，策略直接拿）
    def get_indicators(self, ticker: str) -> dict: ...
    # {"rsi_14": 65.3, "macd": 2.1, "ma_20": 150.5, "atr_14": 3.2, ...}

    # 情緒
    def get_sentiment(self, ticker: str) -> Optional[dict]: ...
    # {"score": 72, "label": "正面", "article_count": 5}

    # 市場狀態
    def get_market_regime(self) -> dict: ...
    # {"vix": 18.5, "spy_trend": "uptrend", "regime": "trending"}

    # 回測專用：推進到下一天
    def advance_day(self) -> date: ...
    def current_date(self) -> date: ...
```

### 兩種實作

| 模式 | 實作 | 用途 |
|------|------|------|
| `HistoricalProvider` | 從 DB 載入歷史數據，advance_day() 模擬時間推進 | 回測 |
| `LiveProvider` | 從 DB + yfinance 即時數據 | 實盤信號產生 |

### 為什麼不讓策略自己撈數據

1. **回測無法 mock** — 策略直接 call DB，回測時無法控制「它看到哪天的數據」
2. **Lookahead bias** — 策略可能不小心看到未來數據
3. **耦合** — 換數據源（例如從 yfinance 換到 polygon）要改每個策略

---

## 五、Execution / Position / Portfolio

### 關鍵流程

```
Signal → Decision → Order → Fill → Position → PnL

具體：
Day T 收盤後：
  1. provider 更新到 Day T 數據
  2. strategy.generate_signals() 基於 Day T 數據
  3. decision_engine 決定要不要執行
  4. 產生 Order（buy NVDA, market, size=5%）

Day T+1 開盤：
  5. execution_model.fill(order, T+1 open price)
  6. 扣除 slippage + commission
  7. 建立 Position
  8. portfolio.update()
```

### 防 Lookahead Bias（致命重要）

```
❌ 錯誤：Day T 收盤信號 → Day T 收盤價成交
✅ 正確：Day T 收盤信號 → Day T+1 開盤價成交

❌ 錯誤：用 Day T 的 high/low 判斷是否觸及 entry
✅ 正確：用 Day T-1 的數據產生信號，Day T 的 open 成交
```

### Position

```python
@dataclass
class Position:
    ticker: str
    side: str               # "long" | "short"（目前只做 long）
    size: int               # 股數
    entry_price: float
    entry_date: date
    stop_price: Optional[float]
    target_price: Optional[float]
    strategy_name: str      # 哪個策略開的

    # 動態更新
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    mae: float              # Maximum Adverse Excursion
    mfe: float              # Maximum Favorable Excursion
    holding_days: int
```

### Portfolio

```python
@dataclass
class Portfolio:
    initial_capital: float
    cash: float
    positions: list[Position]

    @property
    def equity(self) -> float:
        return self.cash + sum(p.current_price * p.size for p in self.positions)

    @property
    def exposure_pct(self) -> float:
        return (self.equity - self.cash) / self.equity * 100

    equity_curve: list[dict]    # [{"date": ..., "equity": ..., "drawdown": ...}]
```

### ExecutionModel

```python
@dataclass
class ExecutionModel:
    fill_type: str = "next_open"    # "next_open" | "next_close" | "limit"
    slippage_pct: float = 0.05      # 0.05% 滑價
    commission_per_trade: float = 0  # 手續費（美股多數 $0）
    max_position_pct: float = 20.0  # 單支最大倉位
    max_positions: int = 10         # 最多同時持有
```

---

## 六、策略清單（計劃中）

### Phase 2 — 第一批策略

| # | 策略名稱 | Type | 數據需求 | 說明 |
|---|---------|------|---------|------|
| 1 | **SMC v2** | trend | OHLCV | 現有改裝，OB/FVG/結構進出場 |
| 2 | **Momentum Breakout** | breakout | OHLCV + Volume | 突破 N 日高 + 放量 → 追進，ATR trailing stop |
| 3 | **Explosion Scanner** | breakout | OHLCV + Volume | 掃描器信號觸發（量比>5x + 漲幅>10%），快進快出 |

### Phase 4 — 第二批策略

| # | 策略名稱 | Type | 數據需求 | 說明 |
|---|---------|------|---------|------|
| 4 | **Mean Reversion** | mean_reversion | OHLCV + BB + RSI | RSI 超賣 + 觸及 BB 下軌 → 反彈 |
| 5 | **Sentiment Momentum** | sentiment | 新聞 + 社群 | 情緒突變 + 正面爆發 → 跟進 |
| 6 | **Regime Adaptive** | meta | VIX + SPY | 根據市場狀態切換策略權重 |

### 暫不做

| 策略 | 原因 |
|------|------|
| Options | 數據複雜（需要期權鏈），先不碰 |
| 財報驅動 | 頻率太低（季度），ROI 不划算 |
| 高頻/日內 | 需要即時數據 + 低延遲，架構不支援 |

---

## 七、決策引擎（Ensemble）

### 階段 1：簡單模式

```python
class DecisionEngine:
    mode: str  # "single" | "vote" | "weighted" | "split_account"

    # 單策略：直接用某策略的信號
    # 投票：同 strategy_type 的信號投票，多數決
    # 加權：按 confidence × weight 加權
    # 分帳戶：每個策略有獨立資金池
```

### 階段 2：進階模式

1. **動態權重** — 按近 30 天策略表現調整權重（表現好的加權）
2. **Regime 切換** — 趨勢市用 trend/breakout，盤整市用 mean_reversion
3. **相關性控制** — 兩個策略高度相關時，不要同時重倉

### 策略衝突處理

```
同類策略衝突（SMC vs Momentum，都是 trend 類）：
  → 投票，多數決

不同類策略衝突（Trend 看多 vs Mean Reversion 看空）：
  → 不衝突！分帳戶各自操作
  → 或者：regime 判斷當前適合哪類，聽那類的
```

---

## 八、數據層擴充優先順序

> 原則：先用最少數據支撐最多策略

### Tier 1（現有，支撐 80% 策略）
- [x] OHLCV 歷史股價
- [x] 技術指標（MA, RSI, MACD, BB, ATR, Volume）
- [x] 新聞情緒

### Tier 2（下一步，支撐 regime 判斷）
- [ ] VIX 指數
- [ ] SPY/QQQ 趨勢（已有但未結構化）
- [ ] 市場 breadth（漲跌比、新高新低數）

### Tier 3（再下一步，支撐社群策略）
- [ ] Reddit/StockTwits 提及數 + 情緒
- [ ] Google Trends 搜索量

### Tier 4（暫不做）
- [ ] Options chain（IV, OI, Greeks）
- [ ] 財報數據（EPS, Revenue）
- [ ] 盤中即時數據

---

## 九、Roadmap

### Phase 1：基礎設施（策略可插拔）

> 目標：讓系統「可擴展」，新策略接進來不用改引擎

- [ ] Signal dataclass 定義（含 expiry, strategy_type）
- [ ] DataProvider interface + HistoricalProvider 實作
- [ ] BaseStrategy interface
- [ ] Position + Portfolio dataclass
- [ ] ExecutionModel（T+1 open, slippage, commission）
- [ ] Backtest v3 通用引擎（不綁策略）
- [ ] 把現有 SMC v2 包成第一個 BaseStrategy 實作
- [ ] 驗證：SMC 在新引擎的回測結果 ≈ 舊引擎（不能差太多）

### Phase 2：第二策略 + 驗證

> 目標：證明「多策略有用」，如果這裡沒 alpha 就不往下做

- [ ] Momentum Breakout 策略實作
- [ ] Explosion Scanner 策略實作
- [ ] 回測比較：SMC vs Momentum vs Explosion
- [ ] 補算所有策略的 CAGR / Sharpe / Sortino
- [ ] 如果新策略沒有比 SMC 好 → 調參或放棄，不硬做

### Phase 3：Ensemble v1

> 目標：多策略組合是否比單策略好

- [ ] DecisionEngine 實作（vote / weighted / split_account）
- [ ] 組合回測：SMC + Momentum ensemble vs 各自單獨
- [ ] 分帳戶模式：核心(SMC) 70% + 搏擊(Momentum+Explosion) 30%
- [ ] 前端：多策略信號對比頁面

### Phase 4：強化

- [ ] Regime detection（VIX + MA → trending/ranging/volatile）
- [ ] 動態權重（近 N 天表現 → 權重調整）
- [ ] 策略相關性控制
- [ ] 更多策略（Mean Reversion, Sentiment）

---

## 十、技術決策記錄

| 決策 | 選擇 | 原因 |
|------|------|------|
| Signal 是 Opinion 不是 Trade | price_hint optional | 情緒策略沒有 entry/stop |
| 策略透過 DataProvider 取數據 | 不直接碰 DB | 回測可 mock、防 lookahead |
| T+1 open 成交 | 不用 T close | 防 lookahead bias |
| 先做 2-3 個策略就好 | 不貪多 | 先證明 alpha 存在再擴展 |
| 數據擴充按 tier | OHLCV → VIX → 社群 → Options | 先用最少數據支撐最多策略 |
| 分帳戶模式優先 | 不急著做 ensemble | 各策略先獨立證明自己有效 |
| 先賺錢再說 | 不過度工程化 | 目標是自己交易賺錢，不是做產品 |

---

## 十一、已知風險 & 待解決

| 風險 | 嚴重度 | 狀態 |
|------|--------|------|
| 現有 SMC 回測缺 CAGR/Sharpe | 中 | 待補算 |
| Lookahead bias 在舊回測中可能存在 | 高 | Phase 1 重建引擎時修復 |
| 策略過擬合（參數調太多） | 高 | 需要 out-of-sample 測試 |
| 外部數據源穩定性（yfinance 限流） | 中 | 考慮 polygon.io 或 alpha vantage 備援 |
| 爆擊策略勝率極低，心理壓力大 | 中 | 分帳戶 + 嚴格停損 |

---

## 十二、Review 要求

這份文件需要外部 Review，重點確認：

1. **Signal 設計** 是否完整（有沒有漏掉什麼必要欄位）
2. **DataProvider** 是否夠用（回測 mock 的可行性）
3. **Execution 流程** T+1 是否正確，有沒有其他 bias 風險
4. **策略優先順序** 是否合理
5. **分帳戶 vs Ensemble** 哪個先做比較好
6. **Phase 1 的範圍** 會不會太大或太小
