from __future__ import annotations
"""
技術分析 Service（趨勢追蹤版 v2）
從 DB 讀取 price_history，計算動量指標並回傳 0~100 評分

設計哲學：趨勢追蹤
- RSI 高 = 動量強，不懲罰
- 布林突破上軌 = 強勢，加分
- 量價配合 = 關鍵確認信號
- 與 SMC 方向一致：順勢做多
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


# ── 趨勢追蹤版評分函數 ──────────────────────────────────────────

def _score_rsi(v: float) -> float:
    """
    RSI 評分（趨勢追蹤）
    - 50-70: 健康動量區間 → 高分
    - 70-80: 強勢動量 → 仍然高分（不懲罰）
    - >80: 極端過熱 → 輕微減分（但不重罰）
    - 40-50: 動量偏弱
    - <30: 超賣弱勢 → 低分（趨勢追蹤不抄底）
    """
    if 50 <= v <= 65:   return 85.0
    if 65 < v <= 75:    return 80.0
    if 75 < v <= 80:    return 70.0
    if v > 80:          return max(50.0, 70 - (v - 80) * 2)
    if 40 <= v < 50:    return 55.0
    if 30 <= v < 40:    return 35.0
    return 20.0


def _score_macd(macd: float, sig: float, hist: float, prev_hist: float) -> float:
    """
    MACD 評分（趨勢追蹤）
    - 金叉 + 柱體放大 → 最高分
    - 金叉 + 柱體縮小 → 動量減弱但方向仍對
    - 死叉 → 低分
    """
    hist_expanding = hist > prev_hist

    if macd > sig:  # 金叉
        if macd < 0:
            return 90.0 if hist_expanding else 72.0
        else:
            return 85.0 if hist_expanding else 65.0
    else:  # 死叉
        if macd > 0:
            return 40.0 if not hist_expanding else 30.0
        else:
            return 15.0


def _score_ma(close: float, ma5: float, ma20: float, ma60: float) -> float:
    """均線排列評分（本來就是趨勢邏輯，保持原設計）"""
    if close > ma5 > ma20 > ma60:  return 90.0
    if close > ma20 > ma60:        return 75.0
    if close > ma60:               return 60.0
    if close < ma5 < ma20 < ma60:  return 10.0
    if close < ma20 < ma60:        return 25.0
    if close < ma60:               return 35.0
    return 50.0


def _score_bb(close: float, upper: float, lower: float) -> float:
    """
    布林通道評分（趨勢追蹤版）
    - 突破上軌 = 強勢動能，高分
    - 中軌以上 = 健康趨勢
    - 跌破下軌 = 弱勢
    """
    bw = upper - lower
    if bw == 0:
        return 50.0
    mid = (upper + lower) / 2

    if close > upper:   return 85.0
    if close > mid:
        pos = (close - mid) / (upper - mid)
        return 65.0 + pos * 10   # 65~75
    if close > lower:
        pos = (close - lower) / (mid - lower)
        return 30.0 + pos * 15   # 30~45
    return 15.0


def _score_volume(vol: float, vol_ma: float, is_bullish: bool) -> float:
    """
    量價配合評分（趨勢追蹤版）
    - 漲 + 量增 = 好（有資金推動）
    - 漲 + 量縮 = 差（動能不足）
    - 跌 + 量增 = 差（賣壓湧入）
    - 跌 + 量縮 = 中性（正常回調）
    """
    if vol_ma == 0:
        return 50.0
    r = vol / vol_ma

    if is_bullish:
        if r >= 2.0:   return 95.0
        if r >= 1.5:   return 85.0
        if r >= 1.0:   return 70.0
        if r >= 0.7:   return 45.0
        return 30.0
    else:
        if r >= 2.0:   return 15.0
        if r >= 1.5:   return 25.0
        if r >= 1.0:   return 40.0
        if r >= 0.7:   return 60.0
        return 70.0


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
    prev_close = float(close.iloc[-2]) if len(close) >= 2 else current
    is_bullish = current >= prev_close

    # 權重：MACD 30% + MA 25% + RSI 20% + Vol 15% + BB 10%
    weights = {"macd": 0.30, "ma": 0.25, "rsi": 0.20, "vol": 0.15, "bb": 0.10}
    sub = {
        "rsi":  _score_rsi(rsi),
        "macd": _score_macd(macd_val, macd_sig, macd_hist, macd_hist_prev),
        "ma":   _score_ma(current, ma5, ma20, ma60),
        "bb":   _score_bb(current, bb_upper, bb_lower),
        "vol":  _score_volume(vol_latest, vol_ma, is_bullish),
    }
    total = sum(sub[k] * weights[k] for k in sub)

    # 訊號文字
    signals = []
    if rsi > 70:
        signals.append(f"RSI {rsi:.1f} 動量強勁")
    elif rsi > 50:
        signals.append(f"RSI {rsi:.1f} 動量健康")
    elif rsi > 30:
        signals.append(f"RSI {rsi:.1f} 動量偏弱")
    else:
        signals.append(f"RSI {rsi:.1f} 極度弱勢")

    if macd_val > macd_sig:
        extra = "柱體放大" if macd_hist > macd_hist_prev else "柱體收斂"
        signals.append(f"MACD 金叉（{extra}）")
    else:
        signals.append("MACD 死叉")

    if current > ma5 > ma20:
        signals.append("均線多頭排列")
    elif current < ma5 < ma20:
        signals.append("均線空頭排列")

    if current > bb_upper:
        signals.append("突破布林上軌（強勢動能）")
    elif current < bb_lower:
        signals.append("跌破布林下軌（弱勢）")

    vol_ratio = vol_latest / vol_ma if vol_ma > 0 else 0
    vol_dir = "漲" if is_bullish else "跌"
    if vol_ratio >= 1.5:
        signals.append(f"帶量{vol_dir} {vol_ratio:.1f}x 均量")
    elif vol_ratio < 0.7:
        signals.append(f"縮量{vol_dir} {vol_ratio:.1f}x 均量")
    else:
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
