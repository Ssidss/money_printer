"""
Explosion Scanner Strategy Wrapper — US-2-02

把現有爆擊掃描器的 6 指標邏輯包成 BaseStrategy。
不依賴 DB，直接用 provider 的 OHLCV 計算。

買入條件: explosion_score >= score_threshold (default 60)
停損: entry × (1 - stop_pct) = -8%
目標: entry × (1 + target_pct) = +25%
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd

from ..backtest_v3.models import Signal
from ..backtest_v3.provider import DataProvider
from ..backtest_v3.strategy import BaseStrategy

logger = logging.getLogger(__name__)


def _compute_explosion_metrics(df: pd.DataFrame) -> dict:
    """
    從 OHLCV DataFrame 計算爆擊 6 指標。
    複用 scanner.py 的評分邏輯但不依賴 DB。
    """
    if len(df) < 22:
        return {}

    close = df["Close"]
    volume = df["Volume"]

    today_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])

    # 1. 單日漲幅 %
    change_pct = (today_close - prev_close) / prev_close * 100 if prev_close > 0 else 0

    # 2. 量比 = 今日量 / 20日均量
    vol_20ma = float(volume.rolling(20).mean().iloc[-1])
    today_vol = float(volume.iloc[-1])
    volume_ratio = today_vol / vol_20ma if vol_20ma > 0 else 0

    # 3. 連續上漲天數 + 累計漲幅
    consecutive_up = 0
    cum_gain_start = today_close
    for i in range(len(close) - 1, 0, -1):
        if float(close.iloc[i]) > float(close.iloc[i - 1]):
            consecutive_up += 1
            cum_gain_start = float(close.iloc[i - 1])
        else:
            break
    cumulative_gain_pct = (today_close - cum_gain_start) / cum_gain_start * 100 if cum_gain_start > 0 else 0

    # 4. 突破新高
    # Exclude today's bar for breakout comparison
    prev_closes = close.iloc[:-1]
    high_52w = float(prev_closes.tail(252).max()) if len(prev_closes) >= 252 else float(prev_closes.max())
    high_20d = float(prev_closes.tail(20).max())
    is_52w_high = today_close >= high_52w
    is_20d_high = today_close >= high_20d

    # 5. 量能加速度 = avg(近3日量) / avg(前3日量)
    if len(volume) >= 6:
        recent_3 = float(volume.iloc[-3:].mean())
        prior_3 = float(volume.iloc[-6:-3].mean())
        vol_acceleration = recent_3 / prior_3 if prior_3 > 0 else 1.0
    else:
        vol_acceleration = 1.0

    return {
        "change_pct": change_pct,
        "volume_ratio": volume_ratio,
        "consecutive_up_days": consecutive_up,
        "cumulative_gain_pct": cumulative_gain_pct,
        "is_52w_high": is_52w_high,
        "is_20d_high": is_20d_high,
        "vol_acceleration": vol_acceleration,
        "close_price": today_close,
        "volume": today_vol,
    }


def _score_explosion(m: dict) -> float:
    """
    計算爆擊分數 (0-100)，權重同 scanner.py
    """
    score = 0

    # 量比 30%
    vr = m["volume_ratio"]
    if vr >= 10: score += 30
    elif vr >= 5: score += 25
    elif vr >= 3: score += 18
    elif vr >= 2: score += 10

    # 漲幅 20%
    cp = m["change_pct"]
    if cp >= 20: score += 20
    elif cp >= 10: score += 15
    elif cp >= 5: score += 10
    elif cp >= 3: score += 5

    # 連漲 15%
    cu = m["consecutive_up_days"]
    if cu >= 5: score += 15
    elif cu >= 3: score += 10
    elif cu >= 2: score += 5

    # 突破 15%
    if m["is_52w_high"]: score += 15
    elif m["is_20d_high"]: score += 8

    # 量加速 10%
    va = m["vol_acceleration"]
    if va >= 2: score += 10
    elif va >= 1.5: score += 5

    # 低價 10%
    price = m["close_price"]
    if price <= 5: score += 10
    elif price <= 10: score += 7
    elif price <= 20: score += 3

    return score


class ExplosionScannerStrategy(BaseStrategy):
    """
    Explosion Scanner — 量價異常爆擊策略

    Config:
      score_threshold: 最低爆擊分數 (default 60)
      stop_pct: 固定停損 % (default 8.0 → -8%)
      target_pct: 固定目標 % (default 25.0 → +25%)
      signal_expiry_days: 信號有效期 (default 2, 爆擊股要快進)
    """

    def __init__(
        self,
        score_threshold: float = 60.0,
        stop_pct: float = 8.0,
        target_pct: float = 25.0,
        signal_expiry_days: int = 2,
    ):
        self.score_threshold = score_threshold
        self.stop_pct = stop_pct
        self.target_pct = target_pct
        self.signal_expiry_days = signal_expiry_days

    @property
    def strategy_name(self) -> str:
        return "explosion_scanner"

    @property
    def strategy_type(self) -> str:
        return "breakout"

    def generate_signals(self, ticker: str, provider: DataProvider) -> list[Signal]:
        current = provider.current_date()

        df = provider.get_ohlcv(ticker, lookback=252)
        if len(df) < 22:
            return []

        # 計算爆擊指標
        metrics = _compute_explosion_metrics(df)
        if not metrics:
            return []

        score = _score_explosion(metrics)

        # 低於門檻 → 不產生 signal
        if score < self.score_threshold:
            return []

        # Entry/Stop/Target
        entry = metrics["close_price"]
        stop = entry * (1 - self.stop_pct / 100)
        target = entry * (1 + self.target_pct / 100)
        rr_ratio = (target - entry) / (entry - stop) if entry > stop else 0

        # Confidence = score / 100, capped at [0.5, 0.95]
        confidence = min(max(score / 100.0, 0.5), 0.95)

        # Tier: 爆擊股一律探索倉位（風險高）
        # score >= 80 → 標準，其他探索
        tier = "標準" if score >= 80 else "探索"

        signal = Signal(
            signal_id=Signal.create_id(),
            ticker=ticker,
            side="long",
            action="buy",
            confidence=round(confidence, 3),
            strategy_name=self.strategy_name,
            strategy_type=self.strategy_type,
            timeframe="1d",
            timestamp=current,
            expiry=current + timedelta(days=self.signal_expiry_days),
            position_tier=tier,
            price_hint={
                "entry": round(entry, 2),
                "stop": round(stop, 2),
                "target": round(target, 2),
                "rr_ratio": round(rr_ratio, 2),
                "position_tier": tier,
            },
            meta={
                "explosion_score": round(score, 1),
                "change_pct": round(metrics["change_pct"], 2),
                "volume_ratio": round(metrics["volume_ratio"], 2),
                "consecutive_up_days": metrics["consecutive_up_days"],
                "is_52w_high": metrics["is_52w_high"],
                "is_20d_high": metrics["is_20d_high"],
                "vol_acceleration": round(metrics["vol_acceleration"], 2),
            },
        )

        return [signal]
