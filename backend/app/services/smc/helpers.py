"""
SMC v2 — 共用工具函數

ATR 計算、K 棒 resample、時間戳標準化、tick size。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import SmcConfig, DEFAULT_CONFIG


# ═══════════════════════════════════════════════════════════════
# ATR
# ═══════════════════════════════════════════════════════════════

def compute_atr(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """
    計算 Average True Range (Wilder's smoothing)。
    回傳跟輸入同長度的 array，前 period-1 筆填 NaN。
    """
    n = len(highs)
    if n < 2:
        return np.full(n, np.nan)

    tr = np.empty(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    atr = np.full(n, np.nan)
    if n < period:
        return atr

    # 第一個 ATR = 前 period 筆 TR 的 SMA
    atr[period - 1] = np.mean(tr[:period])
    # Wilder's smoothing
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr


def get_current_atr(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> float:
    """取最後一筆有效 ATR，找不到回傳 0。"""
    atr_arr = compute_atr(highs, lows, closes, period)
    # 從尾部往前找第一個非 NaN
    for v in reversed(atr_arr):
        if not np.isnan(v):
            return float(v)
    return 0.0


# ═══════════════════════════════════════════════════════════════
# Volume SMA
# ═══════════════════════════════════════════════════════════════

def compute_volume_sma(volumes: np.ndarray, period: int = 20) -> np.ndarray:
    """計算 Volume 的 SMA，前 period-1 筆填 NaN。"""
    n = len(volumes)
    sma = np.full(n, np.nan)
    if n < period:
        return sma
    cumsum = np.cumsum(volumes, dtype=float)
    sma[period - 1:] = (cumsum[period - 1:] - np.concatenate([[0], cumsum[:-period]])) / period
    return sma


# ═══════════════════════════════════════════════════════════════
# Tick Size
# ═══════════════════════════════════════════════════════════════

# 台股 tick size 對照表
_TW_TICK_TABLE = [
    (10, 0.01),
    (50, 0.05),
    (100, 0.1),
    (500, 0.5),
    (1000, 1.0),
    (float("inf"), 5.0),
]


def get_tick_size(price: float, market: str = "US") -> float:
    """
    取得 tick size。
    market: "US" | "TW"
    """
    if market == "TW":
        for threshold, tick in _TW_TICK_TABLE:
            if price < threshold:
                return tick
        return 5.0

    # 美股
    if price < 1.0:
        return 0.0001
    return 0.01


def get_swing_tolerance(
    atr: float,
    close: float,
    market: str = "US",
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> float:
    """
    計算 Swing Point 容差。
    tolerance = max(ATR * 0.05, tick_size * 3)
    + 波動率 regime 調整
    """
    tick = get_tick_size(close, market)
    tol = max(atr * cfg.swing_tolerance_atr_mult, tick * cfg.swing_tolerance_min_ticks)

    # 波動率 regime 調整
    if close > 0:
        vol_ratio = atr / close
        if vol_ratio > cfg.swing_high_vol_threshold:
            tol *= cfg.swing_high_vol_mult
        elif vol_ratio < cfg.swing_low_vol_threshold:
            tol *= cfg.swing_low_vol_mult

    return tol


# ═══════════════════════════════════════════════════════════════
# Resample
# ═══════════════════════════════════════════════════════════════

def _ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    """確保 DataFrame 有 DatetimeIndex。"""
    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        df.index = pd.to_datetime(df.index)
    return df


def resample_bars(df: pd.DataFrame, target_tf: str) -> pd.DataFrame:
    """
    將日線 resample 到週線/月線。

    target_tf: "weekly" | "monthly"
    """
    df = _ensure_datetime_index(df)

    rule = {"weekly": "W-FRI", "monthly": "ME"}[target_tf]

    resampled = df.resample(rule).agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna(subset=["Close"])

    return resampled


# ═══════════════════════════════════════════════════════════════
# DataFrame → numpy 快速存取
# ═══════════════════════════════════════════════════════════════

def df_to_arrays(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """將 OHLCV DataFrame 轉成 numpy arrays dict，方便高速計算。"""
    return {
        "open": df["Open"].values.astype(float),
        "high": df["High"].values.astype(float),
        "low": df["Low"].values.astype(float),
        "close": df["Close"].values.astype(float),
        "volume": df["Volume"].values.astype(float),
        "dates": np.array([str(d) for d in df.index]),
    }


def get_swing_n(timeframe: str, cfg: SmcConfig = DEFAULT_CONFIG) -> int:
    """依時間框架取 Swing Point 的 N 參數。"""
    return {
        "daily": cfg.swing_n_daily,
        "weekly": cfg.swing_n_weekly,
        "monthly": cfg.swing_n_monthly,
    }.get(timeframe, cfg.swing_n_daily)
