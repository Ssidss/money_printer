"""
Backtest V3 — BaseStrategy ABC

所有策略都必須繼承這個 interface。
策略只能透過 DataProvider 取數據，不能碰 DB。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .models import Signal
from .provider import DataProvider


class BaseStrategy(ABC):
    """策略基類 — 定義標準 interface"""

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """策略唯一名稱，如 'smc_v2'"""
        ...

    @property
    @abstractmethod
    def strategy_type(self) -> str:
        """策略類型：'trend' | 'breakout' | 'mean_reversion' | 'sentiment'"""
        ...

    @abstractmethod
    def generate_signals(self, ticker: str, provider: DataProvider) -> list[Signal]:
        """
        核心方法：對一個 ticker 產生 0~N 個 Signal。

        - 只能用 provider 取數據
        - 回傳的 Signal 必須通過 validate()
        - buy signal 必須有 price_hint (entry + stop)
        """
        ...

    def on_position_update(self, ticker: str, position, provider: DataProvider) -> list[Signal]:
        """
        可選 hook：持倉更新時可以產生出場信號。
        Phase 1A 不用實作，Phase 2 Momentum trailing stop 會用到。

        預設：不產生任何信號（出場由 engine 的 stop/target 處理）
        """
        return []
