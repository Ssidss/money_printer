# Multi-Strategy Trading System — Design Document v3

> 目標：自己交易賺錢，先賺錢再說（工程夠用就好，不過度抽象）
> 最高原則：**先證明 alpha 存在再擴展**
> 狀態：v3.1 — Final spec，可以開工
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
| 量價異常掃描器 | ✅ 完成 | 6 指標爆擊分數，追蹤股+外部池，前後端已上線 |
| 多租戶/認證 | ✅ 完成 | JWT + per-user portfolio |

### 目前的問題

1. **只有一套策略**（SMC + 動量），無法比較、無法組合
2. **回測引擎綁死 SMC**，新策略無法直接接入回測
3. **Signal 沒有標準化**，不同模組的輸出格式不一致
4. **沒有 Position/Portfolio 抽象**，回測中的持倉管理是 ad-hoc 的
5. **數據取用沒有統一介面**，策略直接 call DB
6. **沒有資料切分規範**，回測結果可能過擬合
7. **缺少關鍵 metrics**（CAGR, Sharpe, expectancy）

### 現有回測基線（SMC Strategy D/G）

| 指標 | 數據 |
|------|------|
| Fill Model | close（收盤價成交） |
| Min Conditions | 3 |
| Total Return | +10.6% |
| Win Rate | 74% |
| Max Drawdown | -22% |
| Profit Factor | 2.76 |
| CAGR | 待補算（Phase 1A 完成後） |
| Sharpe | 待補算（Phase 1A 完成後） |

---

## 二、目標架構

```
┌──────────────────────────────────────────────────────────────┐
│                    Data Layer（數據層）                        │
│                                                              │
│  DataProvider interface                                       │
│  ├── get_ohlcv(ticker, lookback)                             │
│  ├── get_latest_price(ticker)                                │
│  ├── get_indicators(ticker) → RSI, MACD, MA, ATR, BB, Vol   │
│  ├── get_sentiment(ticker) → score, label                    │
│  ├── get_market_regime() → VIX, SPY trend, regime            │
│  ├── get_universe() → tradable tickers                       │
│  ├── is_tradable(ticker) → bool                              │
│  ├── current_date() / advance_day()                          │
│  └── (future) get_options(), get_fundamentals()              │
│                                                              │
│  實作：HistoricalProvider（回測）/ LiveProvider（實盤）          │
│  策略不直接碰 DB，全部透過 Provider，可 mock                     │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│                  Strategy Layer（策略層）                       │
│                                                              │
│  BaseStrategy.generate_signals(ticker, provider) → Signal[]   │
│                                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│  │  SMC v2      │ │  Momentum    │ │  Explosion   │ ...      │
│  │  (trend)     │ │  (breakout)  │ │  (breakout)  │          │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘          │
│         │                │                │                  │
│         ▼                ▼                ▼                  │
│                   Signal（統一格式）                           │
│          含 signal_id / side / timeframe / expiry             │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│                Decision Layer（決策層）                         │
│                                                              │
│  Signal[] → Decision[] → Order[]                              │
│                                                              │
│  DecisionEngine 模式：                                        │
│    A. 單策略直通                                               │
│    B. 分帳戶（每策略獨立資金池）← Phase 3 首選                    │
│    C. 同類投票 + 不同類分資金                                    │
│    D. 動態加權（按近期表現）                                     │
│                                                              │
│  Position Sizing:                                             │
│    固定風險模型：每筆承擔 account_risk% / (entry - stop)         │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│              Execution Layer（執行層）                          │
│                                                              │
│  Order → Fill → Position → Portfolio                          │
│                                                              │
│  嚴格規則：                                                    │
│    1. Day T close 產生信號                                     │
│    2. Day T+1 open 嘗試成交                                    │
│    3. 跳空超過閾值 → 可取消交易                                  │
│    4. 出場觸發價格模型固定（日內 high/low or 收盤）               │
│    5. slippage + commission 扣除                               │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│              Backtest Engine（回測引擎）                        │
│                                                              │
│  通用引擎，不綁任何策略：                                        │
│    輸入：Strategy + 股票池 + 時間範圍 + 初始資金                  │
│    每天：provider.advance_day() → strategy.generate()          │
│          → decision → execution → position update              │
│    輸出：三層報表（Portfolio / Strategy / Trade）                │
│                                                              │
│  資料切分（鐵律）：                                              │
│    Train (調參) → Validation (選模型) → Test (只看一次)          │
│    看過 test 後修改 → 必須重切資料重做                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、Signal 設計

### 原則：Signal = Opinion，不是 Trade

```python
@dataclass
class Signal:
    # ── 必填 ──
    signal_id: str              # UUID，追蹤信號生命週期
    ticker: str
    side: str                   # "long"（預留 short）
    action: str                 # "buy" | "sell" | "hold" | "watch"
    confidence: float           # 0.0 ~ 1.0
    strategy_name: str          # "smc_v2" | "momentum_breakout" | ...
    strategy_type: str          # "trend" | "breakout" | "mean_reversion" | "sentiment"
    timeframe: str              # "1d" | "1w" | "1h"（避免不同時間框架混在一起）
    timestamp: datetime         # 信號產生時間
    expiry: datetime            # 信號過期時間（超過就作廢）

    # ── 選填 ──
    price_hint: Optional[dict] = None
    # {
    #     "entry": 142.00,
    #     "stop": 135.00,
    #     "target": 166.00,
    #     "rr_ratio": 3.8,
    #     "position_tier": "標準",
    # }

    meta: dict = field(default_factory=dict)
    # 策略專屬資訊，格式自由
    # SMC: {"trend": "uptrend", "ob_level": 142.5, "conditions_met": 3}
    # Momentum: {"breakout_level": 150, "volume_ratio": 3.5, "atr": 4.2}
```

### 設計決策

| 欄位 | 為什麼 |
|------|--------|
| `signal_id` | 追蹤哪個信號開倉/失效，回測 trade log 必須 |
| `side` | 現在只做 long，但先留欄位避免未來改資料結構 |
| `timeframe` | SMC 日線 vs breakout 週線不能混，決策層需要知道 |
| `expiry` | breakout 信號可能只有 1-2 天有效，過期就不該執行 |
| `price_hint` optional | 情緒策略沒有 entry/stop，不該強制 |
| `confidence` | 決策層需要權重依據 |
| `meta` 自由格式 | 每個策略的內部資訊不同 |

---

## 四、Decision 設計

### 原則：Signal 是意見，Decision 是行動

同一個 ticker 可能同時收到 3 個 signals，但 portfolio 只能做 1 個決策。

```python
@dataclass
class Decision:
    ticker: str
    action: str                 # "open" | "close" | "reduce" | "hold"
    side: str                   # "long"
    size_pct: float             # 佔資金池的 %（由 sizing model 計算）
    size_shares: Optional[int] = None  # Execution 階段填入，Decision 不負責算
    strategy_name: str          # 主要來源策略
    capital_pool: str = "default"  # 分帳戶模式："core" | "momentum" | "explosion" | "default"
    reason: str                 # 人可讀的決策理由
    linked_signal_ids: list[str]  # 關聯的 signal_id（可多個）
    priority: int = 0           # 同天多個 decision 的優先順序
```

### 職責邊界（鐵律）

```
Decision 只表達「意圖」（想買多少風險）
SizingModel 算出「目標股數」→ 產生 Order
Execution 根據實際資金與開盤價成交 → Order.status = filled → 產生 Position

完整 pipeline: Signal → Decision → Order → Fill → Position

❌ 不能在 Decision 和 Execution 各算一次部位
```

### Signal → Decision 的轉換邏輯

```
同一 ticker 多個 signals 的處理：

1. 分帳戶模式：
   每個策略的 signal 獨立轉成 decision，互不影響

2. 投票模式：
   同 strategy_type 的 signals 投票
   action 多數決，confidence 取最高
   不同 strategy_type 的 signals 分開處理

3. 加權模式：
   score = sum(confidence × weight) for each signal
   score > threshold → decision = buy
```

### Order（Decision 和 Position 之間的橋樑）

```python
@dataclass
class Order:
    order_id: str               # UUID
    ticker: str
    side: str                   # "long"
    order_type: str = "market"  # v1 只做 market
    requested_shares: int = 0
    status: str = "pending"     # "pending" | "filled" | "cancelled"
    created_date: date = None
    linked_decision_id: str = ""
    linked_signal_ids: list[str] = field(default_factory=list)
    capital_pool: str = "default"

    # ── 成交後填入 ──
    fill_price: Optional[float] = None
    fill_date: Optional[date] = None
    fill_shares: Optional[int] = None
    cancel_reason: Optional[str] = None  # "gap" | "insufficient_funds" | "expired"
```

> Order 不可跨天 pending — 當天沒成交 = cancelled。
> v1 只做 market order，limit / partial fill 留 Phase 4+。

---

## 五、DataProvider 設計

### 原則：策略不碰 DB，不碰 API

```python
class DataProvider(ABC):
    """策略的唯一數據來源"""

    # ── 價格 ──
    @abstractmethod
    def get_ohlcv(self, ticker: str, lookback: int = 252) -> pd.DataFrame: ...
    @abstractmethod
    def get_latest_price(self, ticker: str) -> float: ...

    # ── 技術指標 ──
    @abstractmethod
    def get_indicators(self, ticker: str) -> dict: ...
    # {"rsi_14": 65.3, "macd": 2.1, "ma_20": 150.5, "atr_14": 3.2, "bb_upper": ..., ...}

    # ── 情緒 ──
    @abstractmethod
    def get_sentiment(self, ticker: str) -> Optional[dict]: ...
    # {"score": 72, "label": "正面", "article_count": 5}

    # ── 市場狀態 ──
    @abstractmethod
    def get_market_regime(self) -> dict: ...
    # {"vix": 18.5, "spy_trend": "uptrend", "regime": "trending"}

    # ── 股票池 ──
    @abstractmethod
    def get_universe(self) -> list[str]: ...
    @abstractmethod
    def is_tradable(self, ticker: str) -> bool: ...
    # 停牌 / 資料不足 / 流動性太差 → False

    # ── 時間控制（回測用）──
    @abstractmethod
    def current_date(self) -> date: ...
    @abstractmethod
    def advance_day(self) -> date: ...
```

### 兩種實作

| 模式 | 實作 | 用途 |
|------|------|------|
| `HistoricalProvider` | 從 DB 載入歷史數據，advance_day() 模擬時間推進 | 回測 |
| `LiveProvider` | 從 DB + yfinance 即時數據 | 實盤信號產生 |

### is_tradable 過濾條件

- 價格資料不足 lookback 天 → False
- 近 5 天平均成交量 < 100,000 → False（流動性不足）
- 近 5 天有缺資料（停牌/暫停交易）→ False

---

## 六、Position Sizing（一級公民）

### 原則：用風險控制倉位大小，不用固定比例

```
❌ 固定比例：每筆投 10% 資金
   問題：停損 2% 的股票和停損 15% 的股票，風險完全不同

✅ 固定風險：每筆承擔總資金 X% 的風險
   size = (account × risk_per_trade) / (entry - stop)
```

### Position Sizing Model

```python
@dataclass
class SizingModel:
    risk_per_trade_pct: float = 1.0       # 每筆最多虧總資金的 1%
    max_position_pct: float = 20.0      # 單支最大不超過 20%
    max_positions: int = 10             # 最多同時持有 10 支
    max_exposure_pct: float = 100.0     # 總曝險上限
    max_portfolio_risk_pct: float = 5.0 # 所有持倉同時停損的最大虧損 ≤ 5%

    def calculate_shares(
        self, equity: float, entry: float, stop: float
    ) -> int:
        if entry <= stop:
            return 0
        risk_amount = equity * (self.risk_per_trade_pct / 100)
        risk_per_share = entry - stop
        shares = int(risk_amount / risk_per_share)
        # 限制最大倉位
        max_shares = int(equity * (self.max_position_pct / 100) / entry)
        shares = min(shares, max_shares)

        # ── Portfolio-level risk cap ──
        # 所有持倉同時停損的總虧損不能超過 max_portfolio_risk_pct
        # current_total_risk = sum(each position's risk_amount)
        # remaining_risk_budget = equity * max_portfolio_risk_pct/100 - current_total_risk
        # if remaining_risk_budget < risk_amount:
        #     shares = int(remaining_risk_budget / risk_per_share)
        return shares

    # ── Portfolio Risk 計算統一口徑 ──
    # position_risk = abs(current_effective_stop - entry_price) × shares
    # 若 trailing stop 已上移 → 用最新 stop（risk 可能趨近 0）
    # 若浮盈已超過 1R → risk 視為 0（保本停損）
    # current_total_risk = sum(所有 open position 的 position_risk)
    # 回測與實盤必須用同一算法
```

### 沒有 stop 的信號怎麼辦

- 如果 `price_hint` 沒有 stop → 使用 ATR-based 預設停損
- 預設停損 = entry - 2 × ATR(14)
- 如果連 entry 都沒有 → 不開倉（watch/hold 信號不執行）

---

## 七、Execution 規則（六條鐵律）

> **v3 僅支援 long-only。** 若未來加入 short，需重新定義 short 倉位的保守 intraday path（Open→High→Low→Close）與 gap 規則。

### 鐵律 1：信號與執行分離

```
Day T 收盤後 → 產生 Signal（基於 Day T 及之前的數據）
Day T+1 開盤 → 嘗試執行 Fill
```

### 鐵律 2：Intraday Path Assumption（保守路徑）

> 真實市場中，我們不知道日內價格先到 high 還是先到 low。
> 必須選一個「一致的假設」，否則回測結果不可重現。

```
對 Long 倉位，假設價格路徑為：

  Open → Low → High → Close

含義：
  1. 先檢查是否觸及停損（price hit low first）
  2. 再檢查是否觸及停利（price hit high second）

這會「低估績效」（因為假設最壞情況先發生），但安全。
同一天同時觸及停損和停利 → 觸發停損。

❌ 絕對不用 Open → High → Low → Close（樂觀路徑會高估績效）
```

### 鐵律 3：Gap 保護（進場 + 出場）

```
── 進場 Gap 保護 ──
if abs(T+1_open - T_close) / T_close > gap_threshold:
    cancel_order()  # 跳空太大，取消進場

gap_threshold = 5%（預設）

── 出場 Gap 保護（致命重要）──
已持倉時，如果開盤跳空穿越停損/停利：

  Gap Down Stop（多單）：
    if open_price < stop_price:
        exit_price = open_price  # 不是 stop_price！
        # 真實市場中，止損單會以開盤價成交，不是你設的價

  Gap Up Profit（多單）：
    if open_price > target_price:
        exit_price = open_price  # 以開盤價獲利了結

❌ 絕對不能用 exit_price = stop_price 當跳空的成交價
   這會嚴重高估績效，實盤會「暴死」
```

### 鐵律 4：同天多信號優先順序

```
1. 先處理出場信號（close/reduce）→ 釋放資金
2. 再處理進場信號（open）→ 按 confidence 降序
3. 資金不足時 → 縮小倉位到可用資金，而不是直接跳過
   actual_size = min(requested_size, available_cash × 0.95)
   如果縮小後 size < 最低門檻（例如 1 股）→ 才跳過
```

### 鐵律 5：出場觸發價格模型

```
使用日內 high/low 判斷（搭配鐵律 2 的保守路徑）：

  Step 1: 開盤檢查
    open < stop → gap stop（鐵律 3）
    open > target → gap profit（鐵律 3）

  Step 2: 日內檢查（保守路徑 open→low→high→close）
    low ≤ stop → exit at stop_price
    high ≥ target → exit at target_price

  Step 3: 收盤
    都沒觸及 → 持倉繼續
    更新 MAE = min(MAE, low - entry)
    更新 MFE = max(MFE, high - entry)
```

### 鐵律 6：不可竄改已完成的交易

```
回測中一旦 position 被 close：
  - 不可修改 exit_price / exit_date / exit_reason
  - 不可「假設如果沒出場會怎樣」
  - closed trade 直接進入 trade log，不可逆
```

### ExecutionModel

```python
@dataclass
class ExecutionModel:
    fill_type: str = "next_open"        # "next_open" | "next_close"
    slippage_pct: float = 0.05          # 0.05% 滑價
    commission_per_trade: float = 0     # 美股多數 $0
    gap_threshold_pct: float = 5.0      # 進場跳空超過 5% → 取消
    gap_stop_enabled: bool = True       # 出場跳空 → 用 open price
    path_assumption: str = "conservative"  # "conservative" = open→low→high→close
    min_trade_value: float = 100.0      # 縮小倉位後的最低交易金額
```

---

## 八、Position & Portfolio

### Position

```python
@dataclass
class Position:
    position_id: str            # UUID
    ticker: str
    side: str                   # "long"
    size: int                   # 股數
    entry_price: float
    entry_date: date
    stop_price: Optional[float]
    target_price: Optional[float]
    strategy_name: str
    linked_signal_id: str       # 開倉的 signal_id

    # ── 動態更新（每天回測循環中更新）──
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    mae: float = 0.0            # Max Adverse Excursion（最大浮虧）
    mfe: float = 0.0            # Max Favorable Excursion（最大浮盈）
    holding_days: int = 0

    # ── 平倉後填入 ──
    exit_price: Optional[float] = None
    exit_date: Optional[date] = None
    exit_reason: Optional[str] = None   # "stop" | "target" | "signal_reversal" | "time_stop"
    realized_pnl: Optional[float] = None
    realized_pnl_pct: Optional[float] = None
```

### Portfolio

```python
@dataclass
class Portfolio:
    initial_capital: float
    cash: float
    positions: list[Position]       # open positions
    closed_trades: list[Position]   # closed positions（完整 trade log）
    equity_curve: list[dict]        # [{"date": ..., "equity": ..., "drawdown_pct": ...}]

    @property
    def equity(self) -> float:
        return self.cash + sum(p.current_price * p.size for p in self.positions)

    @property
    def exposure_pct(self) -> float:
        if self.equity <= 0:
            return 0
        return (self.equity - self.cash) / self.equity * 100

    @property
    def open_position_count(self) -> int:
        return len(self.positions)
```

---

## 九、回測報表（三層）

### Level 1：Portfolio Summary

| 指標 | 說明 |
|------|------|
| Total Return % | 總報酬 |
| CAGR % | 年化報酬 |
| Max Drawdown % | 最大回撤 |
| Sharpe Ratio | 風險調整報酬 |
| Sortino Ratio | 下行風險調整報酬 |
| Profit Factor | 總獲利 / 總虧損 |
| Win Rate % | 勝率 |
| Total Trades | 總交易次數 |
| Avg Holding Days | 平均持有天數 |
| Expectancy | 期望值 = win_rate × avg_win - loss_rate × avg_loss |
| Exposure % | 平均曝險比例 |
| Max Consecutive Losses | 最大連續虧損次數 |
| Calmar Ratio | CAGR / Max Drawdown（越高越好，>1 算不錯）|
| Tail Risk (CVaR 5%) | 最差 5% 交易的平均虧損（Expected Shortfall）|

### Level 2：Strategy Breakdown

| 指標 | 說明 |
|------|------|
| 每個策略的獨立 metrics | 跟 Level 1 相同指標，按策略拆分 |
| 按 market regime 拆分 | trending / ranging / volatile 各自績效 |
| 按 position tier 拆分 | 核心 / 標準 / 探索 各自績效 |
| 策略相關性矩陣 | 策略 A 和 B 的報酬是否高度相關 |

### Level 3：Trade Log

| 欄位 | 說明 |
|------|------|
| signal_id, strategy_name | 來源追蹤 |
| ticker, entry_date, entry_price | 進場資訊 |
| exit_date, exit_price, exit_reason | 出場資訊 |
| pnl_pct, pnl_amount | 損益 |
| mae, mfe | 最大浮虧/浮盈 |
| holding_days | 持有天數 |
| conditions_met, confidence | 信號品質 |

---

## 十、資料切分規範（鐵律）

### 三段切分

```
Train:       2018-01-01 ~ 2022-12-31  （調參數用）
Validation:  2023-01-01 ~ 2024-12-31  （選模型/策略用）
Test:        2025-01-01 ~ 2026-04-10  （最終驗證，只看一次）
```

### 規則

1. **Train 上調參** — 可以反覆調整策略參數
2. **Validation 上選模型** — 比較不同策略/參數組合，選最好的
3. **Test 只看一次** — 最終結果，不能回去改
4. **看過 Test 後修改任何東西** → 必須重切資料，Test 段作廢
5. **Walk-forward（進階）** — 滾動窗口驗證，Phase 4 再考慮

### 最低標準

一個策略要通過驗證：
- Train 和 Validation 的 metrics 不能差太多（穩定性）
- Validation 的 Sharpe > 0.5
- Validation 的 Profit Factor > 1.5
- Test 結果與 Validation 方向一致

---

## 十一、策略清單

### Phase 2 — 第一批新策略

| # | 策略名稱 | Type | 數據需求 | 工作量 | 說明 |
|---|---------|------|---------|--------|------|
| 1 | **SMC v2** | trend | OHLCV | 改裝 | 現有邏輯包成 BaseStrategy |
| 2 | **Momentum Breakout** | breakout | OHLCV + Vol | 新寫 | 突破 N 日高 + 放量 → 追進，ATR trailing |
| 3 | **Explosion Scanner** | breakout | OHLCV + Vol | 0.5 天 | 掃描器已做完，包成 Strategy wrapper |

> Momentum 和 Explosion 都是 breakout 類型，共用 ATR trailing stop 基礎設施。

### Phase 4 — 第二批策略

| # | 策略名稱 | Type | 數據需求 | 前置條件 |
|---|---------|------|---------|---------|
| 4 | **Mean Reversion** | mean_reversion | OHLCV + BB + RSI | 需要 regime detection |
| 5 | **Sentiment Momentum** | sentiment | 新聞 + 社群 | 需要社群數據 |
| 6 | **Regime Adaptive** | meta | VIX + SPY | 需要 market regime |

### 暫不做

| 策略 | 原因 |
|------|------|
| Options | 數據複雜（需要期權鏈），先不碰 |
| 財報驅動 | 頻率太低（季度），ROI 不划算 |
| 高頻/日內 | 需要即時數據 + 低延遲，架構不支援 |

### 策略優先順序的考量

GPT Review 建議把 Explosion 降到第 4，Mean Reversion 提前。
我們的判斷：**不同意**。理由：
1. Explosion Scanner 後端+前端已完成，包成 Strategy 只需 wrapper，工作量極低
2. Mean Reversion 需要 regime detection 才能正確使用（盤整市才有效），這在 Phase 4
3. Momentum 和 Explosion 都是 breakout 類，可以共用 ATR trailing 基建
4. 先做兩個 breakout 策略 + 一個 trend 策略，驗證不同進場邏輯的差異

---

## 十二、決策引擎

### 演進路線（從簡到繁）

```
Phase 2:  單策略模式（各自獨立跑回測，不組合）
Phase 3:  分帳戶模式（SMC 70% + Breakout 20% + Explosion 10%）
Phase 4:  投票/加權模式（同類投票 + 不同類分資金）
Phase 5:  動態加權 + Regime adaptive
```

### 為什麼分帳戶先於 Ensemble

1. 最容易落地，不需要解決策略衝突
2. 最容易診斷績效來源（哪個桶賺/虧）
3. 不會把不同策略的 edge 混在一起抵消掉
4. trend 和 mean_reversion 常互相打架，分帳戶避免這問題

### Phase 3 分帳戶建議配置

```
總資金 100%
├── 核心帳戶 70%：SMC v2（高勝率、穩定）
├── 動量帳戶 20%：Momentum Breakout（追突破）
└── 搏擊帳戶 10%：Explosion Scanner（小注快打）
```

### 策略衝突處理

```
同類策略衝突（都是 breakout）：
  → 投票，confidence 高的優先
  → 或各自在子帳戶操作

不同類策略衝突（trend 看多 vs mean_reversion 看空）：
  → 分帳戶各自操作，不互相干擾
  → Phase 5 用 regime 判斷當前適合哪類
```

### 策略相關性硬限制

```
同類策略（相同 strategy_type）的合計曝險 ≤ 60%

例如：Momentum 25% + Explosion 20% = 45%（breakout 類合計）✅
      Momentum 40% + Explosion 25% = 65%（breakout 類合計）❌ → 縮減

原因：同類策略的報酬高度相關，集中在同一類等於沒分散
Phase 2 的回測報表會產出策略相關性矩陣，用來驗證這個假設
```

---

## 十三、Exit 規則

### Phase 1-2：出場邏輯留在策略內部

每個策略定義自己的出場規則：
- **SMC v2**: OB/FVG 結構停損、結構目標停利
- **Momentum**: ATR trailing stop
- **Explosion**: 固定停損 -8%、移動停利

### Phase 4+：如果發現共用模式，再抽象

> 理由：SMC 的出場邏輯是其 edge 的核心部分，過早拆出來會破壞策略完整性。
> 等 Phase 2 做完 Momentum 後，如果發現 ATR trailing 被 2+ 策略共用，再提取 ExitPolicy。
> 這符合「先賺錢再說」— 不為假設的未來需求過度抽象。

---

## 十四、數據層擴充優先順序

> 原則：先用最少數據支撐最多策略

### Tier 1（現有，支撐 80% 策略）
- [x] OHLCV 歷史股價
- [x] 技術指標（MA, RSI, MACD, BB, ATR, Volume）
- [x] 新聞情緒

### Tier 2（Phase 4，支撐 regime 判斷）
- [ ] VIX 指數
- [ ] SPY/QQQ 趨勢（已有但未結構化）
- [ ] 市場 breadth（漲跌比、新高新低數）

### Tier 3（Phase 5+，支撐社群策略）
- [ ] Reddit/StockTwits 提及數 + 情緒
- [ ] Google Trends 搜索量

### Tier 4（暫不做）
- [ ] Options chain（IV, OI, Greeks）
- [ ] 財報數據（EPS, Revenue）
- [ ] 盤中即時數據

---

## 十五、Kill Switch（系統熔斷）

### 原則：系統失控時自動停機，不靠人的紀律

```
A. Research Gate（策略是否允許上線）

  1. Test 段 Sharpe < 0.3         → 策略沒有真正的 edge，不准上線
  2. Test 與 Validation 方向不一致  → 可能過擬合，不准上線
  3. OOS 結果偏離 Validation > 2σ  → 結構性問題，回去 debug

  ❌ 沒通過 Research Gate 的策略，連 paper trading 都不做

B. Runtime Kill Switch（運行中即時熔斷）

  1. 即時 MDD > 30%              → 虧損已超出可接受範圍
  2. 連續虧損 > 15 筆             → 可能市場 regime 改變或策略失效
  3. 單日虧損 > 5% 總資金         → 異常事件，先停再查
  4. Rolling 60-day Sharpe < 0     → 策略近期完全無效
  5. 策略即時報酬偏離 Validation > 2σ → 市場結構性改變

  觸發後行動：
    - 停止開新倉
    - 已持倉按正常停損/停利出場
    - 生成診斷報告（最近 30 天 trade log + metrics drift）
    - 人工 review 後手動重啟
```

### 回測中的 Kill Switch

```python
@dataclass
class KillSwitch:
    max_drawdown_pct: float = 30.0
    max_consecutive_losses: int = 15
    max_daily_loss_pct: float = 5.0
    min_rolling_sharpe: float = 0.0      # rolling 60-day Sharpe < 0 → 熔斷
    enabled: bool = True

    def check(self, portfolio) -> Optional[str]:
        """回傳 None = OK，回傳 str = 觸發原因"""
        if portfolio.current_drawdown_pct > self.max_drawdown_pct:
            return f"MDD {portfolio.current_drawdown_pct:.1f}% > {self.max_drawdown_pct}%"
        if portfolio.consecutive_losses > self.max_consecutive_losses:
            return f"連續虧損 {portfolio.consecutive_losses} > {self.max_consecutive_losses}"
        # ... 其他檢查
        return None
```

---

## 十六、Roadmap（務實版）

### Phase 1A：最小可回測引擎

> 目標：SMC 能在新引擎跑出接近舊引擎的結果
> 預計：2-3 天

- [ ] Signal dataclass（含 signal_id / side / timeframe / expiry）
- [ ] Decision dataclass
- [ ] BaseStrategy interface
- [ ] HistoricalProvider（從 DB 載入，advance_day 模擬）
- [ ] SizingModel（固定風險模型）
- [ ] 最小 Backtest Engine（每日循環 → signal → decision → fill → position）
- [ ] SMC v2 包成 BaseStrategy
- [ ] 驗證：新引擎 vs 舊引擎回測結果對齊（誤差 < 5%）
- [ ] 補算 SMC 基線 CAGR / Sharpe / Sortino

### Phase 1B：風控骨架

> 目標：回測結果開始可信
> 預計：1-2 天

- [ ] Position（含 MAE/MFE 追蹤）
- [ ] Portfolio（equity curve, drawdown）
- [ ] ExecutionModel（T+1, slippage, gap protection）
- [ ] 三層回測報表（Portfolio / Strategy / Trade log）
- [ ] Train/Validation/Test 切分
- [ ] 完整 metrics（expectancy, Sortino, consecutive losses, exposure）

### Phase 2：第二+第三策略

> 目標：找到獨立 edge
> 預計：2-3 天
> **關卡：如果新策略在 Validation 上沒有 Sharpe > 0.5，不往下做**

- [ ] Momentum Breakout 策略實作
- [ ] Explosion Scanner 包成 Strategy（wrapper，0.5 天）
- [ ] 三個策略各自 Train + Validation 回測
- [ ] 策略相關性分析（Momentum vs SMC 的報酬相關係數）
- [ ] OOS (out-of-sample) 驗證

### Phase 2.5：各策略 OOS 驗證

> 目標：確認不是過擬合

- [ ] 每個策略在 Test 段跑一次（只看一次！）
- [ ] 結果與 Validation 方向一致 → 通過
- [ ] 結果差很多 → 策略有問題，回去 debug

### Phase 3：Split Account

> 目標：多策略運行，各自獨立
> 前提：至少 2 個策略通過 OOS 驗證

- [ ] DecisionEngine — split_account 模式
- [ ] 資金分配：SMC 70% / Momentum 20% / Explosion 10%
- [ ] 組合回測 vs 各自單獨
- [ ] 確認組合的 MDD < 各自單獨的 MDD（分散風險）

### Phase 4：Ensemble + 強化

> 前提：Phase 3 證明分帳戶有效

- [ ] Regime detection（VIX + MA）
- [ ] Mean Reversion 策略（需要 regime）
- [ ] 動態權重（近 30 天表現 → 權重調整）
- [ ] 投票/加權模式
- [ ] 策略相關性控制

---

## 十七、技術決策記錄

| 決策 | 選擇 | 原因 |
|------|------|------|
| Signal = Opinion | price_hint optional, 加 signal_id/side/timeframe | 追蹤信號生命週期、支援多時間框架 |
| 新增 Decision 層 | Signal[] → Decision[] → Order[] | 多信號匯總成單一行動，分離意見與執行 |
| 固定風險 sizing | risk_per_trade / (entry - stop) | 比固定比例更合理，不同策略風險一致 |
| 策略透過 DataProvider | 不直接碰 DB | 回測可 mock、防 lookahead |
| T+1 open 成交 | 不用 T close | 防 lookahead bias |
| 出場邏輯留在策略內 | Phase 2 後再看是否抽象 | 不為假設需求過度工程化 |
| Explosion 保持 Phase 2 | 不降到 Phase 4 | 掃描器已完成，wrapper 工作量極低 |
| 分帳戶先於 Ensemble | Phase 3 | 最容易落地、最容易診斷、不會混掉 edge |
| Train/Valid/Test 三段 | 寫進鐵律 | 防過擬合，這是回測可信度的底線 |
| Phase 1 拆 A/B | A=最小引擎 B=風控 | 避免兩週沒結果，快速看到 SMC 在新引擎跑 |
| 保守 Intraday Path | Open→Low→High→Close | 低估績效但安全，同天觸及 stop+target → 觸發 stop |
| Gap Stop = Open Price | 不用 stop_price | 真實市場跳空會以開盤價成交，用 stop_price 會高估績效 |
| Portfolio Risk Cap 5% | 所有持倉同時停損 ≤ 5% | 10 支 × 1% = 10% 太高，用 cap 控制尾部風險 |
| Kill Switch | 5 個熔斷條件 | 系統失控時自動停機，不靠人的紀律 |
| 同類曝險 ≤ 60% | 策略相關性硬限制 | 同類策略報酬高度相關，集中等於沒分散 |

---

## 十八、已知風險

| 風險 | 嚴重度 | 對策 |
|------|--------|------|
| 現有 SMC 回測缺 CAGR/Sharpe | 中 | Phase 1A 補算 |
| 舊回測可能有 lookahead bias | 高 | Phase 1A 新引擎修復，對比結果 |
| 策略過擬合 | 高 | Train/Valid/Test 三段切分 + OOS 驗證 |
| 新策略沒有 alpha | 中 | Phase 2 關卡：Sharpe < 0.5 就不往下 |
| 外部數據源不穩定 | 中 | 考慮 polygon.io 備援 |
| 爆擊策略勝率極低 | 中 | 分帳戶 + 嚴格停損 + 最多 10% 資金 |
| 做太多工程、忘記目標 | 中 | 每個 phase 問：這會不會更快證明哪個策略能賺錢？ |

---

## 十九、Review 歷史

### v1 Review（2026-04-10，GPT-4）

評分：7.8 / 10

採納的修正：
1. Signal 補 signal_id / side / timeframe ✅
2. Decision 獨立結構 ✅
3. Position sizing 固定風險模型 ✅
4. Train/Valid/Test 三段切分 ✅
5. 三層回測報表 ✅
6. 分帳戶先於 Ensemble ✅
7. Phase 1 拆 A/B ✅
8. DataProvider 補 get_universe / is_tradable ✅

挑戰 GPT 的地方：
1. **Exit Policy 抽象化** — 延後到 Phase 4，不在 Phase 1 做。出場邏輯是策略 edge 的核心，過早抽象化違反「先賺錢再說」。
2. **Explosion Scanner 優先順序** — 維持 Phase 2。掃描器已完成，包成 Strategy 只需 wrapper。Mean Reversion 需要 regime detection，放 Phase 4 更合理。

### v2 Review（2026-04-10，GPT-4）

評分：9.1 / 10

採納的修正（6 個致命點全部修復）：
1. **Intraday Path Assumption** — 新增鐵律 2：保守路徑 Open→Low→High→Close ✅
2. **Gap Stop on Existing Positions** — 新增鐵律 3 出場部分：exit_price = open_price, not stop_price ✅
3. **Portfolio-level Risk Cap** — SizingModel 新增 max_portfolio_risk_pct = 5.0 ✅
4. **Strategy Correlation Limits** — 同類策略合計曝險 ≤ 60% 硬限制 ✅
5. **Capital Insufficient Fallback** — 鐵律 4：縮小倉位而非跳過 ✅
6. **Kill Switch** — 新增第十五節：系統熔斷條件 + KillSwitch dataclass ✅

額外新增：
- Decision 新增 `capital_pool` 欄位，支援分帳戶模式
- 報表新增 Calmar Ratio 和 Tail Risk (VaR 5%) 指標
- Execution 從 4 條鐵律擴充為 6 條鐵律（出場價格模型 + 不可竄改已完成交易）
- ExecutionModel 新增 gap_stop_enabled / path_assumption / min_trade_value 參數

### v3 Review（2026-04-10，GPT-4）

評分：9.3 / 10 — **可以開工，沒有大毛病**

採納的修正（5 個中小問題）：
1. **Decision.size_shares 職責邊界** — size_shares 改為 Execution 填入，Decision 只表達意圖 ✅
2. **Portfolio risk cap 精確算法** — 統一口徑：用當前有效 stop 計算，trailing stop 上移後 risk 跟著降 ✅
3. **Tail Risk 命名** — VaR 5% → CVaR 5% (Expected Shortfall)，術語更精確 ✅
4. **Kill Switch 分類** — 拆為 Research Gate（上線前）+ Runtime Kill Switch（運行中）✅
5. **Long-only 聲明** — 鐵律僅適用 long，short 需重新定義保守路徑 ✅

結論：**設計已過危險區，進入實作。接下來最大風險不是設計錯，而是實作偷偷偏離 spec。**
