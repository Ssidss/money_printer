"""
SMC v2 — 整合入口

run_smc_analysis_v2() 呼叫所有模組，回傳統一的 SmcResult。
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ...schemas.smc import (
    SmcResult,
    RegimeResult,
    MarketRegime,
)
from .config import SmcConfig, DEFAULT_CONFIG
from .helpers import compute_atr, df_to_arrays, resample_bars
from .structure import analyze_structure
from .order_block import analyze_order_blocks
from .fvg import analyze_fvg
from .liquidity import analyze_liquidity
from .fibonacci import analyze_fibonacci


def run_smc_analysis_v2(
    ticker: str,
    df: pd.DataFrame,
    timeframe: str = "daily",
    market: str = "US",
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> SmcResult:
    """
    SMC v2 完整分析入口。

    輸入：
      ticker: 股票代號
      df: OHLCV DataFrame（index 為日期，欄位 Open/High/Low/Close/Volume）
      timeframe: "daily" | "weekly" | "monthly"
      market: "US" | "TW"
      cfg: SMC 配置

    輸出：SmcResult（統一結果型別）
    """
    warnings: list[str] = []
    n = len(df)

    # 清理 NaN（yfinance 可能回傳盤中不完整數據）
    df = df.dropna(subset=["Close"])
    n = len(df)

    # 數據品質檢查
    if n < 20:
        return _empty_result(ticker, timeframe, n, cfg, ["insufficient bars (<20)"], "insufficient")

    # 如果需要 resample
    if timeframe in ("weekly", "monthly") and _is_daily_data(df):
        df = resample_bars(df, timeframe)
        n = len(df)
        if n < 10:
            return _empty_result(ticker, timeframe, n, cfg, [f"insufficient {timeframe} bars after resample"], "insufficient")

    # 轉換為 numpy arrays
    arrays = df_to_arrays(df)
    opens = arrays["open"]
    highs = arrays["high"]
    lows = arrays["low"]
    closes = arrays["close"]
    volumes = arrays["volume"]
    dates = arrays["dates"]

    # 計算 ATR
    atr = compute_atr(highs, lows, closes, cfg.atr_period)

    # ── 1. 結構分析 ──
    structure = analyze_structure(
        highs, lows, closes, opens, dates, volumes, atr,
        timeframe, market, cfg,
    )

    # ── 2. Order Block ──
    order_blocks = analyze_order_blocks(
        opens, highs, lows, closes, volumes, dates, atr,
        structure.events, timeframe, cfg,
    )

    # ── 3. FVG ──
    fvg = analyze_fvg(
        opens, highs, lows, closes, dates, atr,
        timeframe, cfg,
    )

    # ── 4. 流動性 ──
    liquidity = analyze_liquidity(
        opens, highs, lows, closes, dates, atr,
        structure.swing_highs, structure.swing_lows, cfg,
    )

    # ── 5. Fibonacci ──
    fibonacci = analyze_fibonacci(
        opens, highs, lows, closes, atr,
        structure.swing_highs, structure.swing_lows, cfg,
    )

    # ── 6. Regime（簡化版，P2 再做完整版）──
    regime = _simple_regime(atr, closes, cfg)

    # 收集 warnings
    if not structure.swing_highs or not structure.swing_lows:
        warnings.append("no swing points detected")
    if not order_blocks.active_bullish and not order_blocks.active_bearish:
        warnings.append("no active order blocks")
    if not fvg.active:
        warnings.append("no active FVG")
    if not fibonacci.valid:
        warnings.append("no valid fibonacci leg")

    data_quality = "full"
    if warnings:
        data_quality = "partial"
    if n < 50:
        data_quality = "partial"
        warnings.append("limited bar count (<50)")

    return SmcResult(
        ticker=ticker,
        timeframe=timeframe,
        bar_count=n,
        computed_at=datetime.now(timezone.utc).isoformat(),
        strategy_hash=cfg.strategy_hash(),
        structure=structure,
        order_blocks=order_blocks,
        fvg=fvg,
        liquidity=liquidity,
        fibonacci=fibonacci,
        regime=regime,
        warnings=warnings,
        data_quality=data_quality,
    )


def _is_daily_data(df: pd.DataFrame) -> bool:
    """判斷是否為日線數據（非已 resample 的週/月線）。"""
    if len(df) < 10:
        return True
    # 看平均間隔，日線約 1-3 天
    idx = pd.to_datetime(df.index)
    avg_gap = (idx[-1] - idx[0]).days / len(idx)
    return avg_gap < 5


def _simple_regime(
    atr: np.ndarray,
    closes: np.ndarray,
    cfg: SmcConfig,
) -> RegimeResult:
    """簡化版 regime 偵測（完整版在 P2）。"""
    valid_atr = atr[~np.isnan(atr)]
    if len(valid_atr) < 20:
        return RegimeResult()

    current_atr = float(valid_atr[-1])
    percentile = float(np.sum(valid_atr <= current_atr) / len(valid_atr) * 100)

    if percentile > 80:
        regime = MarketRegime.HIGH_VOL
    elif percentile < 20:
        regime = MarketRegime.LOW_VOL
    else:
        regime = MarketRegime.TRENDING

    return RegimeResult(regime=regime, atr_percentile=round(percentile, 1))


def _empty_result(
    ticker: str,
    timeframe: str,
    bar_count: int,
    cfg: SmcConfig,
    warnings: list[str],
    quality: str,
) -> SmcResult:
    """回傳空的 SmcResult。"""
    from ...schemas.smc import (
        StructureResult,
        OrderBlockResult,
        FvgResult,
        LiquidityResult,
        FibonacciResult,
        RegimeResult,
        TrendDirection,
    )
    return SmcResult(
        ticker=ticker,
        timeframe=timeframe,
        bar_count=bar_count,
        computed_at=datetime.now(timezone.utc).isoformat(),
        strategy_hash=cfg.strategy_hash(),
        structure=StructureResult(trend=TrendDirection.INSUFFICIENT),
        order_blocks=OrderBlockResult(),
        fvg=FvgResult(),
        liquidity=LiquidityResult(),
        fibonacci=FibonacciResult(),
        regime=RegimeResult(),
        warnings=warnings,
        data_quality=quality,
    )
