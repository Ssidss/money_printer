"""
SMC v2 — Order Block 偵測

嚴格 5 項驗證 + 連續型 0-10 評分 + 去重 + decay。
"""

from __future__ import annotations

import numpy as np

from ...schemas.smc import (
    OrderBlock,
    OrderBlockResult,
    StructureEvent,
    FairValueGap,
)
from .config import SmcConfig, DEFAULT_CONFIG
from .helpers import compute_volume_sma


# ═══════════════════════════════════════════════════════════════
# OB 偵測
# ═══════════════════════════════════════════════════════════════

def detect_order_blocks(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    dates: np.ndarray,
    atr: np.ndarray,
    events: list[StructureEvent],
    timeframe: str = "daily",
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> list[OrderBlock]:
    """
    偵測所有 Order Blocks。

    OB 定義：大幅度移動前的最後一根反向 K 棒。
    Bullish OB: 急拉前的最後一根陰棒
    Bearish OB: 急跌前的最後一根陽棒
    """
    n = len(closes)
    if n < 10:
        return []

    disp_atr = (cfg.ob_displacement_atr_daily if timeframe == "daily"
                else cfg.ob_displacement_atr_weekly)

    vol_sma = compute_volume_sma(volumes, cfg.vol_sma_period)
    all_obs: list[OrderBlock] = []

    # 建立結構事件的 bar_index 集合（用於 BOS/MSS 確認）
    event_bar_indices = {e.break_bar_index for e in events}

    for i in range(2, n - 1):
        cur_atr = atr[i] if not np.isnan(atr[i]) else 0
        if cur_atr <= 0:
            continue

        is_bearish_candle = closes[i] < opens[i]
        is_bullish_candle = closes[i] > opens[i]

        # ── Bullish OB：陰棒 + 後面有強力上推 ──
        if is_bearish_candle:
            ob = _try_bullish_ob(
                i, opens, highs, lows, closes, volumes, dates, atr, vol_sma,
                event_bar_indices, disp_atr, cfg,
            )
            if ob:
                all_obs.append(ob)

        # ── Bearish OB：陽棒 + 後面有強力下推 ──
        if is_bullish_candle:
            ob = _try_bearish_ob(
                i, opens, highs, lows, closes, volumes, dates, atr, vol_sma,
                event_bar_indices, disp_atr, cfg,
            )
            if ob:
                all_obs.append(ob)

    return all_obs


def _try_bullish_ob(
    i: int,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    dates: np.ndarray,
    atr: np.ndarray,
    vol_sma: np.ndarray,
    event_bar_indices: set[int],
    disp_atr: float,
    cfg: SmcConfig,
) -> OrderBlock | None:
    """嘗試在 bar i 建立 Bullish OB。"""
    n = len(closes)
    cur_atr = atr[i]

    # 找後面的 displacement candle（OB 後 1-5 根內）
    disp_idx = None
    disp_strength = 0.0
    for j in range(i + 1, min(i + 6, n)):
        body = closes[j] - opens[j]
        if body > disp_atr * cur_atr:
            disp_idx = j
            disp_strength = body / cur_atr
            break

    if disp_idx is None:
        return None

    # ── 5 項驗證 + 評分 ──
    confirmations: list[str] = []
    score = 0.0

    # 1. Displacement（必須）✅ 已通過
    score += min(3.0, max(0.0, disp_strength - 0.5))
    confirmations.append(f"displacement:{disp_strength:.1f}ATR")

    # 2. FVG 確認（必須）
    has_fvg = False
    for j in range(i + 1, min(i + cfg.ob_fvg_window + 1, n - 1)):
        if j + 1 < n and highs[j - 1] < lows[j + 1]:  # bullish FVG
            has_fvg = True
            break
    if not has_fvg:
        return None  # 必要條件不滿足
    score += 2.0
    confirmations.append("fvg_confirmed")

    # 3. 結構突破（必須）
    has_bos = False
    for j in range(i + 1, min(i + cfg.ob_bos_window + 1, n)):
        if j in event_bar_indices:
            has_bos = True
            break
    if not has_bos:
        return None  # 必要條件不滿足
    score += 2.0
    confirmations.append("structure_break")

    # 4. 流動性掃蕩（加分）
    sweep_bonus = _check_sweep_before_ob(i, opens, highs, lows, closes)
    if sweep_bonus > 0:
        score += min(1.5, sweep_bonus)
        confirmations.append(f"sweep:{sweep_bonus:.1f}")

    # 5. 成交量確認（加分）
    if not np.isnan(vol_sma[disp_idx]) and vol_sma[disp_idx] > 0:
        vol_ratio = volumes[disp_idx] / vol_sma[disp_idx]
        vol_bonus = min(1.0, max(0.0, (vol_ratio - 1.0) * 0.5))
        if vol_bonus > 0:
            score += vol_bonus
            confirmations.append(f"volume:{vol_ratio:.1f}x")
        elif vol_ratio < 1.0:
            score -= 1.0  # 低於平均量，扣分
            confirmations.append("low_volume")

    if score < cfg.ob_score_threshold:
        return None

    return OrderBlock(
        type="bullish",
        top=float(max(opens[i], closes[i])),
        bottom=float(min(opens[i], closes[i])),
        date=str(dates[i]),
        index=i,
        score=round(score, 1),
        confirmations=confirmations,
        formation_bars_ago=len(closes) - 1 - i,
    )


def _try_bearish_ob(
    i: int,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    dates: np.ndarray,
    atr: np.ndarray,
    vol_sma: np.ndarray,
    event_bar_indices: set[int],
    disp_atr: float,
    cfg: SmcConfig,
) -> OrderBlock | None:
    """嘗試在 bar i 建立 Bearish OB。"""
    n = len(closes)
    cur_atr = atr[i]

    # 找後面的 displacement candle（下跌）
    disp_idx = None
    disp_strength = 0.0
    for j in range(i + 1, min(i + 6, n)):
        body = opens[j] - closes[j]  # 陰棒 body
        if body > disp_atr * cur_atr:
            disp_idx = j
            disp_strength = body / cur_atr
            break

    if disp_idx is None:
        return None

    confirmations: list[str] = []
    score = 0.0

    # 1. Displacement
    score += min(3.0, max(0.0, disp_strength - 0.5))
    confirmations.append(f"displacement:{disp_strength:.1f}ATR")

    # 2. FVG 確認（bearish FVG）
    has_fvg = False
    for j in range(i + 1, min(i + cfg.ob_fvg_window + 1, n - 1)):
        if j + 1 < n and lows[j - 1] > highs[j + 1]:  # bearish FVG
            has_fvg = True
            break
    if not has_fvg:
        return None
    score += 2.0
    confirmations.append("fvg_confirmed")

    # 3. 結構突破
    has_bos = False
    for j in range(i + 1, min(i + cfg.ob_bos_window + 1, n)):
        if j in event_bar_indices:
            has_bos = True
            break
    if not has_bos:
        return None
    score += 2.0
    confirmations.append("structure_break")

    # 4. 流動性掃蕩
    sweep_bonus = _check_sweep_before_ob(i, opens, highs, lows, closes)
    if sweep_bonus > 0:
        score += min(1.5, sweep_bonus)
        confirmations.append(f"sweep:{sweep_bonus:.1f}")

    # 5. 成交量
    if not np.isnan(vol_sma[disp_idx]) and vol_sma[disp_idx] > 0:
        vol_ratio = volumes[disp_idx] / vol_sma[disp_idx]
        vol_bonus = min(1.0, max(0.0, (vol_ratio - 1.0) * 0.5))
        if vol_bonus > 0:
            score += vol_bonus
            confirmations.append(f"volume:{vol_ratio:.1f}x")
        elif vol_ratio < 1.0:
            score -= 1.0
            confirmations.append("low_volume")

    if score < cfg.ob_score_threshold:
        return None

    return OrderBlock(
        type="bearish",
        top=float(max(opens[i], closes[i])),
        bottom=float(min(opens[i], closes[i])),
        date=str(dates[i]),
        index=i,
        score=round(score, 1),
        confirmations=confirmations,
        formation_bars_ago=len(closes) - 1 - i,
    )


def _check_sweep_before_ob(
    ob_idx: int,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
) -> float:
    """檢查 OB 前 1-3 根是否有流動性掃蕩（影線穿越+收盤未過）。"""
    bonus = 0.0
    for j in range(max(0, ob_idx - 3), ob_idx):
        candle_top = max(opens[j], closes[j])
        candle_bottom = min(opens[j], closes[j])
        body = candle_top - candle_bottom
        wick_up = highs[j] - candle_top
        wick_down = candle_bottom - lows[j]
        if body > 0:
            wick_ratio = max(wick_up, wick_down) / body
            if wick_ratio > 1.5:
                bonus = max(bonus, min(1.5, wick_ratio / 3))
    return bonus


# ═══════════════════════════════════════════════════════════════
# OB 去重
# ═══════════════════════════════════════════════════════════════

def dedup_order_blocks(
    obs: list[OrderBlock],
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> list[OrderBlock]:
    """
    OB 去重規則：
    1. 同一 impulsive leg → 保留主 OB + 最多 1 個 nested
    2. 重疊 > 50% 且非包含 → 合併
    """
    if not obs:
        return []

    # 按 index 排序
    obs = sorted(obs, key=lambda o: o.index)

    # 按類型分開處理
    bullish = [o for o in obs if o.type == "bullish"]
    bearish = [o for o in obs if o.type == "bearish"]

    result = _dedup_one_side(bullish, cfg) + _dedup_one_side(bearish, cfg)
    return sorted(result, key=lambda o: o.index)


def _dedup_one_side(
    obs: list[OrderBlock],
    cfg: SmcConfig,
) -> list[OrderBlock]:
    """單邊去重。"""
    if len(obs) <= 1:
        return obs

    result: list[OrderBlock] = []
    i = 0
    while i < len(obs):
        main = obs[i]
        nested_candidates: list[OrderBlock] = []

        # 找同一 leg 的 OB（index 相鄰且價格重疊）
        j = i + 1
        while j < len(obs) and obs[j].index - main.index <= 10:
            overlap = _overlap_ratio(main, obs[j])
            if overlap > cfg.ob_overlap_merge_threshold:
                # 重疊 > 50% → 合併
                main = _merge_obs(main, obs[j])
            elif _is_nested(main, obs[j]):
                nested_candidates.append(obs[j])
            j += 1

        result.append(main)

        # 最多保留 1 個 nested
        if nested_candidates:
            best_nested = max(nested_candidates, key=lambda o: o.score)
            if (best_nested.score >= cfg.ob_nested_min_score
                    and _range_of(best_nested) < _range_of(main) * cfg.ob_nested_max_range_ratio):
                best_nested.nested = True
                best_nested.parent_index = main.index
                result.append(best_nested)

        i = j

    return result


def _overlap_ratio(a: OrderBlock, b: OrderBlock) -> float:
    """兩個 OB 的重疊比例。"""
    overlap_top = min(a.top, b.top)
    overlap_bottom = max(a.bottom, b.bottom)
    if overlap_top <= overlap_bottom:
        return 0.0
    overlap = overlap_top - overlap_bottom
    smaller = min(_range_of(a), _range_of(b))
    return overlap / smaller if smaller > 0 else 0.0


def _is_nested(parent: OrderBlock, child: OrderBlock) -> bool:
    """child 是否完全包含在 parent 範圍內。"""
    return child.top <= parent.top and child.bottom >= parent.bottom


def _merge_obs(a: OrderBlock, b: OrderBlock) -> OrderBlock:
    """合併兩個 OB，取較高分。"""
    winner = a if a.score >= b.score else b
    return OrderBlock(
        type=winner.type,
        top=max(a.top, b.top),
        bottom=min(a.bottom, b.bottom),
        date=winner.date,
        index=winner.index,
        score=max(a.score, b.score),
        confirmations=winner.confirmations,
        formation_bars_ago=winner.formation_bars_ago,
    )


def _range_of(ob: OrderBlock) -> float:
    return ob.top - ob.bottom


# ═══════════════════════════════════════════════════════════════
# OB 狀態更新（mitigated + decay）
# ═══════════════════════════════════════════════════════════════

def update_ob_states(
    obs: list[OrderBlock],
    closes: np.ndarray,
    lows: np.ndarray,
    highs: np.ndarray,
    dates: np.ndarray,
    current_bar: int,
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> list[OrderBlock]:
    """
    更新 OB 的 mitigated 狀態和 decay。

    在 detect 後呼叫，遍歷 OB 形成後的所有 bar 來更新狀態。
    """
    for ob in obs:
        if ob.mitigated:
            continue

        # 遍歷 OB 形成後的 bar
        start = ob.index + 1
        retest_count = 0

        for bar_idx in range(start, current_bar + 1):
            if ob.type == "bullish":
                # 收盤 < OB.bottom → mitigated
                if closes[bar_idx] < ob.bottom:
                    ob.mitigated = True
                    ob.mitigated_date = str(dates[bar_idx])
                    break
                # 價格進入 OB zone（low 觸及 bottom）後離開（close > top）= retest
                if lows[bar_idx] <= ob.bottom and closes[bar_idx] > ob.top:
                    retest_count += 1
            else:  # bearish
                if closes[bar_idx] > ob.top:
                    ob.mitigated = True
                    ob.mitigated_date = str(dates[bar_idx])
                    break
                # 價格進入 OB zone（high 觸及 top）後離開（close < bottom）= retest
                if highs[bar_idx] >= ob.top and closes[bar_idx] < ob.bottom:
                    retest_count += 1

        ob.retest_count = retest_count

        if not ob.mitigated:
            # Retest decay
            ob.score -= retest_count * cfg.ob_retest_decay
            # Time decay
            bars_since = current_bar - ob.index
            if bars_since > cfg.ob_time_decay_bars:
                ob.score -= cfg.ob_time_decay_amount

            ob.score = round(max(0, ob.score), 1)

    return obs


# ═══════════════════════════════════════════════════════════════
# 整合入口
# ═══════════════════════════════════════════════════════════════

def analyze_order_blocks(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    dates: np.ndarray,
    atr: np.ndarray,
    events: list[StructureEvent],
    timeframe: str = "daily",
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> OrderBlockResult:
    """完整 OB 分析入口。"""
    n = len(closes)
    if n < 10:
        return OrderBlockResult()

    # 1. 偵測
    raw_obs = detect_order_blocks(
        opens, highs, lows, closes, volumes, dates, atr,
        events, timeframe, cfg,
    )

    # 2. 去重
    obs = dedup_order_blocks(raw_obs, cfg)

    # 3. 狀態更新
    obs = update_ob_states(obs, closes, lows, highs, dates, n - 1, cfg)

    # 4. 分類
    active_bullish = [
        ob for ob in obs
        if ob.type == "bullish" and not ob.mitigated and ob.score >= cfg.ob_expire_score
    ]
    active_bearish = [
        ob for ob in obs
        if ob.type == "bearish" and not ob.mitigated and ob.score >= cfg.ob_expire_score
    ]

    # 按 score 排序取 top N
    active_bullish.sort(key=lambda o: o.score, reverse=True)
    active_bearish.sort(key=lambda o: o.score, reverse=True)

    return OrderBlockResult(
        blocks=obs,
        active_bullish=active_bullish[:cfg.ob_max_display_per_side + 2],
        active_bearish=active_bearish[:cfg.ob_max_display_per_side + 2],
    )
