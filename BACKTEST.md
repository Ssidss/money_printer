# BACKTEST.md — 回測工程師上手指南

本文件是 money_printer 回測系統的技術手冊。  
自 KINA-329 後，系統只保留 **VectorBT 引擎**，已移除 V2/V3 舊引擎。  
目標讀者：新加入的回測工程師、量化研究員（需要理解信號格式）、風控師（需要讀懂 KPI）。

---

## 目錄

1. [系統架構概覽](#1-系統架構概覽)
2. [VectorBT 快速回測路徑](#2-vectorbt-快速回測路徑)
3. [成本模型（手續費 + 滑點）](#3-成本模型)
4. [前視偏誤防護機制](#4-前視偏誤防護機制)
5. [現有策略清單](#5-現有策略清單)
6. [新增策略 — 完整步驟](#6-新增策略)
7. [執行回測 — REST API](#7-執行回測)
8. [KPI 說明與判讀標準](#8-kpi-說明與判讀標準)
9. [常見錯誤與排查](#9-常見錯誤與排查)

---

## 1. 系統架構概覽

```
┌────────────────────────────────────────────────────────────────┐
│                  VectorBT 快速回測系統                           │
│                                                                  │
│  資料層           信號層                  執行層                 │
│  ─────────        ──────────────────      ─────────────────────  │
│  PostgreSQL  →    HistoricalProvider  →   VectorBT Framework    │
│  (OHLCV)          (防前視偏誤)            (向量化計算)            │
│                        │                                         │
│                   BaseStrategy (ABC)                             │
│                   ├── SMCStrategy                               │
│                   ├── MomentumBreakoutStrategy                  │
│                   └── ExplosionScannerStrategy                  │
│                                                                  │
│                  REST API 路徑（單股快速回測）                    │
│                  ─────────────────────────────                   │
│                  _generate_signal_series()                       │
│                  → entries / sl_stops / tp_stops                 │
│                  → vbt.Portfolio.from_signals()                  │
│                  → VbtBacktestResult                             │
└────────────────────────────────────────────────────────────────┘
```

### 關鍵檔案位置

| 職責 | 檔案路徑 |
|------|----------|
| VBT 回測主入口 | `backend/app/services/backtest_vbt.py` |
| 策略目錄 | `backend/app/services/strategies/` |
| REST API (VBT) | `backend/app/routers/backtest_vbt.py` |
| 資料模型 | `backend/app/models/backtest.py` |

**已移除**（KINA-329）：
- ❌ `backend/app/services/backtester_v2.py`（V2 引擎）
- ❌ `backend/app/services/backtest_v3/`（V3 引擎）
- ❌ `backend/app/routers/backtest_v2.py`、`backtest_v3.py`、`strategies.py`、`signals.py`

---

## 2. VectorBT 快速回測路徑

**用途**：前端使用者互動、單一 ticker 快速驗證、REST API 調用  
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

## 3. 成本模型

成本常數定義在 `backtest_vbt.py` 頂部：

```python
# US 市場：雙邊 ~0.11%（滑點 0.05%×2 + SEC fee 約 0.00278%）
_US_FEES = 0.0011
_US_SLIPPAGE = 0.0005

# TW 市場：雙邊 ~0.47%（手續費 0.1425%×0.6×2 + 交易稅 0.3%）
_TW_FEES = 0.0047
_TW_SLIPPAGE = 0.001
```

> **重要**：美股成本比台股低，不可混用。執行前確認 `market` 參數正確。

> **⚠️ 已知限制**：`backtest_vbt.py` 中 `slippage` 固定使用 `_US_SLIPPAGE = 0.0005`，不隨 `market` 切換。台股回測的費用（`_TW_FEES`）已正確套用，但滑點實際為 0.05%（非 0.1%）。此為已知 bug，待修正前請注意此差異。

---

## 4. 前視偏誤防護機制

這是回測系統最核心的誠信設計，共有兩層防護：

### 防護 1：HistoricalProvider 時間窗口鎖定

```python
# backtest_vbt.py — HistoricalProvider.get_ohlcv() 只回傳 <= current_date 的數據
def get_ohlcv(self, ticker: str) -> Optional[pd.DataFrame]:
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

> **紅線**：策略的 `generate_signals()` 只能用 `provider.get_ohlcv()` 取數據。直接存取 DB 或傳入「未來資料」是嚴重違規。

---

## 5. 現有策略清單

| 策略名稱（registry key） | 說明 | 類型 |
|--------------------------|------|------|
| `smc_v2` | SMC 智慧資金結構 — OB/FVG/BOS 信號，T+1 執行 | trend |
| `momentum_breakout` | N 日新高突破 + 放量確認 + RSI 過濾，ATR 停損/目標 | breakout |
| `explosion_scanner` | 6 指標爆擊評分（量價+動量+結構），固定停損 8% 目標 25% | breakout |
| `mock_test` | 每 20 日產生 buy signal — 僅用於驗證 registry 機制 | trend |

**⚠️ 已知限制**：上述策略當前無法導入（依賴已刪除的 backtest_v3 基類）。需要在後續任務（如 KINA-330）中重構，以支援 VBT 架構或新設計。

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

## 6. 新增策略

### 步驟 1：確認策略邏輯（向研究員確認）

新策略上線前必須確認：
- 進場條件（什麼情況產生 buy signal）
- 停損規則（固定% / ATR 倍數 / 結構停損）
- 目標規則（固定% / ATR 倍數 / 結構目標）
- 策略類型：`trend` / `breakout` / `mean_reversion` / `sentiment`

### 步驟 2：建立策略檔案

在 `backend/app/services/strategies/` 新增 `my_strategy.py`：

> **注意**：策略檔案放在 `backend/app/services/strategies/`。這是唯一的策略目錄。

```python
import uuid
from datetime import timedelta
from typing import Optional
import pandas as pd


class Signal:
    """簡化 Signal 模型（後續可擴展）"""
    def __init__(self, **kwargs):
        self.action = kwargs.get('action')
        self.price_hint = kwargs.get('price_hint')


class DataProvider:
    """簡化 DataProvider 模型"""
    def get_ohlcv(self, ticker: str) -> Optional[pd.DataFrame]:
        pass
    
    def current_date(self) -> date:
        pass


class BaseStrategy:
    """基策略類（簡化）"""
    
    @property
    def strategy_name(self) -> str:
        raise NotImplementedError
    
    @property
    def strategy_type(self) -> str:
        raise NotImplementedError
    
    def generate_signals(self, ticker: str, provider: DataProvider) -> list[Signal]:
        """
        只能透過 provider 取數據，不能碰 DB。
        """
        raise NotImplementedError


class MyStrategy(BaseStrategy):
    
    @property
    def strategy_name(self) -> str:
        return "my_strategy"
    
    @property
    def strategy_type(self) -> str:
        return "breakout"  # trend | breakout | mean_reversion | sentiment
    
    def generate_signals(self, ticker: str, provider: DataProvider) -> list[Signal]:
        df = provider.get_ohlcv(ticker)
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
            action="buy",
            price_hint={
                "entry": round(entry, 2),
                "stop": round(stop, 2),
                "target": round(target, 2),
                "rr_ratio": round((target - entry) / (entry - stop), 2) if (entry - stop) != 0 else 0,
            },
        )
        
        return [signal]
```

### 步驟 3：註冊到 STRATEGY_REGISTRY

編輯 `backend/app/services/backtest_vbt.py`：

```python
def _build_registry():
    from .strategies.smc_strategy import SMCStrategy
    from .strategies.momentum_breakout import MomentumBreakoutStrategy
    from .strategies.explosion_scanner import ExplosionScannerStrategy
    from .strategies.mock_strategy import MockStrategy
    from .strategies.my_strategy import MyStrategy  # ← 新增

    registry = {}
    
    # ... 現有的 try-except 邏輯 ...
    
    # 新增 MyStrategy
    try:
        registry["my_strategy"] = MyStrategy
    except (ImportError, ModuleNotFoundError) as e:
        logger.warning(f"Could not import MyStrategy: {e}")
    
    return registry


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

### 步驟 4：驗證 Signal 格式

在加入完整回測之前，先用 API 確認 registry 機制正常：

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

## 7. 執行回測

### REST API（單股）

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

### 前端 UI

1. 前端路徑：`/backtest`
2. 選擇 ticker、日期範圍、策略
3. 送出後從 `/backtest/vbt/run` 取得結果
4. 顯示 equity curve + 交易明細

---

## 8. KPI 說明與判讀標準

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

### 閱讀回測報告的優先順序

1. **看 total_trades 先** — 若少於 30 筆，其他 KPI 無統計意義
2. **看 max_drawdown** — 超過 25% 風控通常不會批准
3. **看 sharpe_ratio** — 低於 1.0 需要特別理由
4. **看 profit_factor** — < 1.0 代表整體虧損
5. **看 expectancy_pct** — 確認正期望值
6. **看 equity curve** — 是否有明顯 regime 斷崖（某段時間突然大幅下行）

---

## 9. 常見錯誤與排查

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
- 降低 `min_conditions`（如適用）
- 確認 `Signal` 物件正確建立

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

## 附錄：Signal 資料結構

```python
Signal(
    action="buy",           # "buy" | "sell" | "hold" | "watch"
    price_hint={
        "entry": float,     # 進場價（買入 signal 必填）
        "stop": float,      # 停損價（買入 signal 必填）
        "target": float,    # 目標價（選填，有才有 tp_stop）
        "rr_ratio": float,  # 風報比（選填）
    },
)
```

---

## 版本史

- **2026-04-15**：KINA-329 清理技術債 — 移除 V2/V3 引擎，只保留 VBT
- **2026-04-14**：初始文件建立

---

*最後更新：2026-04-15 | 由後端工程師整理*
