"""
SMC v2 — 流動性偵測

EQH/EQL (ATR 自適應容差) + Sweep/Run 判定 + liq_score。
"""

from __future__ import annotations

import numpy as np

from ...schemas.smc import (
    LiquidityLevel,
    LiquidityResult,
    SwingPoint,
)
from .config import SmcConfig, DEFAULT_CONFIG
from .helpers import get_current_atr


# ═══════════════════════════════════════════════════════════════
# EQH / EQL 偵測
# ═══════════════════════════════════════════════════════════════

def detect_liquidity(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    dates: np.ndarray,
    atr: np.ndarray,
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> list[LiquidityLevel]:
    """
    偵測 EQH（Equal Highs / BSL）和 EQL（Equal Lows / SSL）。

    自適應容差：tolerance = max(0.3%, 0.15 * ATR%)
    """
    n = len(closes)
    if n == 0:
        return []

    current_atr = get_current_atr(highs, lows, closes, cfg.atr_period)
    last_close = float(closes[-1]) if n > 0 else 1.0

    # 計算容差
    atr_pct = (current_atr / last_close * 100) if last_close > 0 else 1.0
    tolerance_pct = max(cfg.liq_tolerance_pct_floor, cfg.liq_tolerance_atr_mult * atr_pct)
    tolerance_abs = last_close * tolerance_pct / 100

    levels: list[LiquidityLevel] = []

    # EQH: 用 swing highs 聚類
    eqh_clusters = _cluster_swings(swing_highs, tolerance_abs, is_high=True)
    for cluster in eqh_clusters:
        if len(cluster) < cfg.liq_min_touches:
            continue
        avg_price = sum(s.price for s in cluster) / len(cluster)
        liq_score = _calc_liq_score(cluster, n, cfg)

        levels.append(LiquidityLevel(
            type="EQH",
            side="BSL",
            price=round(avg_price, 2),
            touches=len(cluster),
            liq_score=round(liq_score, 3),
            members=[s.index for s in cluster],
        ))

    # EQL: 用 swing lows 聚類
    eql_clusters = _cluster_swings(swing_lows, tolerance_abs, is_high=False)
    for cluster in eql_clusters:
        if len(cluster) < cfg.liq_min_touches:
            continue
        avg_price = sum(s.price for s in cluster) / len(cluster)
        liq_score = _calc_liq_score(cluster, n, cfg)

        levels.append(LiquidityLevel(
            type="EQL",
            side="SSL",
            price=round(avg_price, 2),
            touches=len(cluster),
            liq_score=round(liq_score, 3),
            members=[s.index for s in cluster],
        ))

    return levels


def _cluster_swings(
    swings: list[SwingPoint],
    tolerance: float,
    is_high: bool,
) -> list[list[SwingPoint]]:
    """將 swing points 按價格容差聚類。"""
    if not swings:
        return []

    # 按價格排序
    sorted_swings = sorted(swings, key=lambda s: s.price, reverse=is_high)
    clusters: list[list[SwingPoint]] = []
    used: set[int] = set()

    for i, s in enumerate(sorted_swings):
        if i in used:
            continue
        cluster = [s]
        used.add(i)

        for j in range(i + 1, len(sorted_swings)):
            if j in used:
                continue
            if abs(sorted_swings[j].price - s.price) <= tolerance:
                cluster.append(sorted_swings[j])
                used.add(j)

        clusters.append(cluster)

    # 合併相近的 cluster
    return _merge_close_clusters(clusters, tolerance)


def _merge_close_clusters(
    clusters: list[list[SwingPoint]],
    tolerance: float,
) -> list[list[SwingPoint]]:
    """合併價格接近的 cluster。"""
    if len(clusters) <= 1:
        return clusters

    merged: list[list[SwingPoint]] = []
    for cluster in clusters:
        avg = sum(s.price for s in cluster) / len(cluster)
        found = False
        for existing in merged:
            existing_avg = sum(s.price for s in existing) / len(existing)
            if abs(avg - existing_avg) <= tolerance:
                existing.extend(cluster)
                found = True
                break
        if not found:
            merged.append(cluster)

    return merged


def _calc_liq_score(
    cluster: list[SwingPoint],
    total_bars: int,
    cfg: SmcConfig,
) -> float:
    """
    liq_score = touches * 0.4 + time_spread * 0.3 + dwell_ratio * 0.3

    touches: cluster 大小
    time_spread: 跨越時間 / 總 bar 數
    dwell_ratio: 價格在該區域停留的比例（用 cluster 分佈近似）
    """
    touches = len(cluster)
    indices = [s.index for s in cluster]
    first_idx = min(indices)
    last_idx = max(indices)

    # touches 正規化（2=0.3, 3=0.6, 4+=1.0）
    touch_score = min(1.0, (touches - 1) * 0.3)

    # time_spread
    span = last_idx - first_idx
    time_spread = min(1.0, span / max(total_bars * 0.3, 1))

    # dwell_ratio（用 cluster 密度近似）
    dwell_ratio = touches / max(span, 1) if span > 0 else 0.5

    score = (touch_score * cfg.liq_score_touch_weight
             + time_spread * cfg.liq_score_spread_weight
             + min(1.0, dwell_ratio) * cfg.liq_score_dwell_weight)

    return min(1.0, score)


# ═══════════════════════════════════════════════════════════════
# Sweep / Run 判定
# ═══════════════════════════════════════════════════════════════

def detect_sweeps(
    levels: list[LiquidityLevel],
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    opens: np.ndarray,
    dates: np.ndarray,
    atr: np.ndarray,
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> list[LiquidityLevel]:
    """
    偵測流動性是否被 Sweep 或 Run。

    Sweep（假突破）: High > liq_price AND Close < liq_price
    Run（真突破）: Close > liq_price AND body > 0.5 ATR
    """
    n = len(closes)

    # 取 fallback ATR（避免 NaN 導致 cur_atr=0 的誤判）
    fallback_atr = 0.0
    for v in reversed(atr):
        if not np.isnan(v):
            fallback_atr = v
            break

    for level in levels:
        if level.swept:
            continue

        start = max(level.members) + 1 if level.members else 0

        for bar_idx in range(start, n):
            cur_atr = atr[bar_idx] if not np.isnan(atr[bar_idx]) else fallback_atr
            if cur_atr <= 0:
                continue
            body = abs(closes[bar_idx] - opens[bar_idx])

            if level.type == "EQH":  # BSL — 上方流動性
                if highs[bar_idx] > level.price:
                    level.swept = True
                    level.sweep_date = str(dates[bar_idx])
                    if closes[bar_idx] < level.price:
                        level.sweep_type = "sweep"
                    elif body > cfg.sweep_body_threshold_atr * cur_atr:
                        level.sweep_type = "run"
                    else:
                        level.sweep_type = "sweep"
                    break

            else:  # EQL — SSL 下方流動性
                if lows[bar_idx] < level.price:
                    level.swept = True
                    level.sweep_date = str(dates[bar_idx])
                    if closes[bar_idx] > level.price:
                        level.sweep_type = "sweep"
                    elif body > cfg.sweep_body_threshold_atr * cur_atr:
                        level.sweep_type = "run"
                    else:
                        level.sweep_type = "sweep"
                    break

    return levels


# ═══════════════════════════════════════════════════════════════
# 整合入口
# ═══════════════════════════════════════════════════════════════

def analyze_liquidity(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    dates: np.ndarray,
    atr: np.ndarray,
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> LiquidityResult:
    """完整流動性分析入口。"""
    # 1. 偵測 EQH/EQL
    levels = detect_liquidity(
        highs, lows, closes, dates, atr,
        swing_highs, swing_lows, cfg,
    )

    # 2. 偵測 Sweep/Run
    levels = detect_sweeps(levels, highs, lows, closes, opens, dates, atr, cfg)

    # 3. 分類
    bsl = [l for l in levels if l.side == "BSL"]
    ssl = [l for l in levels if l.side == "SSL"]

    # 按 liq_score 排序
    bsl.sort(key=lambda l: l.liq_score, reverse=True)
    ssl.sort(key=lambda l: l.liq_score, reverse=True)

    return LiquidityResult(levels=levels, bsl=bsl, ssl=ssl)
