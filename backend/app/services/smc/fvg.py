"""
SMC v2 — Fair Value Gap 偵測

6 級狀態追蹤 + CE 中線 + 分級 (A/B/C) + 時間衰減。
"""

from __future__ import annotations

import numpy as np

from ...schemas.smc import (
    FairValueGap,
    FvgResult,
    FvgStatus,
    FvgGrade,
)
from .config import SmcConfig, DEFAULT_CONFIG


# ═══════════════════════════════════════════════════════════════
# FVG 偵測
# ═══════════════════════════════════════════════════════════════

def detect_fvg(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    dates: np.ndarray,
    atr: np.ndarray,
    timeframe: str = "daily",
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> list[FairValueGap]:
    """
    偵測所有 Fair Value Gaps。

    Bullish FVG: K1.High < K3.Low（三根 K 棒中間留空白）
    Bearish FVG: K1.Low > K3.High

    K2 displacement 分級：
    A 級: body > 1.5 ATR
    B 級: body > 1.2 ATR
    C 級: body > 1.0 ATR
    < 1.0 ATR → 不標記
    """
    n = len(closes)
    if n < 3:
        return []

    fvgs: list[FairValueGap] = []

    for i in range(1, n - 1):
        cur_atr = atr[i] if not np.isnan(atr[i]) else 0
        if cur_atr <= 0:
            continue

        k2_body = abs(closes[i] - opens[i])

        # 分級
        if k2_body >= cfg.fvg_grade_a_atr * cur_atr:
            grade = FvgGrade.A
        elif k2_body >= cfg.fvg_grade_b_atr * cur_atr:
            grade = FvgGrade.B
        elif k2_body >= cfg.fvg_grade_c_atr * cur_atr:
            grade = FvgGrade.C
        else:
            continue  # 不夠格

        # Bullish FVG: K1.High < K3.Low
        if highs[i - 1] < lows[i + 1]:
            top = float(lows[i + 1])
            bottom = float(highs[i - 1])
            gap_size = top - bottom
            gap_pct = (gap_size / closes[i]) * 100 if closes[i] > 0 else 0

            fvgs.append(FairValueGap(
                type="bullish",
                top=top,
                bottom=bottom,
                ce=(top + bottom) / 2,
                date=str(dates[i]),
                index=i,
                grade=grade,
                gap_pct=round(gap_pct, 2),
            ))

        # Bearish FVG: K1.Low > K3.High
        elif lows[i - 1] > highs[i + 1]:
            top = float(lows[i - 1])
            bottom = float(highs[i + 1])
            gap_size = top - bottom
            gap_pct = (gap_size / closes[i]) * 100 if closes[i] > 0 else 0

            fvgs.append(FairValueGap(
                type="bearish",
                top=top,
                bottom=bottom,
                ce=(top + bottom) / 2,
                date=str(dates[i]),
                index=i,
                grade=grade,
                gap_pct=round(gap_pct, 2),
            ))

    return fvgs


# ═══════════════════════════════════════════════════════════════
# FVG 狀態更新
# ═══════════════════════════════════════════════════════════════

def update_fvg_states(
    fvgs: list[FairValueGap],
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    current_bar: int,
    total_bars: int,
    timeframe: str = "daily",
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> list[FairValueGap]:
    """
    更新每個 FVG 的狀態（6 級狀態機）。

    判定順序：
    1. Active:       價格尚未回測到 FVG 範圍內
    2. CE Touched:   低點觸及 CE 但收盤仍在 CE 之上
    3. Respected:    價格回到 FVG 後在 CE 之上反彈
    4. Deeply Filled: 收盤穿越 CE 但未穿越 bottom
    5. Fully Filled:  收盤穿越 bottom
    6. Inverted:     Fully Filled 後價格反向使用
    """
    decay_threshold = (cfg.fvg_decay_daily if timeframe == "daily"
                       else cfg.fvg_decay_weekly)

    for fvg in fvgs:
        if fvg.status in (FvgStatus.FULLY_FILLED, FvgStatus.INVERTED):
            fvg.freshness = 0.0
            continue

        start = fvg.index + 2  # FVG 後第二根開始
        touched_ce = False
        was_in_zone = False

        for bar_idx in range(start, current_bar + 1):
            # 先更新追蹤狀態，再判斷 FVG status
            if fvg.type == "bullish":
                if lows[bar_idx] <= fvg.ce:
                    touched_ce = True
                if lows[bar_idx] <= fvg.top:
                    was_in_zone = True

                # Fully Filled: 收盤 < FVG.bottom
                if closes[bar_idx] < fvg.bottom:
                    fvg.status = FvgStatus.FULLY_FILLED
                    break
                # Deeply Filled: 收盤穿越 CE 但未穿越 bottom
                elif closes[bar_idx] < fvg.ce and closes[bar_idx] > fvg.bottom:
                    fvg.status = FvgStatus.DEEPLY_FILLED
                # Respected: 進入 zone 後在 CE 之上反彈
                elif was_in_zone and touched_ce and closes[bar_idx] > fvg.top:
                    fvg.status = FvgStatus.RESPECTED
                # CE Touched
                elif touched_ce and fvg.status == FvgStatus.ACTIVE:
                    fvg.status = FvgStatus.CE_TOUCHED
            else:  # bearish
                if highs[bar_idx] >= fvg.ce:
                    touched_ce = True
                if highs[bar_idx] >= fvg.bottom:
                    was_in_zone = True

                if closes[bar_idx] > fvg.top:
                    fvg.status = FvgStatus.FULLY_FILLED
                    break
                elif closes[bar_idx] > fvg.ce and closes[bar_idx] < fvg.top:
                    fvg.status = FvgStatus.DEEPLY_FILLED
                elif was_in_zone and touched_ce and closes[bar_idx] < fvg.bottom:
                    fvg.status = FvgStatus.RESPECTED
                elif touched_ce and fvg.status == FvgStatus.ACTIVE:
                    fvg.status = FvgStatus.CE_TOUCHED

        # 時間衰減（對 ACTIVE、CE_TOUCHED、RESPECTED 都適用）
        bars_since = current_bar - fvg.index
        if bars_since > decay_threshold:
            if fvg.status == FvgStatus.ACTIVE:
                fvg.status = FvgStatus.CE_TOUCHED
            elif fvg.status in (FvgStatus.CE_TOUCHED, FvgStatus.RESPECTED):
                if bars_since > decay_threshold * 1.5:
                    fvg.status = FvgStatus.DEEPLY_FILLED

        # 計算 freshness
        if fvg.status in (FvgStatus.FULLY_FILLED, FvgStatus.INVERTED):
            fvg.freshness = 0.0
        else:
            fvg.freshness = round(max(0.0, 1.0 - bars_since / (decay_threshold * 2)), 2)

    return fvgs


# ═══════════════════════════════════════════════════════════════
# 整合入口
# ═══════════════════════════════════════════════════════════════

def analyze_fvg(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    dates: np.ndarray,
    atr: np.ndarray,
    timeframe: str = "daily",
    cfg: SmcConfig = DEFAULT_CONFIG,
) -> FvgResult:
    """完整 FVG 分析入口。"""
    n = len(closes)
    if n < 3:
        return FvgResult()

    # 1. 偵測
    fvgs = detect_fvg(opens, highs, lows, closes, dates, atr, timeframe, cfg)

    # 2. 狀態更新
    fvgs = update_fvg_states(fvgs, highs, lows, closes, n - 1, n, timeframe, cfg)

    # 3. 篩選 active
    active = [
        f for f in fvgs
        if f.status in (FvgStatus.ACTIVE, FvgStatus.CE_TOUCHED, FvgStatus.RESPECTED)
        and f.freshness > 0
    ]

    return FvgResult(gaps=fvgs, active=active)
