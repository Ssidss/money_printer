"""
VectorBT 整合 — SMC 回測 Service

架構：
  1. 從 DB 載入 ticker 的 OHLCV 歷史（含 252 bar lookback buffer）
  2. 滑動窗口呼叫 SMCStrategy.generate_signals()（防前視偏誤）
  3. 聚合 entries / sl_stop / tp_stop arrays（T+1 執行）
  4. vbt.Portfolio.from_signals() 向量化計算績效
  5. 回傳結構化 BacktestResult dict

前視偏誤防護：
  - 信號在 T 日收盤後產生，T+1 開盤才執行（entries.shift(1)）
  - HistoricalProvider.get_ohlcv() 僅回傳 <= current_date 的數據
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

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


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class VbtBacktestResult:
    ticker: str
    market: str
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

def _generate_smc_signal_series(
    ticker: str,
    price_df: pd.DataFrame,
    start_date: date,
    end_date: date,
    market: str,
    min_conditions: int,
    min_rr: float,
) -> tuple[pd.Series, pd.Series, pd.Series, int]:
    """
    滑動窗口逐日產生 SMC 信號，回傳對齊 price_df 日期索引的 boolean/float Series。

    Returns:
        entries (bool Series):  當日有 buy signal
        sl_stops (float Series): 停損幅度（相對 entry price 的比例，NaN 表示無信號）
        tp_stops (float Series): 停利幅度（相對 entry price 的比例，NaN 表示無信號）
        signals_count: 產生 buy signal 的天數
    """
    # 延遲 import 避免影響啟動時間
    from .backtest_v3.strategies.smc_strategy import SMCStrategy
    from .backtest_v3.provider import HistoricalProvider

    strategy = SMCStrategy(
        min_conditions=min_conditions,
        min_rr=min_rr,
        signal_expiry_days=3,
        market=market,
    )

    # price_df 索引必須是 DatetimeIndex
    price_df = price_df.copy()
    price_df.index = pd.to_datetime(price_df.index)

    # 需要 lookback buffer：在 start_date 前至少 252 bars
    provider = HistoricalProvider(
        price_data={ticker: price_df},
        stocks_info=[{"ticker": ticker, "market": market, "id": 0}],
        start_date=start_date,
        end_date=end_date,
        min_bars=60,
        min_volume=0,   # 單支股票不做 volume filter
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

            # 計算相對停損/停利幅度
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

async def run_smc_backtest(
    ticker: str,
    start_date: date,
    end_date: date,
    market: str = "US",
    initial_capital: float = 100_000,
    min_conditions: int = 2,
    min_rr: float = 1.5,
) -> dict:
    """
    執行 SMC 策略 VectorBT 回測。

    Args:
        ticker:         股票代碼（如 "2330" 或 "NVDA"）
        start_date:     回測開始日
        end_date:       回測結束日
        market:         "TW" 或 "US"
        initial_capital: 初始資金
        min_conditions: SMC 最少滿足條件數（預設 2）
        min_rr:         最低風報比（預設 1.5）

    Returns:
        dict 格式的 BacktestResult（可直接序列化為 JSON）
    """
    t0 = time.time()

    # ── Step 1: 從 DB 載入 OHLCV ────────────────────────────────────────
    from ..database import AsyncSessionLocal
    from ..models.stock import Stock, PriceHistory
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        # 取 stock_id
        stock_row = (await db.execute(
            select(Stock).where(Stock.ticker == ticker)
        )).scalar_one_or_none()

        if stock_row is None:
            return {"error": f"Ticker '{ticker}' not found in database"}

        # 需要 252 bars lookback buffer 在 start_date 之前
        buffer_start = start_date - timedelta(days=400)  # 約 252 交易日 + 安全邊際

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

    # 建立 DataFrame
    price_df = pd.DataFrame([{
        "date": r.date,
        "Open": float(r.open or 0),
        "High": float(r.high or 0),
        "Low": float(r.low or 0),
        "Close": float(r.close or 0),
        "Volume": int(r.volume or 0),
    } for r in price_rows]).set_index("date").sort_index()

    price_df.index = pd.to_datetime(price_df.index)

    # ── Step 2: 預計算 SMC signals ───────────────────────────────────────
    logger.info(f"[backtest_vbt] Generating SMC signals for {ticker} "
                f"{start_date} ~ {end_date} ({len(price_df)} bars total)")

    entries_raw, sl_stops, tp_stops, signals_count = _generate_smc_signal_series(
        ticker=ticker,
        price_df=price_df,
        start_date=start_date,
        end_date=end_date,
        market=market,
        min_conditions=min_conditions,
        min_rr=min_rr,
    )

    # ── Step 3: 準備 VectorBT 輸入 ──────────────────────────────────────
    # 只取回測期間的 close series
    period_mask = (price_df.index >= pd.Timestamp(start_date)) & \
                  (price_df.index <= pd.Timestamp(end_date))
    close = price_df.loc[period_mask, "Close"]

    # T+1 執行：信號在 T 日產生，T+1 日才能買入（shift by 1）
    entries = entries_raw.shift(1).fillna(False).astype(bool)
    sl_stops_shifted = sl_stops.shift(1)
    tp_stops_shifted = tp_stops.shift(1)

    # 對齊索引（以防萬一）
    entries = entries.reindex(close.index, fill_value=False)
    sl_stops_shifted = sl_stops_shifted.reindex(close.index, fill_value=np.nan)
    tp_stops_shifted = tp_stops_shifted.reindex(close.index, fill_value=np.nan)

    # ── Step 4: VectorBT Portfolio ──────────────────────────────────────
    import vectorbt as vbt

    fees = _TW_FEES if market == "TW" else _US_FEES
    slippage = _US_SLIPPAGE  # TW 的滑點差異小，統一用相同值

    # sl_stop / tp_stop 需要 float64 Series，NaN 表示「這天無信號，不設止損」
    # VectorBT 在沒有 sl_stop 的位置會用前一個有效值（forward fill），
    # 因此確保只有 entry 當日有值
    sl_arr = sl_stops_shifted.values.astype(float)
    tp_arr = tp_stops_shifted.values.astype(float)

    # 用均值填充（作為保守預設值）
    sl_mean = float(np.nanmean(sl_arr)) if not np.all(np.isnan(sl_arr)) else 0.05
    tp_mean = float(np.nanmean(tp_arr)) if not np.all(np.isnan(tp_arr)) else 0.10

    # 無停損信號的 bar 用均值填充，避免 VBT 警告
    sl_arr = np.where(np.isnan(sl_arr), sl_mean, sl_arr)
    tp_arr = np.where(np.isnan(tp_arr), tp_mean, tp_arr)

    try:
        pf = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=pd.Series(False, index=close.index),  # 出場由 sl/tp 觸發
            sl_stop=sl_arr,
            tp_stop=tp_arr,
            fees=fees,
            slippage=slippage,
            init_cash=initial_capital,
            freq="D",
            upon_opposite_entry="ignore",   # 已持倉時忽略新信號
        )
    except Exception as e:
        logger.error(f"VectorBT portfolio creation failed for {ticker}: {e}")
        return {"error": f"VectorBT error: {str(e)}"}

    # ── Step 5: 提取績效指標 ─────────────────────────────────────────────
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
        total_return = 0.0
        sharpe = 0.0
        max_dd = 0.0
        win_rate = 0.0
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

                # 持倉天數
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
        f"[backtest_vbt] {ticker} done in {elapsed}s: "
        f"return={total_return:.1f}%, sharpe={sharpe:.2f}, "
        f"max_dd={max_dd:.1f}%, trades={total_trades}, signals={signals_count}"
    )

    result = VbtBacktestResult(
        ticker=ticker,
        market=market,
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
