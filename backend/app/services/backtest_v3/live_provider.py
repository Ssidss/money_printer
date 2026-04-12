"""
Backtest V3 — LiveProvider

即時信號用的 DataProvider 實作。
從 DB 載入的 price_data 中取最新日期作為 current_date，
策略可以直接呼叫 generate_signals() 產生即時信號。
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from .provider import DataProvider


class LiveProvider(DataProvider):
    """
    即時信號用 Provider。

    跟 HistoricalProvider 的差別：
    - 不需要 advance_day()，直接以最新日期為 current_date
    - 不需要 start/end range
    - 可以只載入單支股票的資料
    """

    def __init__(
        self,
        price_data: dict[str, pd.DataFrame],
        target_date: Optional[date] = None,
        min_bars: int = 22,
    ):
        self._price_data: dict[str, pd.DataFrame] = {}
        for ticker, df in price_data.items():
            df = df.copy()
            df.index = pd.to_datetime(df.index)
            self._price_data[ticker] = df

        self._min_bars = min_bars

        # target_date = 指定日期 or 所有資料中的最新日期
        if target_date:
            self._current_date = target_date
        else:
            all_max = [df.index.max() for df in self._price_data.values() if len(df) > 0]
            if all_max:
                self._current_date = max(all_max).date()
            else:
                self._current_date = date.today()

    def current_date(self) -> date:
        return self._current_date

    def advance_day(self) -> Optional[date]:
        # LiveProvider 不前進，永遠在 current_date
        return None

    def _to_ts(self, d: date):
        return pd.Timestamp(d)

    def get_ohlcv(self, ticker: str, lookback: int = 252) -> pd.DataFrame:
        df = self._price_data.get(ticker)
        if df is None:
            return pd.DataFrame()
        ts = self._to_ts(self._current_date)
        visible = df[df.index <= ts]
        return visible.tail(lookback).copy()

    def get_latest_price(self, ticker: str) -> Optional[float]:
        df = self.get_ohlcv(ticker, lookback=1)
        if df.empty:
            return None
        return float(df.iloc[-1]["Close"])

    def get_bar(self, ticker: str, target_date: date) -> Optional[dict]:
        df = self._price_data.get(ticker)
        if df is None:
            return None
        ts = self._to_ts(target_date)
        if ts not in df.index:
            return None
        row = df.loc[ts]
        return {
            "Open": float(row["Open"]),
            "High": float(row["High"]),
            "Low": float(row["Low"]),
            "Close": float(row["Close"]),
            "Volume": int(row["Volume"]),
        }

    def get_indicators(self, ticker: str) -> dict:
        df = self.get_ohlcv(ticker, lookback=60)
        if len(df) < 20:
            return {}

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        # RSI 14
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = (ema12 - ema26).iloc[-1]
        macd_signal = (ema12 - ema26).ewm(span=9).mean().iloc[-1]

        # MA
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None

        # ATR 14
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]

        # BB
        bb_std = close.rolling(20).std().iloc[-1]
        bb_upper = ma20 + 2 * bb_std
        bb_lower = ma20 - 2 * bb_std

        # Volume ratio
        vol_avg = volume.rolling(20).mean().iloc[-1]
        vol_ratio = volume.iloc[-1] / vol_avg if vol_avg > 0 else 1.0

        return {
            "rsi_14": float(rsi) if not np.isnan(rsi) else 50.0,
            "macd": float(macd),
            "macd_signal": float(macd_signal),
            "ma_20": float(ma20),
            "ma_50": float(ma50) if ma50 is not None else None,
            "atr_14": float(atr) if not np.isnan(atr) else 0.0,
            "bb_upper": float(bb_upper),
            "bb_lower": float(bb_lower),
            "volume_ratio": float(vol_ratio),
        }

    def get_sentiment(self, ticker: str) -> Optional[dict]:
        return None

    def get_market_regime(self) -> dict:
        return {"vix": None, "spy_trend": "unknown", "regime": "unknown"}

    def get_universe(self) -> list[str]:
        return list(self._price_data.keys())

    def is_tradable(self, ticker: str) -> bool:
        df = self._price_data.get(ticker)
        if df is None or len(df) == 0:
            return False
        ts = self._to_ts(self._current_date)
        visible = df[df.index <= ts]
        if len(visible) < self._min_bars:
            return False
        recent = visible.tail(5)
        if len(recent) < 5:
            return False
        return True
