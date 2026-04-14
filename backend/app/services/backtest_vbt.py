"""
VectorBT 整合 — 策略回測 Service

架構：
  1. STRATEGY_REGISTRY — 所有可用策略的 class map
  2. 從 DB 載入 ticker 的 OHLCV 歷史（含 252 bar lookback buffer）
  3. 滑動窗口呼叫 strategy.generate_signals()（防前視偏誤）
  4. 聚合 entries / sl_stop / tp_stop arrays（T+1 執行）
  5. vbt.Portfolio.from_signals() 向量化計算績效
  6. 回傳結構化 BacktestResult dict

前視偏誤防護：
  - 信號在 T 日收盤後產生，T+1 開盤才執行（entries.shift(1)）
  - HistoricalProvider.get_ohlcv() 僅回傳 <= current_date 的數據
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Type

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Cost constants ────────────────────────────────────────────────────────────

# US market: round-trip ~0.11% (0.05% slippage×2 + SEC fee ~0.00278%)
_US_FEES = 0.0011
_US_SLIPPAGE = 0.0005

# TW market: round-trip ~0.47% (commission 0.1425%×0.6×2 + tax 0.3%)
_TW_FEES = 0.0047
_TW_SLIPPAGE = 0.001


# ── Strategy Registry ─────────────────────────────────────────────────────────

def _build_registry():
    from .strategies.smc_strategy import SMCStrategy
    from .strategies.momentum_breakout import MomentumBreakoutStrategy
    from .strategies.explosion_scanner import ExplosionScannerStrategy
    from .strategies.mock_strategy import MockStrategy

    return {
        "smc_v2": SMCStrategy,
        "momentum_breakout": MomentumBreakoutStrategy,
        "explosion_scanner": ExplosionScannerStrategy,
        "mock_test": MockStrategy,
    }


# Registry metadata — 每個策略的 label + 預設 params
STRATEGY_METADATA = {
    "smc_v2": {
        "label": "SMC v2（智慧資金結構）",
        "description": "Smart Money Concept — 基於 OB/FVG/BOS 結構，T+1 執行",
        "default_params": {
            "min_conditions": 2,
            "min_rr": 1.5,
            "signal_expiry_days": 3,
        },
    },
    "momentum_breakout": {
        "label": "動量突破",
        "description": "N 日新高突破 + 放量確認 + RSI 過濾，ATR 停損/目標",
        "default_params": {
            "breakout_days": 20,
            "volume_ratio_min": 1.5,
            "atr_stop_mult": 1.5,
            "atr_target_mult": 3.0,
        },
    },
    "explosion_scanner": {
        "label": "爆擊掃描器",
        "description": "6 指標爆擊評分（量價 + 動量 + 結構），固定停損 8%，目標 25%",
        "default_params": {
            "score_threshold": 60,
            "stop_pct": 0.08,
            "target_pct": 0.25,
        },
    },
    "mock_test": {
        "label": "Mock 測試策略",
        "description": "驗證 registry 插件化 — 每 20 日產生一個 buy signal，固定停損 5%/目標 10%",
        "default_params": {
            "signal_interval": 20,
            "stop_pct": 0.05,
            "target_pct": 0.10,
        },
    },
}


def get_strategy_registry() -> dict[str, Type]:
    """回傳 STRATEGY_REGISTRY（lazy import 版本，避免啟動時間問題）"""
    return _build_registry()


def list_strategies() -> list[dict]:
    """回傳所有策略的清單（含 name / label / default_params）"""
    registry = get_strategy_registry()
    result = []
    for name, cls in registry.items():
        meta = STRATEGY_METADATA.get(name, {})
        result.append({
            "name": name,
            "label": meta.get("label", name),
            "description": meta.get("description", ""),
            "default_params": meta.get("default_params", {}),
        })
    return result


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class VbtBacktestResult:
    ticker: str
    market: str
    strategy: str
    start_date: str
    end_date: str
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    avg_holding_days: float
    expectancy_pct: float        # 期望值（每筆平均報酬%）
    profit_factor: float         # 毛利 / 毛損
    equity_curve: list           # [[date_str, equity_value], ...]
    trades: list                 # [{entry, exit, return_pct, holding_days}, ...]
    initial_capital: float
    final_equity: float
    signals_generated: int       # 回測期間產生的 buy signals 數量
    elapsed_seconds: float


def _result_to_dict(r: VbtBacktestResult) -> dict:
    return {
        "ticker": r.ticker,
        "market": r.market,
        "strategy": r.strategy,
        "period": {"start": r.start_date, "end": r.end_date},
        "total_return_pct": r.total_return_pct,
        "sharpe_ratio": r.sharpe_ratio,
        "max_drawdown_pct": r.max_drawdown_pct,
        "win_rate": r.win_rate,
        "total_trades": r.total_trades,
        "avg_holding_days": r.avg_holding_days,
        "expectancy_pct": r.expectancy_pct,
        "profit_factor": r.profit_factor,
        "equity_curve": r.equity_curve,
        "trades": r.trades,
        "initial_capital": r.initial_capital,
        "final_equity": r.final_equity,
        "signals_generated": r.signals_generated,
        "elapsed_seconds": r.elapsed_seconds,
    }


# ── Signal generation loop ────────────────────────────────────────────────────

def _generate_signal_series(
    ticker: str,
    price_df: pd.DataFrame,
    start_date: date,
    end_date: date,
    market: str,
    strategy_name: str,
    strategy_params: dict,
) -> tuple[pd.Series, pd.Series, pd.Series, int]:
    """
    滑動窗口逐日產生策略信號，回傳對齊 price_df 日期索引的 boolean/float Series。

    Returns:
        entries (bool Series):  當日有 buy signal
        sl_stops (float Series): 停損幅度（相對 entry price 的比例，NaN 表示無信號）
        tp_stops (float Series): 停利幅度（相對 entry price 的比例，NaN 表示無信號）
        signals_count: 產生 buy signal 的天數
    """
    from .backtest_v3.provider import HistoricalProvider

    registry = get_strategy_registry()
    if strategy_name not in registry:
        raise ValueError(f"Unknown strategy: '{strategy_name}'. Available: {list(registry.keys())}")

    strategy_cls = registry[strategy_name]

    # 合併 metadata default_params + 使用者 override
    meta_defaults = STRATEGY_METADATA.get(strategy_name, {}).get("default_params", {})
    merged_params = {**meta_defaults, **strategy_params}

    # 實例化策略（只傳 strategy 本身認識的 kwargs）
    try:
        strategy = strategy_cls(**merged_params)
    except TypeError:
        # 如果傳入參數不被接受，用預設實例化
        logger.warning(
            f"[backtest_vbt] Strategy '{strategy_name}' rejected params {merged_params}, "
            "falling back to default init"
        )
        strategy = strategy_cls()

    # price_df 索引必須是 DatetimeIndex
    price_df = price_df.copy()
    price_df.index = pd.to_datetime(price_df.index)

    provider = HistoricalProvider(
        price_data={ticker: price_df},
        stocks_info=[{"ticker": ticker, "market": market, "id": 0}],
        start_date=start_date,
        end_date=end_date,
        min_bars=60,
        min_volume=0,
    )

    # 建立結果索引（回測期間的所有交易日）
    period_mask = (price_df.index >= pd.Timestamp(start_date)) & (price_df.index <= pd.Timestamp(end_date))
    period_dates = price_df.index[period_mask]

    entries_raw = pd.Series(False, index=period_dates)
    sl_stops = pd.Series(np.nan, index=period_dates, dtype=float)
    tp_stops = pd.Series(np.nan, index=period_dates, dtype=float)

    signals_count = 0

    while True:
        current = provider.advance_day()
        if current is None:
            break

        ts = pd.Timestamp(current)
        if ts not in period_dates:
            continue

        try:
            signals = strategy.generate_signals(ticker, provider)
        except Exception as e:
            logger.debug(f"Signal generation failed for {ticker} on {current}: {e}")
            continue

        for sig in signals:
            if sig.action != "buy":
                continue
            if sig.price_hint is None:
                continue

            entry = sig.price_hint.get("entry")
            stop = sig.price_hint.get("stop")
            target = sig.price_hint.get("target")

            if entry is None or stop is None or entry <= 0:
                continue

            sl_frac = (entry - stop) / entry
            if sl_frac <= 0:
                continue

            entries_raw[ts] = True
            sl_stops[ts] = sl_frac

            if target is not None and target > entry:
                tp_frac = (target - entry) / entry
                tp_stops[ts] = tp_frac

            signals_count += 1
            break  # 每天最多一個信號

    return entries_raw, sl_stops, tp_stops, signals_count


# ── Main backtest function ────────────────────────────────────────────────────

async def run_vbt_backtest(
    ticker: str,
    start_date: date,
    end_date: date,
    market: str = "US",
    initial_capital: float = 100_000,
    strategy_name: str = "smc_v2",
    strategy_params: Optional[dict] = None,
) -> dict:
    """
    執行策略 VectorBT 回測（通用入口，從 STRATEGY_REGISTRY lookup 策略）。

    Args:
        ticker:          股票代碼（如 "2330" 或 "NVDA"）
        start_date:      回測開始日
        end_date:        回測結束日
        market:          "TW" 或 "US"
        initial_capital: 初始資金
        strategy_name:   策略名稱（必須在 STRATEGY_REGISTRY 中）
        strategy_params: 可選覆蓋策略預設參數的 dict

    Returns:
        dict 格式的 BacktestResult（可直接序列化為 JSON）
    """
    if strategy_params is None:
        strategy_params = {}

    t0 = time.time()

    # ── Step 1: 從 DB 載入 OHLCV ────────────────────────────────────────
    from ..database import AsyncSessionLocal
    from ..models.stock import Stock, PriceHistory
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        stock_row = (await db.execute(
            select(Stock).where(Stock.ticker == ticker)
        )).scalar_one_or_none()

        if stock_row is None:
            return {"error": f"Ticker '{ticker}' not found in database"}

        buffer_start = start_date - timedelta(days=400)  # 252 交易日 + 安全邊際

        price_rows = (await db.execute(
            select(PriceHistory)
            .where(
                PriceHistory.stock_id == stock_row.id,
                PriceHistory.date >= buffer_start,
                PriceHistory.date <= end_date,
            )
            .order_by(PriceHistory.date.asc())
        )).scalars().all()

    if len(price_rows) < 60:
        return {"error": f"Insufficient data for {ticker}: only {len(price_rows)} bars"}

    price_df = pd.DataFrame([{
        "date": r.date,
        "Open": float(r.open or 0),
        "High": float(r.high or 0),
        "Low": float(r.low or 0),
        "Close": float(r.close or 0),
        "Volume": int(r.volume or 0),
    } for r in price_rows]).set_index("date").sort_index()

    price_df.index = pd.to_datetime(price_df.index)

    # ── Step 2: 驗證策略存在 ─────────────────────────────────────────────
    registry = get_strategy_registry()
    if strategy_name not in registry:
        return {"error": f"Unknown strategy: '{strategy_name}'. Available: {list(registry.keys())}"}

    # ── Step 3: 產生信號 ─────────────────────────────────────────────────
    logger.info(
        f"[backtest_vbt] Generating signals for {ticker} "
        f"{start_date} ~ {end_date} strategy={strategy_name} ({len(price_df)} bars total)"
    )

    try:
        entries_raw, sl_stops, tp_stops, signals_count = _generate_signal_series(
            ticker=ticker,
            price_df=price_df,
            start_date=start_date,
            end_date=end_date,
            market=market,
            strategy_name=strategy_name,
            strategy_params=strategy_params,
        )
    except ValueError as e:
        return {"error": str(e)}

    # ── Step 4: 準備 VectorBT 輸入 ──────────────────────────────────────
    period_mask = (price_df.index >= pd.Timestamp(start_date)) & \
                  (price_df.index <= pd.Timestamp(end_date))
    close = price_df.loc[period_mask, "Close"]

    # T+1 執行：信號在 T 日產生，T+1 日才能買入
    entries = entries_raw.shift(1).fillna(False).astype(bool)
    sl_stops_shifted = sl_stops.shift(1)
    tp_stops_shifted = tp_stops.shift(1)

    entries = entries.reindex(close.index, fill_value=False)
    sl_stops_shifted = sl_stops_shifted.reindex(close.index, fill_value=np.nan)
    tp_stops_shifted = tp_stops_shifted.reindex(close.index, fill_value=np.nan)

    # ── Step 5: VectorBT Portfolio ──────────────────────────────────────
    import vectorbt as vbt

    fees = _TW_FEES if market == "TW" else _US_FEES
    slippage = _US_SLIPPAGE

    sl_arr = sl_stops_shifted.values.astype(float)
    tp_arr = tp_stops_shifted.values.astype(float)

    sl_mean = float(np.nanmean(sl_arr)) if not np.all(np.isnan(sl_arr)) else 0.05
    tp_mean = float(np.nanmean(tp_arr)) if not np.all(np.isnan(tp_arr)) else 0.10

    sl_arr = np.where(np.isnan(sl_arr), sl_mean, sl_arr)
    tp_arr = np.where(np.isnan(tp_arr), tp_mean, tp_arr)

    try:
        pf = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=pd.Series(False, index=close.index),
            sl_stop=sl_arr,
            tp_stop=tp_arr,
            fees=fees,
            slippage=slippage,
            init_cash=initial_capital,
            freq="D",
            upon_opposite_entry="ignore",
        )
    except Exception as e:
        logger.error(f"VectorBT portfolio creation failed for {ticker}: {e}")
        return {"error": f"VectorBT error: {str(e)}"}

    # ── Step 6: 提取績效指標 ─────────────────────────────────────────────
    try:
        stats = pf.stats()
        total_return = float(stats.get("Total Return [%]", 0.0))
        sharpe = float(stats.get("Sharpe Ratio", 0.0))
        max_dd = float(stats.get("Max Drawdown [%]", 0.0))
        win_rate_raw = stats.get("Win Rate [%]", None)
        win_rate = float(win_rate_raw) / 100.0 if win_rate_raw is not None and not np.isnan(float(win_rate_raw)) else 0.0
        total_trades = int(stats.get("Total Closed Trades", 0))
    except Exception as e:
        logger.warning(f"Stats extraction error for {ticker}: {e}")
        total_return = sharpe = max_dd = win_rate = 0.0
        total_trades = 0

    # Equity curve
    try:
        equity_series = pf.value()
        equity_curve = [
            [str(dt.date()) if hasattr(dt, 'date') else str(dt), round(float(v), 2)]
            for dt, v in zip(equity_series.index, equity_series.values)
            if not np.isnan(v)
        ]
    except Exception:
        equity_curve = []

    # Trade records
    trades_list = []
    avg_holding_days = 0.0
    expectancy_pct = 0.0
    profit_factor = 0.0

    try:
        trade_records = pf.trades.records_readable
        if not trade_records.empty:
            for _, row in trade_records.iterrows():
                entry_dt = row.get("Entry Index", row.get("Entry Timestamp", None))
                exit_dt = row.get("Exit Index", row.get("Exit Timestamp", None))

                entry_str = str(entry_dt.date()) if hasattr(entry_dt, 'date') else str(entry_dt)
                exit_str = str(exit_dt.date()) if hasattr(exit_dt, 'date') else str(exit_dt)

                ret_pct = float(row.get("Return [%]", 0.0))
                pnl = float(row.get("PnL", 0.0))

                try:
                    holding = (pd.Timestamp(exit_dt) - pd.Timestamp(entry_dt)).days
                except Exception:
                    holding = 0

                trades_list.append({
                    "entry": entry_str,
                    "exit": exit_str,
                    "return_pct": round(ret_pct, 2),
                    "pnl": round(pnl, 2),
                    "holding_days": holding,
                })

            holding_days_arr = [t["holding_days"] for t in trades_list]
            avg_holding_days = float(np.mean(holding_days_arr)) if holding_days_arr else 0.0

            returns_arr = [t["return_pct"] for t in trades_list]
            expectancy_pct = float(np.mean(returns_arr)) if returns_arr else 0.0

            wins = [r for r in returns_arr if r > 0]
            losses = [r for r in returns_arr if r < 0]
            gross_profit = sum(wins)
            gross_loss = abs(sum(losses))
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

    except Exception as e:
        logger.warning(f"Trade records extraction error for {ticker}: {e}")

    final_equity = equity_curve[-1][1] if equity_curve else initial_capital
    elapsed = round(time.time() - t0, 2)

    logger.info(
        f"[backtest_vbt] {ticker}/{strategy_name} done in {elapsed}s: "
        f"return={total_return:.1f}%, sharpe={sharpe:.2f}, "
        f"max_dd={max_dd:.1f}%, trades={total_trades}, signals={signals_count}"
    )

    result = VbtBacktestResult(
        ticker=ticker,
        market=market,
        strategy=strategy_name,
        start_date=str(start_date),
        end_date=str(end_date),
        total_return_pct=round(total_return, 2),
        sharpe_ratio=round(sharpe, 3) if not np.isnan(sharpe) else 0.0,
        max_drawdown_pct=round(max_dd, 2),
        win_rate=round(win_rate, 4),
        total_trades=total_trades,
        avg_holding_days=round(avg_holding_days, 1),
        expectancy_pct=round(expectancy_pct, 2),
        profit_factor=round(profit_factor, 3) if profit_factor != float("inf") else 9999.0,
        equity_curve=equity_curve,
        trades=trades_list,
        initial_capital=initial_capital,
        final_equity=final_equity,
        signals_generated=signals_count,
        elapsed_seconds=elapsed,
    )

    return _result_to_dict(result)


# ── Backward-compatibility shim ───────────────────────────────────────────────

async def run_smc_backtest(
    ticker: str,
    start_date: date,
    end_date: date,
    market: str = "US",
    initial_capital: float = 100_000,
    min_conditions: int = 2,
    min_rr: float = 1.5,
) -> dict:
    """向後相容 shim — 包裝為 smc_v2 策略呼叫"""
    return await run_vbt_backtest(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        market=market,
        initial_capital=initial_capital,
        strategy_name="smc_v2",
        strategy_params={"min_conditions": min_conditions, "min_rr": min_rr},
    )
