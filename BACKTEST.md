# BACKTEST.md — 回測工程師上手指南

本文件是 money_printer 回測系統的技術手冊。  
目標讀者：新加入的回測工程師、量化研究員（需要理解信號格式）、風控師（需要讀懂 KPI）。

---

## 目錄

1. [系統架構概覽](#1-系統架構概覽)
2. [兩條回測路徑](#2-兩條回測路徑)
3. [資料分割（Train / Validation / Test）](#3-資料分割)
4. [成本模型（手續費 + 滑點）](#4-成本模型)
5. [前視偏誤防護機制](#5-前視偏誤防護機制)
6. [現有策略清單](#6-現有策略清單)
7. [新增策略 — 完整步驟](#7-新增策略)
8. [執行回測 — CLI 與 API](#8-執行回測)
9. [KPI 說明與判讀標準](#9-kpi-說明與判讀標準)
10. [常見錯誤與排查](#10-常見錯誤與排查)

---

## 1. 系統架構概覽

```
┌────────────────────────────────────────────────────────────────┐
│                        回測系統全貌                              │
│                                                                  │
│  資料層           信號層                  執行層                 │
│  ─────────        ──────────────────      ─────────────────────  │
│  PostgreSQL  →    HistoricalProvider  →   BacktestEngine (V3)   │
│  (OHLCV)          (防前視偏誤)            (逐日循環)             │
│                        │                                         │
│                   BaseStrategy (ABC)                             │
│                   ├── SMCStrategy                               │
│                   ├── MomentumBreakoutStrategy                  │
│                   └── ExplosionScannerStrategy                  │
│                                                                  │
│                  VectorBT 路徑（單股快速回測）                    │
│                  ─────────────────────────────                   │
│                  _generate_signal_series()                       │
│                  → vbt.Portfolio.from_signals()                  │
│                  → VbtBacktestResult                             │
└────────────────────────────────────────────────────────────────┘
```

### 關鍵檔案位置

| 職責 | 檔案路徑 |
|------|----------|
| VBT 回測主入口 | `backend/app/services/backtest_vbt.py` |
| 策略基類 (ABC) | `backend/app/services/backtest_v3/strategy.py` |
| 通用回測引擎 | `backend/app/services/backtest_v3/engine.py` |
| 資料提供者 | `backend/app/services/backtest_v3/provider.py` |
| 核心資料模型 | `backend/app/services/backtest_v3/models.py` |
| 策略目錄 | `backend/app/services/backtest_v3/strategies/` |
| CLI 執行腳本 | `backend/run_backtest_v3.py` |
| REST API (VBT) | `backend/app/routers/backtest_vbt.py` |

---

## 2. 兩條回測路徑

### 路徑 A：VectorBT 路徑（單股快速回測）

**用途**：前端使用者互動、單一 ticker 快速驗證、API endpoint  
**入口**：`run_vbt_backtest()` in `backtest_vbt.py`  
**API**：`POST /backtest/vbt/run`

執行流程：

```
DB 載入 OHLCV
    ↓
_generate_signal_series()  ← 滑動窗口逐日產生信號
    ↓
entries.shift(1)           ← T+1 執行（防前視）
    ↓
vbt.Portfolio.from_signals() ← VectorBT 向量化計算
    ↓
VbtBacktestResult          ← 結構化 KPI dict
```

**限制**：每次只能跑一個 ticker + 一個策略。多 ticker 需多次呼叫。

---

### 路徑 B：BacktestEngine V3（多股多策略完整回測）

**用途**：策略開發驗證、Walk-forward 分析、風控報告  
**入口**：`python -m backend.run_backtest_v3`  
**引擎**：`BacktestEngine` in `engine.py`

執行流程：

```
DB 載入所有 OHLCV
    ↓
HistoricalProvider（時間窗口鎖定）
    ↓
BacktestEngine.run()
    ├── advance_day()
    ├── 持倉 mark-to-market
    ├── 檢查出場（保守路徑：open→low→high→close）
    ├── generate_signals()（每個策略逐一呼叫）
    ├── Signal → Decision → Order（T+1 pending）
    └── 執行昨日 pending orders
    ↓
calculate_metrics()        ← 完整 KPI 計算
```

**出場保守路徑**：`open → low → high → close`  
這是為了防止回測中假設在最差價格出場（worst-case），避免高估績效。

---

## 3. 資料分割

系統內建三段資料分割，定義在 `provider.py`：

| 分割名稱 | 日期範圍 | 用途 |
|----------|----------|------|
| `train` | 2018-01-01 ～ 2022-12-31 | 策略開發 / 參數優化 |
| `validation` | 2023-01-01 ～ 2024-12-31 | 樣本外驗證（主要評估期） |
| `test` | 2025-01-01 ～ 現在 | 最終驗收（只能看一次！） |

**強制規定**：
- 策略開發期間**只能使用 train**
- 調參後**必須先在 validation 驗證**，績效可接受再看 test
- `test` 是一次性門票，看過就污染了，不能再拿來做決策

```bash
# 正確流程
python -m backend.run_backtest_v3 --split train        # 開發
python -m backend.run_backtest_v3 --split validation   # 驗證
python -m backend.run_backtest_v3 --split test         # 最終驗收（一次性）
```

---

## 4. 成本模型

成本常數定義在 `backtest_vbt.py` 頂部：

```python
# US 市場：雙邊 ~0.11%（滑點 0.05%×2 + SEC fee 約 0.00278%）
_US_FEES = 0.0011
_US_SLIPPAGE = 0.0005

# TW 市場：雙邊 ~0.47%（手續費 0.1425%×0.6×2 + 交易稅 0.3%）
_TW_FEES = 0.0047
_TW_SLIPPAGE = 0.001
```

**路徑 B（BacktestEngine）** 的成本設定在 CLI 參數中：
```python
execution = ExecutionModel(
    fill_type="next_open",   # T+1 開盤成交
    slippage_pct=0.05,       # 0.05% 滑點
    gap_threshold_pct=5.0,   # 跳空超過 5% 取消訂單
)
```

> **重要**：美股成本比台股低，不可混用。執行前確認 `market` 參數正確。

---

## 5. 前視偏誤防護機制

這是回測系統最核心的誠信設計，共有三層防護：

### 防護 1：HistoricalProvider 時間窗口鎖定

```python
# provider.py — get_ohlcv() 只回傳 <= current_date 的數據
def get_ohlcv(self, ticker: str, lookback: int = 252) -> pd.DataFrame:
    # 內部永遠只看 self._current_date 之前的資料
    # 不可能「偷看」未來
```

### 防護 2：T+1 執行 shift

```python
# backtest_vbt.py
# T 日產生信號 → T+1 日才執行
entries = entries_raw.shift(1).fillna(False).astype(bool)
sl_stops_shifted = sl_stops.shift(1)
tp_stops_shifted = tp_stops.shift(1)
```

### 防護 3：出場保守路徑

BacktestEngine 的出場邏輯按 `open → low → high → close` 順序檢查：
- 假設最壞情況先發生（low 先到達），再模擬 high
- 避免在同一天「既觸停損又觸目標」的樂觀假設

> **紅線**：策略的 `generate_signals()` 只能用 `provider.get_ohlcv()` 取數據。直接存取 DB 或傳入「未來資料」是嚴重違規。

---

## 6. 現有策略清單

| 策略名稱（registry key） | 說明 | 類型 |
|--------------------------|------|------|
| `smc_v2` | SMC 智慧資金結構 — OB/FVG/BOS 信號，T+1 執行 | trend |
| `momentum_breakout` | N 日新高突破 + 放量確認 + RSI 過濾，ATR 停損/目標 | breakout |
| `explosion_scanner` | 6 指標爆擊評分（量價+動量+結構），固定停損 8% 目標 25% | breakout |
| `mock_test` | 每 20 日產生 buy signal — 僅用於驗證 registry 機制 | trend |

### 查詢可用策略（API）

```bash
curl http://localhost:8000/backtest/vbt/strategies
```

### 各策略預設參數

**SMC v2**：
- `min_conditions`: 2（最少滿足幾個 SMC 條件才進場）
- `min_rr`: 1.5（最小風報比）
- `signal_expiry_days`: 3（信號有效天數）

**Momentum Breakout**：
- `breakout_days`: 20（N 日新高）
- `volume_ratio_min`: 1.5（放量倍數門檻）
- `atr_stop_mult`: 1.5、`atr_target_mult`: 3.0

**Explosion Scanner**：
- `score_threshold`: 60（爆擊評分門檻，滿分 100）
- `stop_pct`: 0.08（固定停損 8%）
- `target_pct`: 0.25（固定目標 25%）

---

## 7. 新增策略

### 步驟 1：確認策略邏輯（向研究員確認）

新策略上線前必須確認：
- 進場條件（什麼情況產生 buy signal）
- 停損規則（固定% / ATR 倍數 / 結構停損）
- 目標規則（固定% / ATR 倍數 / 結構目標）
- 策略類型：`trend` / `breakout` / `mean_reversion` / `sentiment`

### 步驟 2：建立策略檔案

在 `backend/app/services/backtest_v3/strategies/` 新增 `my_strategy.py`：

```python
from ..models import Signal
from ..provider import DataProvider
from ..strategy import BaseStrategy
import uuid
from datetime import timedelta


class MyStrategy(BaseStrategy):
    
    @property
    def strategy_name(self) -> str:
        return "my_strategy"
    
    @property
    def strategy_type(self) -> str:
        return "breakout"  # trend | breakout | mean_reversion | sentiment
    
    def generate_signals(self, ticker: str, provider: DataProvider) -> list[Signal]:
        """
        只能透過 provider 取數據，不能碰 DB。
        """
        df = provider.get_ohlcv(ticker, lookback=60)
        if df is None or len(df) < 20:
            return []
        
        current_date = provider.current_date()
        
        # ── 你的信號邏輯放這裡 ──────────────────────────────────
        # 範例：20 日新高突破
        recent_high = df["High"].iloc[-21:-1].max()
        today_close = df["Close"].iloc[-1]
        
        if today_close <= recent_high:
            return []
        
        # 計算停損 / 目標
        atr = df["High"].iloc[-14:].max() - df["Low"].iloc[-14:].min()  # 簡化 ATR
        entry = today_close
        stop = entry - 1.5 * atr
        target = entry + 3.0 * atr
        
        if stop >= entry or entry <= 0:
            return []
        
        # ── 建立 Signal ─────────────────────────────────────────
        signal = Signal(
            signal_id=Signal.create_id(),
            ticker=ticker,
            side="long",
            action="buy",
            confidence=0.7,
            strategy_name=self.strategy_name,
            strategy_type=self.strategy_type,
            timeframe="1d",
            timestamp=current_date,
            expiry=current_date + timedelta(days=3),
            position_tier="標準",
            price_hint={
                "entry": round(entry, 2),
                "stop": round(stop, 2),
                "target": round(target, 2),
                "rr_ratio": round((target - entry) / (entry - stop), 2),
            },
        )
        
        # 驗證 Signal 完整性
        errors = signal.validate()
        if errors:
            return []
        
        return [signal]
```

### 步驟 3：註冊到 STRATEGY_REGISTRY

編輯 `backend/app/services/backtest_vbt.py`：

```python
def _build_registry():
    from .backtest_v3.strategies.smc_strategy import SMCStrategy
    from .backtest_v3.strategies.momentum_breakout import MomentumBreakoutStrategy
    from .backtest_v3.strategies.explosion_scanner import ExplosionScannerStrategy
    from .backtest_v3.strategies.mock_strategy import MockStrategy
    from .backtest_v3.strategies.my_strategy import MyStrategy  # ← 新增

    return {
        "smc_v2": SMCStrategy,
        "momentum_breakout": MomentumBreakoutStrategy,
        "explosion_scanner": ExplosionScannerStrategy,
        "mock_test": MockStrategy,
        "my_strategy": MyStrategy,  # ← 新增
    }


STRATEGY_METADATA = {
    # ... 現有策略 ...
    "my_strategy": {  # ← 新增
        "label": "我的新策略",
        "description": "一句話說明策略邏輯",
        "default_params": {
            "breakout_days": 20,
        },
    },
}
```

### 步驟 4：也要在 run_backtest_v3.py 加入（如果要走路徑 B）

```python
# backend/run_backtest_v3.py
from backend.app.services.backtest_v3.strategies.my_strategy import MyStrategy

STRATEGY_MAP = {
    # ... 現有策略 ...
    "my_strategy": lambda: MyStrategy(breakout_days=args.breakout_days),  # ← 新增
}
```

### 步驟 5：驗證 Signal 格式

在加入完整回測之前，先用 `mock_test` 確認 registry 機制正常：

```bash
curl http://localhost:8000/backtest/vbt/strategies
# 確認 my_strategy 出現在清單中

curl -X POST http://localhost:8000/backtest/vbt/run \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "start": "2023-01-01",
    "end": "2023-12-31",
    "strategy": "my_strategy"
  }'
```

---

## 8. 執行回測

### 方式 A：REST API（單股）

```bash
# 列出可用策略
GET /backtest/vbt/strategies

# 執行回測
POST /backtest/vbt/run
{
    "ticker": "NVDA",
    "start": "2023-01-01",
    "end": "2024-12-31",
    "market": "US",
    "initial_capital": 100000,
    "strategy": "momentum_breakout",
    "strategy_params": {
        "breakout_days": 20,
        "volume_ratio_min": 1.5
    }
}
```

台股範例：
```bash
POST /backtest/vbt/run
{
    "ticker": "2330",
    "start": "2023-01-01",
    "end": "2024-12-31",
    "market": "TW",
    "strategy": "smc_v2"
}
```

### 方式 B：CLI（多股多策略）

```bash
# 需要在 conda env money_printer 中執行
conda activate money_printer

# 標準驗證期回測（SMC v2）
python -m backend.run_backtest_v3 --split validation

# 多策略組合
python -m backend.run_backtest_v3 \
    --split validation \
    --strategies smc_v2,momentum_breakout \
    --min-conditions 3 \
    --min-rr 2.0 \
    --max-positions 8 \
    --capital 100000

# 自定義日期範圍
python -m backend.run_backtest_v3 \
    --start 2023-06-01 \
    --end 2024-06-30 \
    --strategies momentum_breakout

# JSON 輸出（供 pipeline 使用）
python -m backend.run_backtest_v3 --split validation --json > result.json
```

### 方式 C：前端 UI

1. 前端路徑：`/backtest`
2. 選擇 ticker、日期範圍、策略
3. 送出後從 `/backtest/vbt/run` 取得結果
4. 顯示 equity curve + 交易明細

---

## 9. KPI 說明與判讀標準

### VBT 路徑輸出欄位（`VbtBacktestResult`）

| KPI 欄位 | 說明 | 參考門檻 |
|----------|------|---------|
| `total_return_pct` | 總報酬率（%） | 依策略類型而定 |
| `sharpe_ratio` | 夏普比率（年化）| ≥ 1.0 才算合格，≥ 1.5 優秀 |
| `max_drawdown_pct` | 最大回撤（%） | ≤ 20% 可接受，≤ 10% 優秀 |
| `win_rate` | 勝率（0.0 ~ 1.0） | 趨勢策略 ≥ 40%，均值回歸 ≥ 55% |
| `total_trades` | 總交易筆數 | ≥ 30 筆才有統計意義 |
| `avg_holding_days` | 平均持倉天數 | 視策略設計 |
| `expectancy_pct` | 期望值（每筆平均報酬%） | > 0% 即正期望值 |
| `profit_factor` | 毛利 / 毛損 | ≥ 1.5 可接受，≥ 2.0 優秀 |
| `signals_generated` | 回測期間產生的 buy signal 數量 | 用來判斷策略是否過度謹慎 |

### BacktestEngine V3 額外指標

| KPI | 說明 | 門檻 |
|-----|------|------|
| `cagr_pct` | 年化複合成長率 | > 大盤 CAGR（SPY ≈ 10%/年）|
| `sortino_ratio` | Sortino 比率（只考慮下行波動）| ≥ 1.0 |
| `calmar_ratio` | 年化報酬 / 最大回撤 | ≥ 0.5 |
| `max_consecutive_losses` | 最大連續虧損次數 | ≤ 5 次 |
| `tail_risk_cvar_5pct` | 尾部風險 CVaR 5% | 越小越好 |
| `avg_exposure_pct` | 平均資金使用率 | 視策略，太低代表訊號太少 |

### 策略分層報告（by_tier）

引擎追蹤三種倉位等級的各別績效：

| 等級 | 佔資金 | 觸發條件 |
|------|--------|---------|
| 核心 | 15-20% | 高 confidence + 多重確認 |
| 標準 | 8-12% | 標準 confidence |
| 探索 | 3-5% | 較低 confidence |

### 閱讀回測報告的優先順序

1. **看 total_trades 先** — 若少於 30 筆，其他 KPI 無統計意義
2. **看 max_drawdown** — 超過 25% 風控通常不會批准
3. **看 sharpe_ratio** — 低於 1.0 需要特別理由
4. **看 profit_factor** — < 1.0 代表整體虧損
5. **看 expectancy_pct** — 確認正期望值
6. **看 equity curve** — 是否有明顯 regime 斷崖（某段時間突然大幅下行）

---

## 10. 常見錯誤與排查

### 錯誤 1：`Insufficient data for {ticker}: only N bars`

**原因**：DB 中該 ticker 的歷史資料不足 60 根 bar。  
**排查**：確認 ticker 已完成資料下載，且回測起始日離現在夠遠。  
**解法**：縮短回測起始日，或先執行 fetcher 補充資料。

---

### 錯誤 2：`Unknown strategy: '{name}'`

**原因**：`strategy_name` 不在 `STRATEGY_REGISTRY`。  
**排查**：`GET /backtest/vbt/strategies` 查看可用清單。  
**解法**：確認 `backtest_vbt.py` 的 `_build_registry()` 有加入你的策略。

---

### 錯誤 3：信號數量為 0（`signals_generated: 0`）

**原因**：策略條件太嚴格、或回測期間根本沒有符合條件的 bar。  
**排查**：用較寬鬆的參數再跑一次，確認是策略設計問題而非 bug。  
**解法**：
- 降低 `min_conditions`（SMC）
- 降低 `score_threshold`（爆擊掃描器）
- 確認 `signal.validate()` 有正確通過

---

### 錯誤 4：`buy signal must have price_hint with entry + stop`

**原因**：策略的 `generate_signals()` 回傳的 Signal 缺少 `price_hint`，或 `entry`/`stop` 為 None。  
**排查**：在策略程式碼中加 debug log，確認 `price_hint` 正確填充。  
**解法**：買入 signal 必須同時帶 `entry` 和 `stop`，缺一不可。

---

### 錯誤 5：VectorBT 夏普比率 = 0 或 NaN

**原因**：通常是因為所有交易都在同一天進出，標準差為 0。  
**排查**：確認 `avg_holding_days` > 0，且交易分布在多天。  
**解法**：確認 T+1 shift 有正確執行（entries.shift(1)）。

---

### 錯誤 6：回測結果在 train / validation 差距太大

**原因**：過度擬合（overfitting）。在 train 上優化過多參數。  
**排查**：比較 train 和 validation 的 sharpe / win_rate / profit_factor。  
**解法**：回到更簡單的策略邏輯；不要讓策略參數數量超過 3-4 個。

---

## 附錄：資料欄位規格

### Signal 必填欄位

```python
Signal(
    signal_id=str,          # uuid4
    ticker=str,             # "NVDA" or "2330"
    side="long",            # 目前只支援多方
    action="buy",           # "buy" | "sell" | "hold" | "watch"
    confidence=float,       # 0.0 ~ 1.0
    strategy_name=str,      # 必須與 strategy_name property 一致
    strategy_type=str,      # "trend"|"breakout"|"mean_reversion"|"sentiment"
    timeframe="1d",         # 目前系統只支援日線
    timestamp=date,         # 信號產生日（current_date）
    expiry=date,            # 信號過期日（通常 +3 days）
    price_hint={
        "entry": float,     # 進場價（買入 signal 必填）
        "stop": float,      # 停損價（買入 signal 必填）
        "target": float,    # 目標價（選填，有才有 tp_stop）
        "rr_ratio": float,  # 風報比（選填）
    },
)
```

### VbtBacktestResult JSON 結構

```json
{
    "ticker": "NVDA",
    "market": "US",
    "strategy": "momentum_breakout",
    "period": {"start": "2023-01-01", "end": "2024-12-31"},
    "total_return_pct": 45.23,
    "sharpe_ratio": 1.45,
    "max_drawdown_pct": 12.34,
    "win_rate": 0.48,
    "total_trades": 23,
    "avg_holding_days": 18.5,
    "expectancy_pct": 3.21,
    "profit_factor": 2.1,
    "equity_curve": [["2023-01-03", 100000], ["2023-01-04", 100120], ...],
    "trades": [
        {"entry": "2023-02-15", "exit": "2023-03-01", "return_pct": 8.3, "pnl": 830.0, "holding_days": 14}
    ],
    "initial_capital": 100000,
    "final_equity": 145230,
    "signals_generated": 31,
    "elapsed_seconds": 2.1
}
```

---

*最後更新：2026-04-14 | 由回測工程師整理*
