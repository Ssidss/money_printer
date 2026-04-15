"""
SMC v2 Strategy — Thin wrapper over existing SMC + EntryPlan logic.

不重寫 SMC 邏輯，只把 EntryPlan 轉成標準 Signal format。
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

from ..backtest_vbt import Signal, DataProvider, BaseStrategy

# Existing SMC modules
from ..smc import run_smc_analysis_v2
from ..smc.config import SmcConfig, DEFAULT_CONFIG
from ..decision.entry import generate_entry_plan

logger = logging.getLogger(__name__)


def _resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 10:
        return pd.DataFrame()
    df_ts = df.copy()
    df_ts.index = pd.to_datetime(df_ts.index)
    return df_ts.resample("W-FRI").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna()


def _resample_monthly(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 30:
        return pd.DataFrame()
    df_ts = df.copy()
    df_ts.index = pd.to_datetime(df_ts.index)
    return df_ts.resample("ME").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna()


# EntryPlan action → Signal action mapping
ACTION_MAP = {
    "買入": "buy",
    "等回調": "watch",
    "觀望": "watch",
    "不操作": "hold",
}

# Conditions → confidence mapping
CONFIDENCE_MAP = {
    4: 0.9,
    3: 0.7,
    2: 0.5,
    1: 0.3,
    0: 0.1,
}


class SMCStrategy(BaseStrategy):
    """SMC v2 策略 — 包成 BaseStrategy interface"""

    def __init__(
        self,
        smc_cfg: SmcConfig = DEFAULT_CONFIG,
        min_conditions: int = 2,
        min_rr: float = 1.5,
        signal_expiry_days: int = 3,
        market: str = "US",
    ):
        self.smc_cfg = smc_cfg
        self.min_conditions = min_conditions
        self.min_rr = min_rr
        self.signal_expiry_days = signal_expiry_days
        self.market = market

    @property
    def strategy_name(self) -> str:
        return "smc_v2"

    @property
    def strategy_type(self) -> str:
        return "trend"

    def generate_signals(self, ticker: str, provider: DataProvider) -> list[Signal]:
        """
        對一個 ticker 產生 SMC 信號。

        流程：
        1. 從 provider 取 OHLCV（日/週/月）
        2. 跑 run_smc_analysis_v2
        3. 跑 generate_entry_plan
        4. 把 EntryPlan 轉成 Signal
        """
        current = provider.current_date()

        # 取日線數據
        daily_df = provider.get_ohlcv(ticker, lookback=252)
        if len(daily_df) < 60:
            return []

        # 跑 SMC 日線分析
        try:
            smc_daily = run_smc_analysis_v2(
                ticker, daily_df,
                timeframe="daily",
                market=self.market,
                cfg=self.smc_cfg,
            )
        except Exception as e:
            logger.debug(f"SMC failed for {ticker}: {e}")
            return []

        # 週線/月線
        weekly_df = _resample_weekly(daily_df)
        monthly_df = _resample_monthly(daily_df)

        weekly_trend = "unknown"
        monthly_trend = "unknown"

        if len(weekly_df) >= 20:
            try:
                smc_w = run_smc_analysis_v2(
                    ticker, weekly_df,
                    timeframe="weekly",
                    market=self.market,
                    cfg=self.smc_cfg,
                )
                weekly_trend = smc_w.structure.trend.value if hasattr(smc_w.structure.trend, 'value') else str(smc_w.structure.trend)
            except Exception:
                pass

        if len(monthly_df) >= 12:
            try:
                smc_m = run_smc_analysis_v2(
                    ticker, monthly_df,
                    timeframe="monthly",
                    market=self.market,
                    cfg=self.smc_cfg,
                )
                monthly_trend = smc_m.structure.trend.value if hasattr(smc_m.structure.trend, 'value') else str(smc_m.structure.trend)
            except Exception:
                pass

        # 產生 EntryPlan
        current_price = float(daily_df["Close"].iloc[-1])
        closes = daily_df["Close"].tolist()
        highs = daily_df["High"].tolist()
        lows = daily_df["Low"].tolist()

        try:
            from ...schemas.smc import TrendDirection
            wt = TrendDirection(weekly_trend) if weekly_trend != "unknown" else TrendDirection.INSUFFICIENT
            mt = TrendDirection(monthly_trend) if monthly_trend != "unknown" else TrendDirection.INSUFFICIENT
        except (ValueError, KeyError):
            from ...schemas.smc import TrendDirection
            wt = TrendDirection.INSUFFICIENT
            mt = TrendDirection.INSUFFICIENT

        try:
            plan = generate_entry_plan(
                smc=smc_daily,
                current_price=current_price,
                closes=closes, highs=highs, lows=lows,
                weekly_trend=wt,
                monthly_trend=mt,
            )
        except Exception as e:
            logger.debug(f"EntryPlan failed for {ticker}: {e}")
            return []

        # 轉成 Signal
        return self._plan_to_signals(plan, ticker, current, smc_daily)

    def _plan_to_signals(self, plan, ticker: str, current: date, smc_daily) -> list[Signal]:
        """EntryPlan → Signal"""

        action = ACTION_MAP.get(plan.action, "hold")

        # 不操作 / 不推薦 → 不產生 signal
        if action == "hold" and plan.recommendation == "不推薦":
            return []

        # 條件不足 → 不產生 buy signal
        if plan.conditions_met < self.min_conditions:
            if action == "buy":
                action = "watch"

        # R:R 不夠 → 降級
        if plan.rr_ratio is not None and plan.rr_ratio < self.min_rr:
            if action == "buy":
                action = "watch"

        # buy signal 必須有 entry + stop
        price_hint = None
        if plan.entry_price and plan.stop_price:
            price_hint = {
                "entry": plan.entry_price,
                "stop": plan.stop_price,
                "target": plan.target_price,
                "rr_ratio": plan.rr_ratio,
                "position_tier": plan.position_tier if plan.position_tier != "none" else "標準",
            }

        # buy 沒有 price_hint → 降級成 watch
        if action == "buy" and price_hint is None:
            action = "watch"

        # watch/hold 不需要轉 signal（engine 不會處理）
        if action != "buy":
            return []

        confidence = CONFIDENCE_MAP.get(plan.conditions_met, 0.3)

        daily_trend = smc_daily.structure.trend.value if hasattr(smc_daily.structure.trend, 'value') else str(smc_daily.structure.trend)

        tier = price_hint.get("position_tier", "標準") if price_hint else "標準"

        signal = Signal(
            signal_id=Signal.create_id(),
            ticker=ticker,
            side="long",
            action=action,
            confidence=confidence,
            strategy_name=self.strategy_name,
            strategy_type=self.strategy_type,
            timeframe="1d",
            timestamp=current,
            expiry=current + timedelta(days=self.signal_expiry_days),
            position_tier=tier,
            price_hint=price_hint,
            meta={
                "daily_trend": daily_trend,
                "conditions_met": plan.conditions_met,
                "conditions_detail": plan.conditions_detail,
                "recommendation": plan.recommendation,
                "original_action": plan.action,
                "entry_source": plan.entry_source,
                "stop_source": plan.stop_source,
                "target_source": plan.target_source,
            },
        )

        return [signal]
