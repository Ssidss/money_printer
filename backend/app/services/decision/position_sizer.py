"""
Decision v2 — 倉位計算

根據條件滿足數量和 MTF gate 決定倉位等級。
"""

from __future__ import annotations


def calculate_position(
    conditions_met: int,
    mtf_max_tier: str,
    mtf_max_pct: float,
    sentiment_signal: str,
) -> tuple[str, float, str]:
    """
    計算倉位等級。

    回傳 (tier, pct, recommendation)

    條件計數決定基礎推薦：
      4 條件 → 強力推薦 + 核心持倉 (15-20%)
      3 條件 → 推薦 + 標準倉位 (8-12%)
      2 條件 → 觀察 + 探索倉位 (3-5%)
      <2     → 不推薦
    """
    # 基礎推薦（由條件數量決定）
    if conditions_met >= 4:
        base_tier = "核心"
        base_pct = 18.0
        base_rec = "強力推薦"
    elif conditions_met == 3:
        base_tier = "標準"
        base_pct = 10.0
        base_rec = "推薦"
    elif conditions_met == 2:
        base_tier = "探索"
        base_pct = 4.0
        base_rec = "觀察"
    else:
        return "none", 0.0, "不推薦"

    # MTF 限制（不能超過 MTF gate 允許的最大值）
    tier_rank = {"核心": 3, "標準": 2, "探索": 1, "none": 0}
    if tier_rank.get(base_tier, 0) > tier_rank.get(mtf_max_tier, 0):
        base_tier = mtf_max_tier
        base_pct = min(base_pct, mtf_max_pct)

    if base_tier == "none":
        return "none", 0.0, "不推薦"

    base_pct = min(base_pct, mtf_max_pct)

    # 情緒調整
    if sentiment_signal == "green":
        # 情緒加速：倉位升級（但不超過 MTF 上限）
        if base_tier == "探索":
            base_tier = "標準"
            base_pct = min(8.0, mtf_max_pct)
        elif base_tier == "標準":
            base_pct = min(base_pct + 2.0, mtf_max_pct)
    elif sentiment_signal == "red":
        # 情緒警告：倉位降級
        if base_tier == "核心":
            base_tier = "標準"
            base_pct = min(10.0, mtf_max_pct)
        elif base_tier == "標準":
            base_tier = "探索"
            base_pct = min(4.0, mtf_max_pct)
        elif base_tier == "探索":
            return "none", 0.0, "不推薦"
    elif sentiment_signal == "yellow":
        # 黃燈：小幅降級
        base_pct = max(base_pct - 2.0, 3.0)

    # 推薦等級跟隨倉位
    if base_tier == "核心":
        base_rec = "強力推薦"
    elif base_tier == "標準":
        base_rec = "推薦"
    elif base_tier == "探索":
        base_rec = "觀察"

    return base_tier, base_pct, base_rec
