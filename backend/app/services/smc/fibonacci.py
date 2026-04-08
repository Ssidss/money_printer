"""
SMC v2 — Fibonacci 分析

Premium/Discount/OTE 區域判定 + Swing Leg 選擇 + Leg Scoring。
"""

from __future__ import annotations

import numpy as np

from ...schemas.smc import (
    FibonacciResult,
    FibZone,
    SwingPoint,
)
from .config import SmcConfig, DEFAULT_CONFIG
from .helpers import get_current_atr


# ═══════════════════════════════════════════════════════════════
# Swing Leg 候選評分
# ═══════════════════════════════════════════════════════════════

def _find_candidate_legs(
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
    closes: np.ndarray,
    opens: np.ndarray,
    atr: np.ndarray,
    current_close: float,
    cfg: SmcConfig,
) -> list[dict]:
    """
    找有 displacement 的主升段候選。

    候選 = 自然的 swing_low → 下一個 swing_high 配對（做多用）
    只看相鄰配對，不做 O(n²) 全排列。
    排除已被完全回撤的（current_close < swing_low）
    """
    candidates = []
    current_atr = 0.0
    for v in reversed(atr):
        if not np.isnan(v):
            current_atr = v
            break

    if current_atr <= 0:
        return []

    # 策略：每個 swing_low 配對其後方「最高的」swing_high
    # 這找的是每個回調低點到其後反彈高點的 leg
    for sl in swing_lows:
        # 找 sl 之後的所有 swing_high
        candidates_sh = [sh for sh in swing_highs if sh.index > sl.index]
        if not candidates_sh:
            continue

        # 取最高的那個（代表主升段的頂點）
        sh = max(candidates_sh, key=lambda s: s.price)

        leg_range = sh.price - sl.price
        if leg_range <= 0:
            continue

        # 排除已被完全回撤的
        if current_close < sl.price:
            continue

        # range 檢查：至少 5 ATR
        if leg_range < cfg.fib_min_range_atr * current_atr:
            continue

        # 檢查 displacement
        has_displacement = False
        disp_strength = 0.0
        for bar_idx in range(sl.index, min(sh.index + 1, len(closes))):
            bar_atr = atr[bar_idx] if not np.isnan(atr[bar_idx]) else current_atr
            body = abs(closes[bar_idx] - opens[bar_idx])
            if body > 1.5 * bar_atr:
                has_displacement = True
                disp_strength = max(disp_strength, body / bar_atr)

        if not has_displacement:
            continue

        candidates.append({
            "swing_low": sl,
            "swing_high": sh,
            "range": leg_range,
            "displacement_strength": disp_strength,
        })

    # 去重：如果多個候選的 swing_high 相同，只保留 leg_score 最高的
    seen_sh: dict[int, dict] = {}
    for c in candidates:
        sh_idx = c["swing_high"].index
        if sh_idx not in seen_sh:
            seen_sh[sh_idx] = c
        else:
            # 保留 range 更大的
            if c["range"] > seen_sh[sh_idx]["range"]:
                seen_sh[sh_idx] = c

    return list(seen_sh.values())


def _score_leg(
    candidate: dict,
    current_bar_idx: int,
    current_atr: float,
    cfg: SmcConfig,
) -> float:
    """
    候選評分：
    leg_score = displacement_strength * 0.4 + recency * 0.4 + range_quality * 0.2
    """
    sh = candidate["swing_high"]
    disp = candidate["displacement_strength"]
    leg_range = candidate["range"]

    # displacement_strength（ATR 倍數，正規化到 0-1）
    disp_score = min(1.0, (disp - 1.0) / 3.0)

    # recency（越近越好）
    days_since = current_bar_idx - sh.index
    recency = max(0.0, 1.0 - days_since / cfg.fib_recency_decay_days)

    # range_quality（range / ATR，越大越好，cap 10）
    range_quality = min(1.0, (leg_range / current_atr) / cfg.fib_range_quality_cap) if current_atr > 0 else 0

    return (disp_score * cfg.fib_displacement_weight
            + recency * cfg.fib_recency_weight
            + range_quality * cfg.fib_range_quality_weight)


# ═══════════════════════════════════════════════════════════════
# Fibonacci 水位計算
# ═══════════════════════════════════════════════════════════════

def _compute_fib_levels(
    swing_high: float,
    swing_low: float,
    cfg: SmcConfig,
) -> dict[str, float]:
    """
    計算 Fibonacci 回撤水位。

    注意：SMC 的 Fibonacci 是從高往低量的回撤。
    level = swing_low + range * (1 - fib_ratio)
    → fib 0.0 = swing_high（頂部）
    → fib 1.0 = swing_low（底部）
    """
    rng = swing_high - swing_low
    levels = {}
    for fib in cfg.fib_levels:
        # 回撤水位：越大的 fib 值越靠近 swing_low
        price = swing_high - rng * fib
        levels[str(fib)] = round(price, 2)
    return levels


def _determine_zone(fib_value: float, cfg: SmcConfig) -> FibZone:
    """根據 fib 值判斷目前所在區域。"""
    if fib_value < 0 or fib_value > 1:
        return FibZone.UNKNOWN

    # OTE 優先判定
    if cfg.fib_ote_low <= fib_value <= cfg.fib_ote_high:
        return FibZone.OTE

    if fib_value < 0.236:
        return FibZone.DEEP_PREMIUM  # 接近頂部
    elif fib_value < 0.48:
        return FibZone.PREMIUM
    elif fib_value <= 0.52:
        return FibZone.EQUILIBRIUM
    elif fib_value < 0.764:
        return FibZone.DISCOUNT
    else:
        return FibZone.DEEP_DISCOUNT  # 接近底部


# ═══════════════════════════════════════════════════════════════
# 整合入口
# ═══════════════════════════════════════════════════════════════

def analyze_fibonacci(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr: np.ndarray,
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> FibonacciResult:
    """完整 Fibonacci 分析入口。"""
    n = len(closes)
    if n < 10 or not swing_highs or not swing_lows:
        return FibonacciResult()

    current_close = float(closes[-1])
    current_atr = get_current_atr(highs, lows, closes, cfg.atr_period)

    if current_atr <= 0:
        return FibonacciResult()

    # 1. 找候選 leg
    candidates = _find_candidate_legs(
        swing_highs, swing_lows, closes, opens, atr, current_close, cfg,
    )

    if not candidates:
        return FibonacciResult()

    # 2. 評分取最佳
    best = None
    best_score = -1.0
    for c in candidates:
        score = _score_leg(c, n - 1, current_atr, cfg)
        if score > best_score:
            best_score = score
            best = c

    if best is None:
        return FibonacciResult()

    sh_price = best["swing_high"].price
    sl_price = best["swing_low"].price
    rng = sh_price - sl_price

    # 3. 計算水位
    levels = _compute_fib_levels(sh_price, sl_price, cfg)

    # 4. 目前價格的 fib 位置
    # fib = (swing_high - current_close) / range
    # 0 = 在頂部，1 = 在底部
    current_fib = (sh_price - current_close) / rng if rng > 0 else 0.5
    # 如果 fib > 1.0 代表現價低於 swing_low（leg 可能已失效）
    # 如果 fib < 0 代表現價高於 swing_high（在 leg 頂部之上）
    current_fib = max(-0.5, min(1.2, current_fib))

    # 5. 判斷區域
    current_zone = _determine_zone(current_fib, cfg)

    return FibonacciResult(
        swing_high=round(sh_price, 2),
        swing_low=round(sl_price, 2),
        leg_score=round(best_score, 3),
        levels=levels,
        current_zone=current_zone,
        current_fib=round(current_fib, 3),
        valid=True,
    )
