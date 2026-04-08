"""
Decision v2 — 進場建議生成

整合 SMC 全模組結果 → 產生具體的進場/停損/目標價位。
"""

from __future__ import annotations

from ...schemas.smc import (
    SmcResult,
    TrendDirection,
    FibZone,
    OrderBlock,
)
from ...schemas.decision import EntryPlan, SentimentGate, MtfGate
from .sentiment_gate import evaluate_sentiment
from .mtf_gate import evaluate_mtf
from .position_sizer import calculate_position
from ..smc.helpers import get_current_atr


def generate_entry_plan(
    smc: SmcResult,
    current_price: float,
    closes: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    sentiment_score: float | None = None,
    monthly_trend: TrendDirection = TrendDirection.INSUFFICIENT,
    weekly_trend: TrendDirection = TrendDirection.INSUFFICIENT,
) -> EntryPlan:
    """
    生成完整進場計畫。

    smc: 日線的 SmcResult
    current_price: 當前價格
    sentiment_score: 情緒分 0-100（可選）
    monthly_trend / weekly_trend: HTF 趨勢（可選，如果有跑 MTF）
    """
    warnings: list[str] = []

    # ── 1. 結構檢查（鐵律：下降結構不買）──
    if smc.structure.trend in (TrendDirection.DOWN, TrendDirection.WEAK_DOWN):
        return EntryPlan(
            ticker=smc.ticker,
            recommendation="不推薦",
            action="不操作",
            current_price=current_price,
            conditions_detail={"smc_structure": False},
            warnings=["下降結構，禁止做多"],
        )

    # ── 2. 情緒紅綠燈 ──
    sentiment = evaluate_sentiment(sentiment_score, smc.fibonacci.current_zone)

    # ── 3. MTF 決策矩陣 ──
    mtf = evaluate_mtf(monthly_trend, weekly_trend, smc.structure.trend)

    if mtf.max_position_tier == "none":
        return EntryPlan(
            ticker=smc.ticker,
            recommendation="不推薦",
            action="不操作",
            current_price=current_price,
            sentiment=sentiment,
            mtf=mtf,
            conditions_detail={"smc_structure": True, "mtf_allowed": False},
            warnings=[mtf.action],
        )

    # ── 4. 找進場價（優先級：OB → FVG → Swing Low → OTE）──
    entry_price, entry_source = _find_entry(smc, current_price)

    # ── 5. 找停損價（用 ATR buffer，不是固定百分比）──
    current_atr = get_current_atr(highs, lows, closes) if closes and highs and lows else None
    stop_price, stop_source = _find_stop(smc, entry_price, current_atr)

    # ── 6. 找目標價（找不到用 entry*1.1 估算）──
    target_price, target_source = _find_target(smc, current_price)
    if target_price is None and entry_price is not None:
        target_price = round(entry_price * 1.1, 2)
        target_source = "estimated"

    # ── 7. R:R 計算 ──
    rr_ratio = None
    if entry_price and stop_price and target_price and entry_price > stop_price:
        risk = entry_price - stop_price
        reward = target_price - entry_price
        if risk > 0:
            rr_ratio = round(reward / risk, 2)

    # ── 8. 條件計數 ──
    conditions = {
        "smc_structure": smc.structure.trend in (TrendDirection.UP, TrendDirection.WEAK_UP),
        "entry_quality": entry_price is not None and stop_price is not None,
        "rr_ratio": rr_ratio is not None and rr_ratio >= 2.0,
        "sentiment_ok": sentiment.signal in ("green", "neutral"),
    }
    conditions_met = sum(conditions.values())

    # ── 9. 倉位計算 ──
    tier, pct, recommendation = calculate_position(
        conditions_met,
        mtf.max_position_tier,
        mtf.max_position_pct,
        sentiment.signal,
    )

    # ── 10. 操作建議 ──
    action = _determine_action(
        entry_price, current_price, tier, smc.structure.trend,
    )

    # 現價距進場價距離
    distance_pct = None
    if entry_price and current_price > 0:
        distance_pct = round((current_price - entry_price) / entry_price * 100, 2)

    if not entry_price:
        warnings.append("無有效進場價位")
    if not stop_price:
        warnings.append("無有效停損價位")
    if not target_price:
        warnings.append("無有效目標價位")
    if rr_ratio and rr_ratio < 1.5:
        warnings.append(f"R:R 偏低 ({rr_ratio})")

    return EntryPlan(
        ticker=smc.ticker,
        recommendation=recommendation,
        action=action,
        entry_price=entry_price,
        entry_source=entry_source,
        stop_price=stop_price,
        stop_source=stop_source,
        target_price=target_price,
        target_source=target_source,
        rr_ratio=rr_ratio,
        position_tier=tier,
        max_position_pct=pct,
        conditions_met=conditions_met,
        conditions_detail=conditions,
        sentiment=sentiment,
        mtf=mtf,
        current_price=current_price,
        distance_to_entry_pct=distance_pct,
        warnings=warnings,
    )


def _find_entry(
    smc: SmcResult,
    current_price: float,
) -> tuple[float | None, str]:
    """
    找進場價位（優先級）：
    1. Bullish OB 上緣（score 最高的）
    2. Bullish FVG CE 中線
    3. 最近 Swing Low
    4. Fibonacci OTE 區間中點
    """
    # 1. Bullish OB（score >= 3.0 才有效）
    active_obs = [
        ob for ob in smc.order_blocks.active_bullish
        if ob.top < current_price and ob.score >= 3.0
    ]
    if active_obs:
        best_ob = max(active_obs, key=lambda o: o.score)
        return round(best_ob.top, 2), f"OB({best_ob.score})"

    # 2. Bullish FVG CE
    active_fvgs = [
        f for f in smc.fvg.active
        if f.type == "bullish" and f.ce < current_price
    ]
    if active_fvgs:
        best_fvg = max(active_fvgs, key=lambda f: f.freshness)
        return round(best_fvg.ce, 2), f"FVG({best_fvg.grade.value})"

    # 3. 最近 Swing Low
    recent_lows = [
        sl for sl in smc.structure.swing_lows
        if sl.price < current_price
    ]
    if recent_lows:
        nearest = max(recent_lows, key=lambda s: s.price)  # 離現價最近的
        return round(nearest.price, 2), "SwingLow"

    # 4. Fibonacci OTE
    if smc.fibonacci.valid:
        ote_mid = smc.fibonacci.levels.get("0.705")
        if ote_mid and ote_mid < current_price:
            return round(ote_mid, 2), "OTE"

    return None, ""


def _find_stop(
    smc: SmcResult,
    entry_price: float | None,
    current_atr: float | None = None,
) -> tuple[float | None, str]:
    """
    找停損價位（優先級）：
    1. OB 底部 - ATR buffer
    2. FVG 底部
    3. 最近 Swing Low - ATR buffer

    STRATEGY.md §7: stop = structure - ATR * 0.15
    """
    if entry_price is None:
        return None, ""

    # ATR-based buffer per STRATEGY.md §7; fallback to 1.5% if ATR unavailable
    buffer = current_atr * 0.15 if current_atr and current_atr > 0 else entry_price * 0.015

    # 1. OB 底部
    obs_below = [
        ob for ob in smc.order_blocks.active_bullish
        if ob.bottom < entry_price
    ]
    if obs_below:
        best_ob = max(obs_below, key=lambda o: o.score)
        stop = best_ob.bottom - buffer
        if stop > 0 and entry_price - stop > buffer:
            return round(stop, 2), "OB_bottom"

    # 2. FVG 底部
    fvgs_below = [
        f for f in smc.fvg.active
        if f.type == "bullish" and f.bottom < entry_price
    ]
    if fvgs_below:
        best = max(fvgs_below, key=lambda f: f.freshness)
        stop = best.bottom - buffer * 0.5
        if stop > 0:
            return round(stop, 2), "FVG_bottom"

    # 3. Swing Low
    lows_below = [
        sl for sl in smc.structure.swing_lows
        if sl.price < entry_price
    ]
    if lows_below:
        # 取離 entry 最近但在下方的
        nearest = max(lows_below, key=lambda s: s.price)
        stop = nearest.price - buffer
        if stop > 0:
            return round(stop, 2), "SwingLow"

    return None, ""


def _find_target(
    smc: SmcResult,
    current_price: float,
) -> tuple[float | None, str]:
    """
    找目標價位（優先級）：
    1. Bearish OB 底部（供應區下緣）
    2. BSL（EQH）最高分的
    3. Swing High
    """
    # 1. Bearish OB
    bear_obs = [
        ob for ob in smc.order_blocks.active_bearish
        if ob.bottom > current_price
    ]
    if bear_obs:
        nearest = min(bear_obs, key=lambda o: o.bottom)
        return round(nearest.bottom, 2), "BearOB"

    # 2. BSL (未被 swept 的)
    unswept_bsl = [
        l for l in smc.liquidity.bsl
        if not l.swept and l.price > current_price
    ]
    if unswept_bsl:
        best = max(unswept_bsl, key=lambda l: l.liq_score)
        return round(best.price, 2), f"BSL(score={best.liq_score:.2f})"

    # 3. Swing High
    highs_above = [
        sh for sh in smc.structure.swing_highs
        if sh.price > current_price
    ]
    if highs_above:
        nearest = min(highs_above, key=lambda s: s.price)
        return round(nearest.price, 2), "SwingHigh"

    return None, ""


def _determine_action(
    entry_price: float | None,
    current_price: float,
    tier: str,
    trend: TrendDirection,
) -> str:
    """決定操作建議。"""
    if tier == "none":
        return "不操作"

    if entry_price is None:
        return "觀望"

    distance_pct = (current_price - entry_price) / entry_price * 100 if entry_price > 0 else 0

    # 現價在進場價附近（±3%）
    if -1.0 <= distance_pct <= 3.0:
        return "買入"

    # 現價遠高於進場價（>5%）→ 等回調
    if distance_pct > 5.0:
        return "等回調"

    # 現價略高於進場價（3-5%）
    if distance_pct > 3.0:
        return "等回調"

    # 現價低於進場價 → 已跌破進場區，觀望
    if distance_pct < -1.0:
        return "觀望"

    return "觀望"
