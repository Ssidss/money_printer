"""
Stock Grouper — 依 ATR 波動度 + 市場自動分群

Groups:
  US_高波動, US_穩定大型, US_低波動, TW_權值, TW_中小型, ETF

穩定性規則:
  - 回測時 groups 在 start_date 固定，整段不變
  - 實戰時每月底更新一次
  - hysteresis ±10%: ATR 需超過閾值才跳群
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import date


# ── ATR 閾值定義 ──────────────────────────────────────────────────────────────

# ATR%（= ATR / Close * 100）分界
US_HIGH_VOL_THRESHOLD = 3.0    # > 3% → 高波動
US_LOW_VOL_THRESHOLD = 1.2     # < 1.2% → 低波動
TW_HIGH_VOL_THRESHOLD = 2.5    # 台股波動閾值稍低
TW_LOW_VOL_THRESHOLD = 1.0

# hysteresis ±10%
HYSTERESIS_PCT = 0.10

ETF_TICKERS = {
    "0050", "0056", "00878", "00713", "00919", "00929",
    "SPY", "QQQ", "VOO", "VTI", "ARKK", "SOXX",
}


def compute_atr_pct(df: pd.DataFrame, period: int = 14) -> float:
    """計算 ATR%（ATR / Close * 100），取最近 period 天平均"""
    if len(df) < period + 1:
        return 0.0

    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values

    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1]),
        ),
    )

    if len(tr) < period:
        return 0.0

    atr = np.mean(tr[-period:])
    last_close = close[-1]
    if last_close <= 0:
        return 0.0

    return (atr / last_close) * 100


def assign_group(
    ticker: str,
    market: str,
    atr_pct: float,
    current_group: str | None = None,
) -> str:
    """
    分配股票到群組。

    Args:
        ticker: 股票代碼
        market: "US" | "TW"
        atr_pct: ATR%
        current_group: 現有群組（用於 hysteresis 判斷）
    """
    # ETF 直接歸類
    if ticker in ETF_TICKERS:
        return "ETF"

    if market == "TW":
        high_th = TW_HIGH_VOL_THRESHOLD
        low_th = TW_LOW_VOL_THRESHOLD
        high_group = "TW_中小型"     # 台股高波動通常是中小型
        mid_group = "TW_權值"
        low_group = "TW_權值"        # 台股低波動也歸權值
    else:
        high_th = US_HIGH_VOL_THRESHOLD
        low_th = US_LOW_VOL_THRESHOLD
        high_group = "US_高波動"
        mid_group = "US_穩定大型"
        low_group = "US_低波動"

    # hysteresis: 如果有現有群組，需要超過閾值 ±10% 才跳群
    if current_group:
        h = HYSTERESIS_PCT
        if current_group == high_group:
            # 要從高波動降到中間，ATR 需 < 閾值 * (1 - h)
            if atr_pct >= high_th * (1 - h):
                return high_group
        elif current_group == low_group:
            if atr_pct <= low_th * (1 + h):
                return low_group

    # 正常分群
    if atr_pct >= high_th:
        return high_group
    elif atr_pct <= low_th:
        return low_group
    else:
        return mid_group


def assign_groups_batch(
    stocks: list[dict],
    price_data: dict[str, pd.DataFrame],
    anchor_date: date | None = None,
) -> dict[str, str]:
    """
    批次分群。回測時傳 anchor_date = start_date，只用 anchor_date 前的資料。

    Args:
        stocks: [{"ticker": "AAPL", "market": "US"}, ...]
        price_data: {ticker: DataFrame(Date, Open, High, Low, Close, Volume)}
        anchor_date: 用哪天的 ATR 來分群（None = 用最新）

    Returns:
        {"AAPL": "US_穩定大型", "NVDA": "US_高波動", ...}
    """
    result = {}
    for s in stocks:
        ticker = s["ticker"]
        market = s.get("market", "US")
        df = price_data.get(ticker)

        if df is None or len(df) < 20:
            result[ticker] = "ETF" if ticker in ETF_TICKERS else f"{market}_穩定大型" if market == "US" else "TW_權值"
            continue

        if anchor_date is not None:
            # index 可能是 date 或 datetime，統一比較
            df = df[df.index <= anchor_date]

        atr_pct = compute_atr_pct(df)
        result[ticker] = assign_group(ticker, market, atr_pct)

    return result
