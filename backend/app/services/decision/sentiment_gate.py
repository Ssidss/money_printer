"""
Decision v2 — 情緒紅綠燈

情緒作為 counter-indicator / gatekeeper：
- 極度悲觀 + Discount 區 = 買入機會（利空出盡）
- 極度樂觀 + Premium 區 = 賣出信號（散戶接盤）
- 正常範圍 = 不影響決策
"""

from __future__ import annotations

from ...schemas.decision import SentimentGate
from ...schemas.smc import FibZone


def evaluate_sentiment(
    sentiment_score: float | None,
    fib_zone: FibZone,
) -> SentimentGate:
    """
    評估情緒信號。

    sentiment_score: 0-100（0=極度悲觀，100=極度樂觀）
    fib_zone: 目前價格所在的 Fibonacci 區域

    回傳 SentimentGate（green/yellow/red/neutral）
    """
    if sentiment_score is None:
        return SentimentGate(signal="neutral", reason="無情緒數據")

    score = sentiment_score
    in_discount = fib_zone in (FibZone.DISCOUNT, FibZone.DEEP_DISCOUNT, FibZone.OTE)
    in_premium = fib_zone in (FibZone.PREMIUM, FibZone.DEEP_PREMIUM)

    # 極度悲觀 (< 25) + Discount 區 = 綠燈（利空出盡，機構進場區）
    if score < 25 and in_discount:
        return SentimentGate(
            score=score,
            signal="green",
            reason="極度悲觀+折價區：利空出盡，機構進場機會",
        )

    # 極度樂觀 (> 80) + Premium 區 = 紅燈（散戶 FOMO，危險）
    if score > 80 and in_premium:
        return SentimentGate(
            score=score,
            signal="red",
            reason="極度樂觀+溢價區：散戶追高，風險極大",
        )

    # 偏悲觀 (25-40) + 任何合理區域 = 黃燈偏綠
    if score < 40 and in_discount:
        return SentimentGate(
            score=score,
            signal="green",
            reason="偏悲觀+折價區：情緒消化中，可進場",
        )

    # 偏樂觀 (65-80) + Premium = 黃燈
    if score > 65 and in_premium:
        return SentimentGate(
            score=score,
            signal="yellow",
            reason="偏樂觀+溢價區：注意追高風險",
        )

    # 極度樂觀但在 Discount = 可以（強勢上漲初期）
    if score > 80 and in_discount:
        return SentimentGate(
            score=score,
            signal="green",
            reason="強勢+折價區：趨勢初期",
        )

    # 極度悲觀但在 Premium = 紅燈（下跌中繼）
    if score < 25 and in_premium:
        return SentimentGate(
            score=score,
            signal="red",
            reason="極度悲觀+溢價區：下跌中繼，不要接",
        )

    # 正常範圍 = 中性
    return SentimentGate(
        score=score,
        signal="neutral",
        reason="情緒正常範圍，不影響決策",
    )
