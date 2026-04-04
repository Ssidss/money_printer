from __future__ import annotations
"""
技術分析 Service
從 DB 讀取 price_history，計算各指標並回傳 0~100 評分
"""

import logging
from datetime import date

import pandas as pd
import ta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.stock import PriceHistory

logger = logging.getLogger(__name__)


async def load_price_df(db: AsyncSession, stock_id: int, limit: int = 120) -> pd.DataFrame | None:
    """從 DB 載入近 N 筆收盤資料為 DataFrame"""
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.stock_id == stock_id)
        .order_by(PriceHistory.date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    if not rows or len(rows) < 30:
        return None

    data = [
        {
            "date": r.date,
            "Open": float(r.open) if r.open else None,
            "High": float(r.high) if r.high else None,
            "Low": float(r.low) if r.low else None,
            "Close": float(r.close) if r.close else None,
            "Volume": int(r.volume) if r.volume else 0,
        }
        for r in reversed(rows)
    ]
    df = pd.DataFrame(data).set_index("date")
    df = df.dropna(subset=["Close"])
    return df


def _score_rsi(v: float) -> float:
    if v <= 30:   return 100.0
    if v <= 40:   return 80 + (40 - v) * 2
    if v <= 50:   return 50 + (50 - v) * 3
    if v <= 60:   return 50.0
    if v <= 70:   return 30 + (70 - v) * 2
    return max(0.0, 30 - (v - 70) * 3)


def _score_macd(macd: float, sig: float, hist: float, prev_hist: float) -> float:
    if macd > sig:
        if macd < 0: return 95.0 if hist > prev_hist else 80.0
        else:        return 75.0 if hist > prev_hist else 60.0
    else:
        return 35.0 if macd > 0 else 10.0


def _score_ma(close: float, ma5: float, ma20: float, ma60: float) -> float:
    if close > ma5 > ma20 > ma60:  return 90.0
    if close > ma20 > ma60:        return 75.0
    if close > ma60:               return 60.0
    if close < ma5 < ma20 < ma60:  return 10.0
    if close < ma20 < ma60:        return 25.0
    if close < ma60:               return 40.0
    return 50.0


def _score_bb(close: float, upper: float, lower: float) -> float:
    bw = upper - lower
    if bw == 0: return 50.0
    pos = (close - lower) / bw
    if pos <= 0.1:   return 90.0
    if pos <= 0.25:  return 75.0
    if pos <= 0.5:   return 50.0
    if pos <= 0.75:  return 40.0
    if pos <= 0.9:   return 20.0
    return 10.0


def _score_volume(vol: float, vol_ma: float) -> float:
    if vol_ma == 0: return 50.0
    r = vol / vol_ma
    if r >= 2.0:  return 90.0
    if r >= 1.5:  return 75.0
    if r >= 1.0:  return 60.0
    if r >= 0.7:  return 45.0
    return 30.0


def analyze_df(df: pd.DataFrame) -> dict:
    """對 DataFrame 做技術分析，回傳評分與指標快照"""
    cfg = settings
    close = df["Close"]
    volume = df["Volume"]

    rsi = ta.momentum.RSIIndicator(close, window=cfg.RSI_PERIOD).rsi().iloc[-1]

    macd_obj = ta.trend.MACD(close, window_fast=cfg.MACD_FAST, window_slow=cfg.MACD_SLOW, window_sign=cfg.MACD_SIGNAL)
    macd_val  = macd_obj.macd().iloc[-1]
    macd_sig  = macd_obj.macd_signal().iloc[-1]
    macd_hist = macd_obj.macd_diff().iloc[-1]
    macd_hist_prev = macd_obj.macd_diff().iloc[-2]

    ma5  = close.rolling(cfg.MA_SHORT).mean().iloc[-1]
    ma20 = close.rolling(cfg.MA_MID).mean().iloc[-1]
    ma60 = close.rolling(cfg.MA_LONG).mean().iloc[-1] if len(df) >= cfg.MA_LONG else ma20

    bb = ta.volatility.BollingerBands(close, window=cfg.BB_PERIOD, window_dev=2)
    bb_upper = bb.bollinger_hband().iloc[-1]
    bb_lower = bb.bollinger_lband().iloc[-1]

    vol_ma = volume.rolling(cfg.VOLUME_MA).mean().iloc[-1]
    vol_latest = float(volume.iloc[-1])
    current = float(close.iloc[-1])

    weights = {"rsi": 0.25, "macd": 0.30, "ma": 0.25, "bb": 0.10, "vol": 0.10}
    sub = {
        "rsi":  _score_rsi(rsi),
        "macd": _score_macd(macd_val, macd_sig, macd_hist, macd_hist_prev),
        "ma":   _score_ma(current, ma5, ma20, ma60),
        "bb":   _score_bb(current, bb_upper, bb_lower),
        "vol":  _score_volume(vol_latest, vol_ma),
    }
    total = sum(sub[k] * weights[k] for k in sub)

    signals = []
    if rsi < cfg.RSI_OVERSOLD:   signals.append(f"RSI {rsi:.1f} 超賣（買入區）")
    elif rsi > cfg.RSI_OVERBOUGHT: signals.append(f"RSI {rsi:.1f} 超買（注意風險）")
    if macd_val > macd_sig:       signals.append("MACD 金叉（多頭訊號）")
    else:                         signals.append("MACD 死叉（空頭訊號）")
    if current > ma5 > ma20:      signals.append("均線多頭排列")
    elif current < ma5 < ma20:    signals.append("均線空頭排列")
    vol_ratio = vol_latest / vol_ma if vol_ma > 0 else 0
    signals.append(f"成交量 {vol_ratio:.1f}x 均量")

    return {
        "score": round(total, 1),
        "sub_scores": sub,
        "indicators": {
            "price": round(current, 2),
            "rsi": round(float(rsi), 1),
            "macd": round(float(macd_val), 6),
            "macd_signal": round(float(macd_sig), 6),
            "ma5": round(float(ma5), 2),
            "ma20": round(float(ma20), 2),
            "ma60": round(float(ma60), 2),
            "bb_upper": round(float(bb_upper), 2),
            "bb_lower": round(float(bb_lower), 2),
            "volume_ratio": round(vol_ratio, 2),
        },
        "signals": signals,
    }


async def analyze_stock(db: AsyncSession, stock_id: int) -> dict | None:
    """從 DB 讀取股價後做技術分析"""
    df = await load_price_df(db, stock_id)
    if df is None:
        return None
    return analyze_df(df)
