"""
Mock Strategy — 驗證 STRATEGY_REGISTRY 插件化運作

不包含真實交易邏輯，僅用於測試 registry 擴展機制：
- 每隔 20 個交易日產生一個 buy signal
- 固定停損 5%，固定目標 10%
- 驗證 generate_signals 介面通過 BaseStrategy 正確運作
"""
from __future__ import annotations

import logging

from ..backtest_vbt import Signal, DataProvider, BaseStrategy

logger = logging.getLogger(__name__)


class MockStrategy(BaseStrategy):
    """
    Mock 策略 — 用於驗證 registry 插件化。

    Params:
        signal_interval: 每隔幾個交易日產生一個 buy signal（預設 20）
        stop_pct: 固定停損比例（預設 0.05 = 5%）
        target_pct: 固定目標比例（預設 0.10 = 10%）
    """

    DEFAULT_PARAMS = {
        "signal_interval": 20,
        "stop_pct": 0.05,
        "target_pct": 0.10,
    }

    def __init__(
        self,
        signal_interval: int = 20,
        stop_pct: float = 0.05,
        target_pct: float = 0.10,
    ):
        self._signal_interval = signal_interval
        self._stop_pct = stop_pct
        self._target_pct = target_pct
        self._bar_count = 0

    @property
    def strategy_name(self) -> str:
        return "mock_test"

    @property
    def strategy_type(self) -> str:
        return "mock"

    def generate_signals(self, ticker: str, provider: DataProvider) -> list[Signal]:
        self._bar_count += 1

        if self._bar_count % self._signal_interval != 0:
            return []

        try:
            df = provider.get_ohlcv(ticker)
        except Exception:
            return []

        if df is None or len(df) < 5:
            return []

        current_close = float(df["Close"].iloc[-1])
        if current_close <= 0:
            return []

        entry = current_close
        stop = entry * (1 - self._stop_pct)
        target = entry * (1 + self._target_pct)

        sig = Signal(
            ticker=ticker,
            action="buy",
            confidence=0.5,
            source=self.strategy_name,
            price_hint={"entry": entry, "stop": stop, "target": target},
            metadata={"bar_count": self._bar_count, "mock": True},
        )

        return [sig]
