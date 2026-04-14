"""
Momentum Breakout Strategy — US-2-01

買入條件：
  1. 今日 close > N 日最高（突破）
  2. 成交量 > volume_ratio_min × 20日均量（放量確認）
  3. RSI 不超賣也不極端超買（30 < RSI < 85）

Price hint:
  entry: 下一日 open（T+1 fill）
  stop: entry - atr_stop_mult × ATR(14)
  target: entry + atr_target_mult × ATR(14)

Confidence:
  基於突破幅度(%) + 放量程度(volume_ratio)
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd

from ..models import Signal
from ..provider import DataProvider
from ..strategy import BaseStrategy

logger = logging.getLogger(__name__)


# ── Confidence 計算 ───────────────────────────────────────
def _calc_confidence(breakout_pct: float, volume_ratio: float) -> float:
    """
    突破幅度 + 放量程度 → confidence [0.4, 0.95]

    breakout_pct: 突破幅度 (%)，e.g. 2.5 means 2.5% above N-day high
    volume_ratio: 當日量 / 20 日均量
    """
    # 突破幅度分數 (0~0.5)
    bp_score = min(breakout_pct / 5.0, 1.0) * 0.5  # 5% 突破 → 滿分

    # 放量分數 (0~0.5)
    vr_score = min((volume_ratio - 1.0) / 3.0, 1.0) * 0.5  # 4x 量 → 滿分

    confidence = 0.4 + (bp_score + vr_score) * 0.55  # range [0.4, 0.95]
    return round(min(max(confidence, 0.4), 0.95), 3)


# ── Tier 判定 ─────────────────────────────────────────────
def _calc_tier(confidence: float, breakout_pct: float, volume_ratio: float) -> str:
    """
    核心: confidence >= 0.8 + breakout > 3% + vol > 2.5x
    標準: confidence >= 0.6
    探索: 其他
    """
    if confidence >= 0.8 and breakout_pct > 3.0 and volume_ratio > 2.5:
        return "核心"
    if confidence >= 0.6:
        return "標準"
    return "探索"


class MomentumBreakoutStrategy(BaseStrategy):
    """
    Momentum Breakout — 突破 N 日高點 + 放量確認

    Config:
      breakout_period: 突破回顧天數（default 20）
      volume_ratio_min: 最低量比（default 1.5）
      atr_stop_mult: ATR 停損倍數（default 2.0）
      atr_target_mult: ATR 目標倍數（default 3.0）
      min_rr: 最低 R:R（default 1.5）
      signal_expiry_days: 信號有效期（default 3）
    """

    def __init__(
        self,
        breakout_period: int = 20,
        volume_ratio_min: float = 1.5,
        atr_stop_mult: float = 2.0,
        atr_target_mult: float = 3.0,
        min_rr: float = 1.5,
        rsi_min: float = 30.0,
        rsi_max: float = 85.0,
        signal_expiry_days: int = 3,
    ):
        self.breakout_period = breakout_period
        self.volume_ratio_min = volume_ratio_min
        self.atr_stop_mult = atr_stop_mult
        self.atr_target_mult = atr_target_mult
        self.min_rr = min_rr
        self.rsi_min = rsi_min
        self.rsi_max = rsi_max
        self.signal_expiry_days = signal_expiry_days

    @property
    def strategy_name(self) -> str:
        return "momentum_breakout"

    @property
    def strategy_type(self) -> str:
        return "breakout"

    def generate_signals(self, ticker: str, provider: DataProvider) -> list[Signal]:
        current = provider.current_date()

        # 需要足夠的歷史數據
        df = provider.get_ohlcv(ticker, lookback=60)
        if len(df) < self.breakout_period + 5:
            return []

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        today_close = float(close.iloc[-1])
        today_volume = float(volume.iloc[-1])

        # ── Condition 1: 突破 N 日高點 ──
        # 用前 N 天（不含今天）的最高 close
        lookback_highs = close.iloc[-(self.breakout_period + 1):-1]
        n_day_high = float(lookback_highs.max())

        if today_close <= n_day_high:
            return []  # 沒有突破

        breakout_pct = (today_close - n_day_high) / n_day_high * 100

        # ── Condition 2: 放量確認 ──
        vol_20ma = float(volume.rolling(20).mean().iloc[-1])
        if vol_20ma <= 0:
            return []
        volume_ratio = today_volume / vol_20ma

        if volume_ratio < self.volume_ratio_min:
            return []  # 沒有放量

        # ── Condition 3: RSI 過濾 ──
        indicators = provider.get_indicators(ticker)
        rsi = indicators.get("rsi_14", 50.0)
        if rsi < self.rsi_min or rsi > self.rsi_max:
            return []  # RSI 不在合理範圍

        # ── ATR for stop/target ──
        atr = indicators.get("atr_14", 0.0)
        if atr <= 0:
            return []

        # entry = 下一日 open（由 engine 填）；先用今日 close 做 hint
        entry = today_close
        stop = entry - self.atr_stop_mult * atr
        target = entry + self.atr_target_mult * atr

        # 確保 stop 合理（不能是負數）
        if stop <= 0 or stop >= entry:
            return []

        rr_ratio = (target - entry) / (entry - stop)
        if rr_ratio < self.min_rr:
            return []

        confidence = _calc_confidence(breakout_pct, volume_ratio)
        tier = _calc_tier(confidence, breakout_pct, volume_ratio)

        signal = Signal(
            signal_id=Signal.create_id(),
            ticker=ticker,
            side="long",
            action="buy",
            confidence=confidence,
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
                "breakout_pct": round(breakout_pct, 2),
                "n_day_high": round(n_day_high, 2),
                "volume_ratio": round(volume_ratio, 2),
                "rsi_14": round(rsi, 1),
                "atr_14": round(atr, 2),
            },
        )

        return [signal]
