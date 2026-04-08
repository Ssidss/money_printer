"""
Decision v2 — 多時間框架決策矩陣

根據月線/週線/日線的趨勢組合，決定允許的最大倉位和操作方向。
"""

from __future__ import annotations

from ...schemas.decision import MtfGate
from ...schemas.smc import TrendDirection


# 趨勢簡化：UP/WEAK_UP → "up", DOWN/WEAK_DOWN → "down", 其他 → "range"
def _simplify_trend(trend: TrendDirection) -> str:
    if trend in (TrendDirection.UP, TrendDirection.WEAK_UP):
        return "up"
    elif trend in (TrendDirection.DOWN, TrendDirection.WEAK_DOWN):
        return "down"
    return "range"


def evaluate_mtf(
    monthly_trend: TrendDirection,
    weekly_trend: TrendDirection,
    daily_trend: TrendDirection,
) -> MtfGate:
    """
    多時間框架決策矩陣（做多方向）。

    回傳允許的最大倉位等級和操作建議。
    """
    m = _simplify_trend(monthly_trend)
    w = _simplify_trend(weekly_trend)
    d = _simplify_trend(daily_trend)

    # ── 鐵律：月線下降 → 全面禁止做多 ──
    if m == "down":
        return MtfGate(
            monthly_trend=m, weekly_trend=w, daily_trend=d,
            action="禁止做多（月線下降）",
            max_position_tier="none",
            max_position_pct=0.0,
        )

    # ── 週線下降 → 禁止做多 ──
    if w == "down":
        return MtfGate(
            monthly_trend=m, weekly_trend=w, daily_trend=d,
            action="禁止做多（週線下降）",
            max_position_tier="none",
            max_position_pct=0.0,
        )

    # ── 月↑ 週↑ 日↑ → 核心持倉 ──
    if m == "up" and w == "up" and d == "up":
        return MtfGate(
            monthly_trend=m, weekly_trend=w, daily_trend=d,
            action="正常做多",
            max_position_tier="核心",
            max_position_pct=20.0,
        )

    # ── 月↑ 週↑ 日─ → 等日線 BOS 確認 ──
    if m == "up" and w == "up" and d == "range":
        return MtfGate(
            monthly_trend=m, weekly_trend=w, daily_trend=d,
            action="等日線 BOS 確認再進",
            max_position_tier="標準",
            max_position_pct=12.0,
        )

    # ── 月↑ 週─ 日↑ → 降級倉位 ──
    if m == "up" and w == "range" and d == "up":
        return MtfGate(
            monthly_trend=m, weekly_trend=w, daily_trend=d,
            action="可做但降級倉位",
            max_position_tier="標準",
            max_position_pct=12.0,
        )

    # ── 月↑ 週─ 日─ → 等週線突破 ──
    if m == "up" and w == "range" and d == "range":
        return MtfGate(
            monthly_trend=m, weekly_trend=w, daily_trend=d,
            action="等週線突破",
            max_position_tier="探索",
            max_position_pct=5.0,
        )

    # ── 月─ 週↑ 日↑ → 可做但降級 ──
    if m == "range" and w == "up" and d == "up":
        return MtfGate(
            monthly_trend=m, weekly_trend=w, daily_trend=d,
            action="可做但降級",
            max_position_tier="標準",
            max_position_pct=12.0,
        )

    # ── 月─ 週─ 日↑ → 最多探索倉 ──
    if m == "range" and w == "range" and d == "up":
        return MtfGate(
            monthly_trend=m, weekly_trend=w, daily_trend=d,
            action="最多探索倉",
            max_position_tier="探索",
            max_position_pct=5.0,
        )

    # ── 其餘組合 → 觀望 ──
    return MtfGate(
        monthly_trend=m, weekly_trend=w, daily_trend=d,
        action="觀望",
        max_position_tier="none",
        max_position_pct=0.0,
    )
