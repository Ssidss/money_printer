"""
Backtest V3 — DataProvider

策略的唯一數據來源。策略不碰 DB，全部透過 Provider。
HistoricalProvider: 回測用，嚴格控制時間可見範圍（防 lookahead）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd


class DataProvider(ABC):
    """策略的唯一數據來源 — ABC"""

    @abstractmethod
    def get_ohlcv(self, ticker: str, lookback: int = 252) -> pd.DataFrame:
        """回傳 OHLCV DataFrame, index=date, max(date) <= current_date"""
        ...

    @abstractmethod
    def get_latest_price(self, ticker: str) -> Optional[float]:
        """current_date 的 close price"""
        ...

    @abstractmethod
    def get_indicators(self, ticker: str) -> dict:
        """convenience: RSI, MACD, MA, ATR, BB, Volume — 用 get_ohlcv() 算"""
        ...

    @abstractmethod
    def get_sentiment(self, ticker: str) -> Optional[dict]:
        """{"score": 72, "label": "正面", "article_count": 5}"""
        ...

    @abstractmethod
    def get_market_regime(self) -> dict:
        """{"vix": 18.5, "spy_trend": "uptrend", "regime": "trending"}"""
        ...

    @abstractmethod
    def get_universe(self) -> list[str]:
        """可交易的 ticker 清單"""
        ...

    @abstractmethod
    def is_tradable(self, ticker: str) -> bool:
        """停牌 / 資料不足 / 流動性太差 → False"""
        ...

    @abstractmethod
    def current_date(self) -> date:
        ...

    @abstractmethod
    def advance_day(self) -> Optional[date]:
        """前進一天，回傳新日期。超出 end_date → None"""
        ...

    def get_bar(self, ticker: str, target_date: date) -> Optional[dict]:
        """取得特定日期的 OHLCV bar — engine 用，策略不應直接呼叫"""
        ...


# ── Data Split Presets ──────────────────────────────────────────

DATA_SPLITS = {
    "train":      (date(2018, 1, 1), date(2022, 12, 31)),
    "validation": (date(2023, 1, 1), date(2024, 12, 31)),
    "test":       (date(2025, 1, 1), date(2026, 12, 31)),
}


def get_split_dates(split: str) -> tuple[date, date]:
    """回傳 (start_date, end_date) for a named split."""
    if split in DATA_SPLITS:
        return DATA_SPLITS[split]
    raise ValueError(f"Unknown split '{split}'. Valid: {list(DATA_SPLITS.keys())}")


class HistoricalProvider(DataProvider):
    """
    回測用 Provider — 從預載的 price_data dict 取數據。

    price_data: {"NVDA": DataFrame(index=date, cols=[Open,High,Low,Close,Volume]), ...}
    嚴格規則：get_ohlcv() 只回傳 current_date 及之前的數據。
    """

    def __init__(
        self,
        price_data: dict[str, pd.DataFrame],
        stocks_info: list[dict],
        start_date: date,
        end_date: date,
        min_bars: int = 60,
        min_volume: int = 100_000,
    ):
        # 統一 index 為 DatetimeIndex（DB 載入的是 datetime.date objects）
        self._price_data = {}
        for ticker, df in price_data.items():
            df = df.copy()
            df.index = pd.to_datetime(df.index)
            self._price_data[ticker] = df
        self._stocks_info = {s["ticker"]: s for s in stocks_info}
        self._start_date = start_date
        self._end_date = end_date
        self._min_bars = min_bars
        self._min_volume = min_volume

        # 建立交易日曆（所有股票的日期聯集）
        all_dates = set()
        for df in price_data.values():
            all_dates.update(df.index.tolist())
        self._trading_days = sorted([
            d if isinstance(d, date) else d.date() if hasattr(d, 'date') else d
            for d in all_dates
            if (start_date <= (d if isinstance(d, date) else d.date() if hasattr(d, 'date') else d) <= end_date)
        ])

        self._day_index = -1  # advance_day() 會推到 0
        self._current_date: Optional[date] = None

        # 預算 tradable universe
        self._universe: list[str] = []
        self._tradable_cache: dict[str, bool] = {}

    def _ensure_date_type(self, d) -> date:
        if isinstance(d, date) and not isinstance(d, pd.Timestamp):
            return d
        if hasattr(d, 'date'):
            return d.date()
        return d

    def current_date(self) -> date:
        if self._current_date is None:
            raise RuntimeError("Must call advance_day() first")
        return self._current_date

    def advance_day(self) -> Optional[date]:
        self._day_index += 1
        if self._day_index >= len(self._trading_days):
            return None
        self._current_date = self._ensure_date_type(self._trading_days[self._day_index])
        # 每天重算 tradable（因為數據量在變）
        self._update_universe()
        return self._current_date

    def _update_universe(self):
        self._universe = []
        self._tradable_cache = {}
        for ticker in self._price_data:
            tradable = self._check_tradable(ticker)
            self._tradable_cache[ticker] = tradable
            if tradable:
                self._universe.append(ticker)

    def _to_ts(self, d: date):
        """統一轉 Timestamp 做比較"""
        return pd.Timestamp(d)

    def _check_tradable(self, ticker: str) -> bool:
        df = self._price_data.get(ticker)
        if df is None or len(df) == 0:
            return False

        ts = self._to_ts(self._current_date)
        visible = df[df.index <= ts]
        if len(visible) < self._min_bars:
            return False

        # 近 5 天平均成交量 < min_volume → False
        recent = visible.tail(5)
        if len(recent) < 5:
            return False
        if recent["Volume"].mean() < self._min_volume:
            return False

        return True

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
        """取特定日期的 bar — 只給 engine 用"""
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
        """Convenience: 用 get_ohlcv() 算常見技術指標"""
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

        # Moving averages
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None

        # ATR 14
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]

        # Bollinger Bands
        bb_mid = ma20
        bb_std = close.rolling(20).std().iloc[-1]
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std

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
        # Phase 1A: sentiment 不納入回測
        return None

    def get_market_regime(self) -> dict:
        # Phase 1A: regime 不納入回測
        return {"vix": None, "spy_trend": "unknown", "regime": "unknown"}

    def get_universe(self) -> list[str]:
        return list(self._universe)

    def is_tradable(self, ticker: str) -> bool:
        return self._tradable_cache.get(ticker, False)

    @property
    def trading_days(self) -> list[date]:
        return list(self._trading_days)

    @property
    def total_days(self) -> int:
        return len(self._trading_days)

    @property
    def progress_pct(self) -> float:
        if not self._trading_days:
            return 0.0
        return (self._day_index + 1) / len(self._trading_days) * 100
