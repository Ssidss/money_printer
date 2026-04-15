"""
決策表策略 — 使用記憶引擎決策表進行交易信號生成

根據記憶引擎的決策表規則生成進出場信號。
"""

import logging
from typing import Optional, List
from datetime import datetime

import pandas as pd

from backend.app.services.backtest_vbt import BaseStrategy, Signal, DataProvider
from backend.app.services.memory_client import MemoryEngineClient

logger = logging.getLogger(__name__)


class DecisionTableStrategy(BaseStrategy):
    """
    使用記憶引擎決策表的策略。

    策略流程：
    1. 計算當前技術指標快照
    2. 查詢記憶引擎決策表
    3. 根據決策規則生成信號
    """

    def __init__(
        self,
        memory_client: Optional[MemoryEngineClient] = None,
        stock_category: str = 'large_cap',
        timeframe: str = '1d',
        min_confidence: float = 0.75,
    ):
        """
        初始化決策表策略。

        Args:
            memory_client: MemoryEngineClient 實例
            stock_category: 股票類別 (large_cap, mid_cap, small_cap)
            timeframe: 時間框架 (1d, 4h, 1h, 等等)
            min_confidence: 最小信心度 (0-1)
        """
        self.memory_client = memory_client or MemoryEngineClient()
        self.stock_category = stock_category
        self.timeframe = timeframe
        self.min_confidence = min_confidence

    @property
    def strategy_name(self) -> str:
        """策略名稱"""
        return "decision_table"

    @property
    def strategy_type(self) -> str:
        """策略類型"""
        return "decision-driven"

    def generate_signals(self, ticker: str, provider: DataProvider) -> List[Signal]:
        """
        根據決策表生成信號。

        Args:
            ticker: 股票代碼
            provider: 資料提供者

        Returns:
            信號清單
        """
        import asyncio

        try:
            # 取得當前 OHLCV 資料
            ohlcv = provider.get_ohlcv(ticker)
            if ohlcv is None or ohlcv.empty:
                return []

            # 計算技術指標快照
            indicators = _build_indicators_snapshot(ohlcv)

            # 查詢決策表
            # 由於 generate_signals 是 sync，需要用 asyncio 運行 async 方法
            # 這是一個臨時解決方案，實際應該使用 async/await 架構
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            decision = loop.run_until_complete(
                self.memory_client.lookup(
                    indicators=indicators,
                    stock_category=self.stock_category,
                    timeframe=self.timeframe
                )
            )

            # 根據決策規則生成信號
            if decision is None:
                return []

            action = decision.get('action', '').upper()
            confidence = decision.get('confidence', 0)

            if confidence < self.min_confidence:
                return []

            # 只在決策表建議 BUY 時生成信號
            if action != 'BUY':
                return []

            # 取得當前價格
            entry_price = provider.get_latest_price(ticker)
            if entry_price is None:
                return []

            # 構建信號
            stop_loss_pct = decision.get('stop_loss_pct', 2.5)
            take_profit_pct = decision.get('take_profit_pct', 5.0)

            stop_price = entry_price * (1 - stop_loss_pct / 100)
            target_price = entry_price * (1 + take_profit_pct / 100)

            signal = Signal(
                ticker=ticker,
                confidence=confidence,
                action="buy",
                strategy_name=self.strategy_name,
                strategy_type=self.strategy_type,
                timeframe=self.timeframe,
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                price_hint={
                    'entry': entry_price,
                    'stop_loss': stop_price,
                    'take_profit': target_price,
                }
            )

            return [signal]

        except Exception as e:
            logger.error(f"Error generating decision table signals for {ticker}: {e}")
            raise


def _build_indicators_snapshot(ohlcv) -> dict:
    """
    從 OHLCV 資料構建技術指標快照。

    Args:
        ohlcv: OHLCV DataFrame

    Returns:
        技術指標 dict
    """
    try:
        import ta

        close = ohlcv['Close'].values
        high = ohlcv['High'].values
        low = ohlcv['Low'].values
        volume = ohlcv['Volume'].values

        indicators = {}

        # RSI (14)
        if len(close) >= 14:
            indicators['rsi_14'] = float(ta.momentum.rsi(
                pd.Series(close), window=14
            ).iloc[-1])

        # MACD
        try:
            macd = ta.trend.macd(
                pd.Series(close), window_fast=12, window_slow=26, window_sign=9
            )
            if macd is not None and len(macd) > 0:
                indicators['macd'] = float(macd.iloc[-1])
        except:
            pass

        # 布林帶
        try:
            import pandas as pd
            bb = ta.volatility.bollinger_bands(
                pd.Series(close), window=20, window_dev=2
            )
            if bb is not None and len(bb) > 0:
                bb_position = (close[-1] - bb.iloc[-1, 2]) / (bb.iloc[-1, 0] - bb.iloc[-1, 2])
                indicators['bb_position'] = float(bb_position) if 0 <= bb_position <= 1 else 0

        except:
            pass

        # 成交量趨勢
        try:
            vol_trend = 'increasing' if volume[-1] > volume[-5:].mean() else 'decreasing'
            indicators['volume_trend'] = vol_trend
        except:
            pass

        return indicators

    except Exception as e:
        logger.warning(f"Failed to build indicators snapshot: {e}")
        return {}
