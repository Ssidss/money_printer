"""
SMC v2 — 市場結構分析

Swing Points（含容差+去重+flat top/bottom）
+ 趨勢判斷（硬規則+弱趨勢）
+ 結構事件 BOS / CHoCH / MSS
"""

from __future__ import annotations

import numpy as np

from ...schemas.smc import (
    StructureResult,
    StructureEvent,
    StructureEventType,
    SwingPoint,
    SwingType,
    TrendDirection,
)
from .config import SmcConfig, DEFAULT_CONFIG
from .helpers import (
    compute_atr,
    get_swing_tolerance,
    get_swing_n,
    compute_volume_sma,
)


# ═══════════════════════════════════════════════════════════════
# Swing Point 偵測
# ═══════════════════════════════════════════════════════════════

def detect_swing_points(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    dates: np.ndarray,
    atr: np.ndarray,
    timeframe: str = "daily",
    market: str = "US",
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> tuple[list[SwingPoint], list[SwingPoint]]:
    """
    偵測 Swing Highs 和 Swing Lows。

    回傳 (swing_highs, swing_lows)，按 index 排序。
    """
    n = len(highs)
    N = get_swing_n(timeframe, cfg)

    if n < N * 2 + 1:
        return [], []

    # 取最後有效 ATR 做為 tolerance 基準
    last_atr = 0.0
    for i in range(n - 1, -1, -1):
        if not np.isnan(atr[i]):
            last_atr = atr[i]
            break
    last_close = closes[-1] if n > 0 else 1.0
    tolerance = get_swing_tolerance(last_atr, last_close, market, cfg)

    raw_highs = _find_raw_swing_highs(highs, dates, N, tolerance)
    raw_lows = _find_raw_swing_lows(lows, dates, N, tolerance)

    # 去重：同類型間距 < N 的只保留極值
    swing_highs = _dedup_swings(raw_highs, N, is_high=True)
    swing_lows = _dedup_swings(raw_lows, N, is_high=False)

    return swing_highs, swing_lows


def _find_raw_swing_highs(
    highs: np.ndarray,
    dates: np.ndarray,
    N: int,
    tolerance: float,
) -> list[SwingPoint]:
    """找原始 Swing Highs（含 flat top 處理）。"""
    n = len(highs)
    results = []
    i = N

    while i < n - N:
        window_left = highs[max(0, i - N):i]
        window_right = highs[i + 1:min(n, i + N + 1)]

        is_swing = (
            highs[i] >= np.max(window_left) - tolerance
            and highs[i] >= np.max(window_right) - tolerance
            and highs[i] == np.max(np.concatenate([window_left, [highs[i]], window_right]))
        )

        if is_swing:
            # Flat top 處理：找連續 high 差距 < tolerance 的區段
            flat_end = i
            while flat_end + 1 < n and abs(highs[flat_end + 1] - highs[i]) < tolerance:
                flat_end += 1

            # 取中間那根的 index，取 max(high) 作為 price
            mid = (i + flat_end) // 2
            price = float(np.max(highs[i:flat_end + 1]))

            results.append(SwingPoint(
                index=mid,
                date=str(dates[mid]),
                price=price,
                type=SwingType.UNKNOWN,  # 後面再標記 HH/LH
                is_high=True,
            ))
            i = flat_end + N  # 跳過 flat 區段
        else:
            i += 1

    return results


def _find_raw_swing_lows(
    lows: np.ndarray,
    dates: np.ndarray,
    N: int,
    tolerance: float,
) -> list[SwingPoint]:
    """找原始 Swing Lows（含 flat bottom 處理）。"""
    n = len(lows)
    results = []
    i = N

    while i < n - N:
        window_left = lows[max(0, i - N):i]
        window_right = lows[i + 1:min(n, i + N + 1)]

        is_swing = (
            lows[i] <= np.min(window_left) + tolerance
            and lows[i] <= np.min(window_right) + tolerance
            and lows[i] == np.min(np.concatenate([window_left, [lows[i]], window_right]))
        )

        if is_swing:
            flat_end = i
            while flat_end + 1 < n and abs(lows[flat_end + 1] - lows[i]) < tolerance:
                flat_end += 1

            mid = (i + flat_end) // 2
            price = float(np.min(lows[i:flat_end + 1]))

            results.append(SwingPoint(
                index=mid,
                date=str(dates[mid]),
                price=price,
                type=SwingType.UNKNOWN,
                is_high=False,
            ))
            i = flat_end + N
        else:
            i += 1

    return results


def _dedup_swings(
    points: list[SwingPoint],
    min_gap: int,
    is_high: bool,
) -> list[SwingPoint]:
    """去重：兩個同類型 swing 間距 < min_gap → 只保留極值。"""
    if not points:
        return []

    result: list[SwingPoint] = [points[0]]
    for p in points[1:]:
        if p.index - result[-1].index < min_gap:
            # 太近，保留更極端的
            if is_high:
                if p.price > result[-1].price:
                    result[-1] = p
            else:
                if p.price < result[-1].price:
                    result[-1] = p
        else:
            result.append(p)

    return result


# ═══════════════════════════════════════════════════════════════
# 標記 HH/HL/LH/LL
# ═══════════════════════════════════════════════════════════════

def label_swing_types(
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
) -> tuple[list[SwingPoint], list[SwingPoint]]:
    """標記每個 swing point 的類型 (HH/LH, HL/LL)。"""
    # 標記 highs
    for i, sh in enumerate(swing_highs):
        if i == 0:
            sh.type = SwingType.UNKNOWN
        else:
            prev = swing_highs[i - 1]
            sh.type = SwingType.HH if sh.price > prev.price else SwingType.LH

    # 標記 lows
    for i, sl in enumerate(swing_lows):
        if i == 0:
            sl.type = SwingType.UNKNOWN
        else:
            prev = swing_lows[i - 1]
            sl.type = SwingType.HL if sl.price > prev.price else SwingType.LL

    return swing_highs, swing_lows


# ═══════════════════════════════════════════════════════════════
# 趨勢判斷
# ═══════════════════════════════════════════════════════════════

def determine_trend(
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
    latest_close: float,
    events: list[StructureEvent],
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> tuple[TrendDirection, str, str]:
    """
    判斷趨勢方向。

    回傳 (trend, hh_hl_ratio, ll_lh_ratio)
    """
    n_groups = cfg.trend_swing_groups
    min_consistent = cfg.trend_min_consistent

    # 需要至少 n_groups 個 swing high + n_groups 個 swing low
    recent_highs = swing_highs[-n_groups:] if len(swing_highs) >= n_groups else swing_highs
    recent_lows = swing_lows[-n_groups:] if len(swing_lows) >= n_groups else swing_lows

    if len(recent_highs) < 2 or len(recent_lows) < 2:
        return TrendDirection.INSUFFICIENT, "0/0", "0/0"

    # 計算 HH 和 HL 的數量
    hh_count = sum(1 for sh in recent_highs if sh.type == SwingType.HH)
    hl_count = sum(1 for sl in recent_lows if sl.type == SwingType.HL)
    lh_count = sum(1 for sh in recent_highs if sh.type == SwingType.LH)
    ll_count = sum(1 for sl in recent_lows if sl.type == SwingType.LL)

    total_h = len(recent_highs) - 1  # 第一個是 UNKNOWN
    total_l = len(recent_lows) - 1

    hh_hl_ratio = f"{hh_count}/{total_h}" if total_h > 0 else "0/0"
    ll_lh_ratio = f"{ll_count}/{total_l}" if total_l > 0 else "0/0"

    # 最近結構事件
    latest_bullish_bos = _has_recent_event(events, "BOS", "bullish")
    latest_bearish_bos = _has_recent_event(events, "BOS", "bearish")
    has_bearish_choch_mss = _has_recent_event(events, "CHoCH", "bearish") or _has_recent_event(events, "MSS", "bearish")
    has_bullish_choch_mss = _has_recent_event(events, "CHoCH", "bullish") or _has_recent_event(events, "MSS", "bullish")

    # 最近的 HL 和 LH
    latest_hl = _get_latest_of_type(recent_lows, SwingType.HL)
    latest_lh = _get_latest_of_type(recent_highs, SwingType.LH)

    # 上升趨勢（4 條件全滿足）
    if (hh_count >= min_consistent
            and hl_count >= min_consistent
            and latest_bullish_bos
            and latest_hl is not None
            and latest_close > latest_hl.price):
        return TrendDirection.UP, hh_hl_ratio, ll_lh_ratio

    # 下降趨勢
    if (lh_count >= min_consistent
            and ll_count >= min_consistent
            and latest_bearish_bos
            and latest_lh is not None
            and latest_close < latest_lh.price):
        return TrendDirection.DOWN, hh_hl_ratio, ll_lh_ratio

    # 弱上升：HL 持續上升但 HH 不足
    if (hl_count >= min_consistent
            and hh_count < min_consistent
            and latest_hl is not None
            and latest_close > latest_hl.price
            and not has_bearish_choch_mss):
        return TrendDirection.WEAK_UP, hh_hl_ratio, ll_lh_ratio

    # 弱下降：LL 持續下降但 LH 不足
    if (ll_count >= min_consistent
            and lh_count < min_consistent
            and latest_lh is not None
            and latest_close < latest_lh.price
            and not has_bullish_choch_mss):
        return TrendDirection.WEAK_DOWN, hh_hl_ratio, ll_lh_ratio

    return TrendDirection.RANGING, hh_hl_ratio, ll_lh_ratio


def _has_recent_event(
    events: list[StructureEvent],
    event_type: str,
    direction: str,
) -> bool:
    """檢查最近的事件是否包含指定類型。"""
    for e in reversed(events):
        if e.type.value == event_type and e.direction == direction:
            return True
        # 如果遇到反向事件就停
        if e.direction != direction:
            return False
    return False


def _get_latest_of_type(
    points: list[SwingPoint],
    swing_type: SwingType,
) -> SwingPoint | None:
    """取最近的指定類型 swing point。"""
    for p in reversed(points):
        if p.type == swing_type:
            return p
    return None


# ═══════════════════════════════════════════════════════════════
# 結構事件偵測 (BOS / CHoCH / MSS)
# ═══════════════════════════════════════════════════════════════

def detect_structure_events(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    opens: np.ndarray,
    dates: np.ndarray,
    volumes: np.ndarray,
    atr: np.ndarray,
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
    timeframe: str = "daily",
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> list[StructureEvent]:
    """
    偵測 BOS / CHoCH / MSS 結構事件。

    邏輯：遍歷所有 bar，檢查是否突破了前一個 swing point。
    """
    events: list[StructureEvent] = []
    n = len(closes)

    if not swing_highs or not swing_lows:
        return events

    # 合併所有 swing points 並按 index 排序
    all_swings = sorted(swing_highs + swing_lows, key=lambda s: s.index)

    # 追蹤當前方向（基於最近的結構事件）
    current_direction = "neutral"

    # 追蹤待確認的 CHoCH（等待 MSS 升級）
    pending_choch: StructureEvent | None = None
    choch_bar_idx: int = -1

    # 追蹤「當前方向下」最近的未被突破的 swing point
    # 方向改變時重置，解決 broken_indices 永不清除的問題
    last_bullish_break_sh: int = -1  # 最近被 bullish 突破的 SH index
    last_bearish_break_sl: int = -1  # 最近被 bearish 突破的 SL index

    # MSS 確認窗口
    confirm_window = {
        "daily": cfg.mss_confirm_window_daily,
        "weekly": cfg.mss_confirm_window_weekly,
        "monthly": cfg.mss_confirm_window_monthly,
    }.get(timeframe, cfg.mss_confirm_window_daily)

    # 遍歷每根 bar（從第一個 swing point 之後開始）
    start_idx = all_swings[0].index + 1 if all_swings else 0

    # ATR fallback: 找第一個有效的 ATR
    fallback_atr = 0.0
    for v in atr:
        if not np.isnan(v):
            fallback_atr = v
            break

    for bar_idx in range(start_idx, n):
        bar_close = closes[bar_idx]
        bar_body = abs(closes[bar_idx] - opens[bar_idx])
        bar_atr = atr[bar_idx] if not np.isnan(atr[bar_idx]) else fallback_atr
        if bar_atr <= 0:
            continue
        fallback_atr = bar_atr  # 更新 fallback

        # 檢查 pending CHoCH 是否該升級為 MSS
        if pending_choch is not None:
            bars_since = bar_idx - choch_bar_idx
            if bars_since <= confirm_window:
                if bar_body > cfg.mss_min_displacement_atr * bar_atr:
                    has_fvg = _check_fvg_at_bar(highs, lows, bar_idx)
                    if has_fvg:
                        mss = StructureEvent(
                            type=StructureEventType.MSS,
                            direction=pending_choch.direction,
                            date=str(dates[bar_idx]),
                            price=pending_choch.price,
                            break_bar_index=bar_idx,
                            displacement=round(bar_body / bar_atr, 2),
                        )
                        # 替換 CHoCH
                        if events and events[-1] == pending_choch:
                            events[-1] = mss
                        else:
                            events.append(mss)
                        current_direction = pending_choch.direction
                        pending_choch = None
                        continue
            else:
                # 窗口過了，CHoCH 保留為 CHoCH（不丟棄），方向更新
                current_direction = pending_choch.direction
                pending_choch = None

        # 找 bar_idx 之前最近的 swing high 和 swing low
        prev_sh = _get_prev_swing(swing_highs, bar_idx)
        prev_sl = _get_prev_swing(swing_lows, bar_idx)

        if prev_sh is None or prev_sl is None:
            continue

        # 避免同一根 bar 同時觸發上下突破：只處理一個方向
        broke_high = (prev_sh.index > last_bullish_break_sh
                      and bar_close > prev_sh.price)
        broke_low = (prev_sl.index > last_bearish_break_sl
                     and bar_close < prev_sl.price)

        # 如果兩個都突破了，取價格移動更大的那邊
        if broke_high and broke_low:
            move_up = bar_close - prev_sh.price
            move_down = prev_sl.price - bar_close
            if move_up >= move_down:
                broke_low = False
            else:
                broke_high = False

        # --- 向上突破 Swing High ---
        if broke_high:
            last_bullish_break_sh = prev_sh.index

            if current_direction in ("bullish", "neutral"):
                event = StructureEvent(
                    type=StructureEventType.BOS,
                    direction="bullish",
                    date=str(dates[bar_idx]),
                    price=prev_sh.price,
                    break_bar_index=bar_idx,
                )
                events.append(event)
                current_direction = "bullish"
            else:
                # 反向突破 → CHoCH or MSS
                is_choch = bar_body <= cfg.choch_max_body_atr * bar_atr
                if is_choch:
                    event = StructureEvent(
                        type=StructureEventType.CHOCH,
                        direction="bullish",
                        date=str(dates[bar_idx]),
                        price=prev_sh.price,
                        break_bar_index=bar_idx,
                    )
                    events.append(event)
                    pending_choch = event
                    choch_bar_idx = bar_idx
                else:
                    has_fvg = _check_fvg_at_bar(highs, lows, bar_idx)
                    event = StructureEvent(
                        type=StructureEventType.MSS if has_fvg else StructureEventType.CHOCH,
                        direction="bullish",
                        date=str(dates[bar_idx]),
                        price=prev_sh.price,
                        break_bar_index=bar_idx,
                        displacement=round(bar_body / bar_atr, 2) if has_fvg else None,
                    )
                    events.append(event)
                    if has_fvg:
                        current_direction = "bullish"
                        pending_choch = None
                    else:
                        pending_choch = event
                        choch_bar_idx = bar_idx

        # --- 向下突破 Swing Low ---
        elif broke_low:
            last_bearish_break_sl = prev_sl.index

            if current_direction in ("bearish", "neutral"):
                event = StructureEvent(
                    type=StructureEventType.BOS,
                    direction="bearish",
                    date=str(dates[bar_idx]),
                    price=prev_sl.price,
                    break_bar_index=bar_idx,
                )
                events.append(event)
                current_direction = "bearish"
            else:
                is_choch = bar_body <= cfg.choch_max_body_atr * bar_atr
                if is_choch:
                    event = StructureEvent(
                        type=StructureEventType.CHOCH,
                        direction="bearish",
                        date=str(dates[bar_idx]),
                        price=prev_sl.price,
                        break_bar_index=bar_idx,
                    )
                    events.append(event)
                    pending_choch = event
                    choch_bar_idx = bar_idx
                else:
                    has_fvg = _check_fvg_at_bar(highs, lows, bar_idx)
                    event = StructureEvent(
                        type=StructureEventType.MSS if has_fvg else StructureEventType.CHOCH,
                        direction="bearish",
                        date=str(dates[bar_idx]),
                        price=prev_sl.price,
                        break_bar_index=bar_idx,
                        displacement=round(bar_body / bar_atr, 2) if has_fvg else None,
                    )
                    events.append(event)
                    if has_fvg:
                        current_direction = "bearish"
                        pending_choch = None
                    else:
                        pending_choch = event
                        choch_bar_idx = bar_idx

    return events


def _get_prev_swing(points: list[SwingPoint], bar_idx: int) -> SwingPoint | None:
    """取 bar_idx 之前最近的 swing point。"""
    result = None
    for p in points:
        if p.index < bar_idx:
            result = p
        else:
            break
    return result


def _check_fvg_at_bar(
    highs: np.ndarray,
    lows: np.ndarray,
    bar_idx: int,
) -> bool:
    """檢查 bar_idx 附近是否有 FVG（簡化版，用於 MSS 確認）。"""
    n = len(highs)
    if bar_idx < 1 or bar_idx >= n - 1:
        return False

    # Bullish FVG: bar[i-1].high < bar[i+1].low
    if highs[bar_idx - 1] < lows[bar_idx + 1]:
        return True
    # Bearish FVG: bar[i-1].low > bar[i+1].high
    if lows[bar_idx - 1] > highs[bar_idx + 1]:
        return True

    return False


# ═══════════════════════════════════════════════════════════════
# 整合入口
# ═══════════════════════════════════════════════════════════════

def analyze_structure(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    opens: np.ndarray,
    dates: np.ndarray,
    volumes: np.ndarray,
    atr: np.ndarray,
    timeframe: str = "daily",
    market: str = "US",
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> StructureResult:
    """
    完整結構分析入口。

    回傳 StructureResult，包含 swing points、趨勢、結構事件。
    """
    n = len(closes)

    if n < 20:
        return StructureResult(
            trend=TrendDirection.INSUFFICIENT,
            warnings=["bars < 20, insufficient data"],
        )

    # 1. 偵測 Swing Points
    swing_highs, swing_lows = detect_swing_points(
        highs, lows, closes, dates, atr, timeframe, market, cfg
    )

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return StructureResult(
            trend=TrendDirection.INSUFFICIENT,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
        )

    # 2. 偵測結構事件
    events = detect_structure_events(
        highs, lows, closes, opens, dates, volumes, atr,
        swing_highs, swing_lows, timeframe, cfg,
    )

    # 3. 標記 HH/HL/LH/LL
    swing_highs, swing_lows = label_swing_types(swing_highs, swing_lows)

    # 4. 判斷趨勢
    latest_close = float(closes[-1])
    trend, hh_hl_ratio, ll_lh_ratio = determine_trend(
        swing_highs, swing_lows, latest_close, events, cfg,
    )

    return StructureResult(
        trend=trend,
        swing_highs=swing_highs,
        swing_lows=swing_lows,
        events=events,
        latest_event=events[-1] if events else None,
        hh_hl_ratio=hh_hl_ratio,
        ll_lh_ratio=ll_lh_ratio,
    )
