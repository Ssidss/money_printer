"""
SMC v2 — 所有可調參數集中管理

修改任何參數會改變 strategy_hash → 觸發全量重算。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class SmcConfig:
    """SMC 引擎全域配置（immutable）"""

    # ── ATR ──
    atr_period: int = 14

    # ── Swing Point ──
    swing_n_daily: int = 3
    swing_n_weekly: int = 5
    swing_n_monthly: int = 3
    swing_tolerance_atr_mult: float = 0.05
    swing_tolerance_min_ticks: int = 3
    swing_high_vol_threshold: float = 0.04   # ATR/close > 4% → 高波動
    swing_low_vol_threshold: float = 0.01    # ATR/close < 1% → 低波動
    swing_high_vol_mult: float = 1.5
    swing_low_vol_mult: float = 0.7

    # ── 趨勢 ──
    trend_swing_groups: int = 4    # 最近 N 組 Swing 判斷趨勢
    trend_min_consistent: int = 3  # 至少 3/4 一致

    # ── 結構事件 ──
    choch_max_body_atr: float = 1.5     # CHoCH: break candle body ≤ 1.5 ATR
    mss_min_displacement_atr: float = 1.5  # MSS: displacement body > 1.5 ATR
    mss_confirm_window_daily: int = 5
    mss_confirm_window_weekly: int = 3
    mss_confirm_window_monthly: int = 3

    # ── Order Block ──
    ob_displacement_atr_daily: float = 1.5
    ob_displacement_atr_weekly: float = 1.3
    ob_fvg_window: int = 5         # FVG 確認窗口（OB 後 N 根）
    ob_bos_window: int = 10        # BOS 確認窗口（OB 後 N 根）
    ob_score_threshold: float = 4.0
    ob_score_ideal: float = 7.0
    ob_retest_decay: float = 0.5
    ob_time_decay_bars: int = 60   # 日線 60 天
    ob_time_decay_amount: float = 1.0
    ob_expire_score: float = 2.0
    ob_max_display_per_side: int = 3
    ob_nested_max_range_ratio: float = 0.5
    ob_nested_min_score: float = 3.0
    ob_overlap_merge_threshold: float = 0.5

    # ── FVG ──
    fvg_grade_a_atr: float = 1.5
    fvg_grade_b_atr: float = 1.2
    fvg_grade_c_atr: float = 1.0    # 最低門檻
    fvg_decay_daily: int = 40        # 日線 40 天後降級
    fvg_decay_weekly: int = 140      # 20 週 = 140 天

    # ── 流動性 ──
    liq_tolerance_pct_floor: float = 0.3   # 最低 0.3%
    liq_tolerance_atr_mult: float = 0.15   # 0.15 * ATR%
    liq_min_touches: int = 2
    liq_score_touch_weight: float = 0.4
    liq_score_spread_weight: float = 0.3
    liq_score_dwell_weight: float = 0.3
    # Sweep vs Run
    sweep_body_threshold_atr: float = 0.5  # Run: body > 0.5 ATR

    # ── Fibonacci ──
    fib_min_range_atr: float = 5.0         # leg range 最少 5 ATR
    fib_recency_decay_days: int = 120
    fib_displacement_weight: float = 0.4
    fib_recency_weight: float = 0.4
    fib_range_quality_weight: float = 0.2
    fib_range_quality_cap: float = 10.0
    fib_levels: tuple[float, ...] = (0.0, 0.236, 0.382, 0.5, 0.618, 0.705, 0.786, 1.0)
    fib_ote_low: float = 0.618
    fib_ote_high: float = 0.786

    # ── Volume 驗證 ──
    vol_sma_period: int = 20
    vol_ob_displacement_mult: float = 1.5
    vol_bos_confirmation_mult: float = 1.2
    vol_sweep_confirmation_mult: float = 1.3

    # ── Tick Size ──
    tick_us_normal: float = 0.01
    tick_us_penny: float = 0.0001
    tick_us_penny_threshold: float = 1.0

    def strategy_hash(self) -> str:
        """參數的 md5 hash，用於偵測配置變更"""
        raw = json.dumps(asdict(self), sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()[:16]


# 全域單例
DEFAULT_CONFIG = SmcConfig()
