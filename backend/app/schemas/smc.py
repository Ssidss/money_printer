"""
SMC v2 — 統一數據 Schema

所有 SMC 模組的輸出都必須符合這些型別。
下游消費者（decision engine、API、前端）只接受這些型別。
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# 結構 (Structure)
# ═══════════════════════════════════════════════════════════════

class TrendDirection(str, Enum):
    UP = "uptrend"
    WEAK_UP = "weak_uptrend"
    RANGING = "ranging"
    WEAK_DOWN = "weak_downtrend"
    DOWN = "downtrend"
    INSUFFICIENT = "insufficient_data"


class SwingType(str, Enum):
    HH = "HH"
    HL = "HL"
    LH = "LH"
    LL = "LL"
    UNKNOWN = "UNKNOWN"


class SwingPoint(BaseModel):
    index: int
    date: str
    price: float
    type: SwingType
    is_high: bool  # True = swing high, False = swing low


class StructureEventType(str, Enum):
    BOS = "BOS"
    CHOCH = "CHoCH"
    MSS = "MSS"


class StructureEvent(BaseModel):
    type: StructureEventType
    direction: str  # "bullish" | "bearish"
    date: str
    price: float                         # 被突破的 swing point price
    break_bar_index: int                 # 突破的那根 bar index
    displacement: Optional[float] = None  # MSS 才有，ATR 倍數


class StructureResult(BaseModel):
    trend: TrendDirection
    swing_highs: list[SwingPoint] = Field(default_factory=list)
    swing_lows: list[SwingPoint] = Field(default_factory=list)
    events: list[StructureEvent] = Field(default_factory=list)
    latest_event: Optional[StructureEvent] = None
    hh_hl_ratio: str = ""  # "3/4"
    ll_lh_ratio: str = ""  # "3/4"


# ═══════════════════════════════════════════════════════════════
# Order Block
# ═══════════════════════════════════════════════════════════════

class OrderBlock(BaseModel):
    type: str  # "bullish" | "bearish"
    top: float
    bottom: float
    date: str
    index: int
    score: float = Field(ge=0, le=11)  # 0.0-10.0+
    confirmations: list[str] = Field(default_factory=list)
    retest_count: int = 0
    mitigated: bool = False
    mitigated_date: Optional[str] = None
    nested: bool = False
    parent_index: Optional[int] = None  # nested 的母 OB index
    formation_bars_ago: int = 0


class OrderBlockResult(BaseModel):
    blocks: list[OrderBlock] = Field(default_factory=list)
    active_bullish: list[OrderBlock] = Field(default_factory=list)
    active_bearish: list[OrderBlock] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# FVG
# ═══════════════════════════════════════════════════════════════

class FvgStatus(str, Enum):
    ACTIVE = "active"
    CE_TOUCHED = "ce_touched"
    RESPECTED = "respected"
    DEEPLY_FILLED = "deeply_filled"
    FULLY_FILLED = "fully_filled"
    INVERTED = "inverted"


class FvgGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class FairValueGap(BaseModel):
    type: str  # "bullish" | "bearish"
    top: float
    bottom: float
    ce: float  # CE midline = (top + bottom) / 2
    date: str
    index: int
    status: FvgStatus = FvgStatus.ACTIVE
    grade: FvgGrade = FvgGrade.C
    gap_pct: float = 0.0
    freshness: float = 1.0  # 0.0-1.0，隨時間衰減


class FvgResult(BaseModel):
    gaps: list[FairValueGap] = Field(default_factory=list)
    active: list[FairValueGap] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# 流動性 (Liquidity)
# ═══════════════════════════════════════════════════════════════

class LiquidityLevel(BaseModel):
    type: str  # "EQH" | "EQL"
    side: str  # "BSL" (buy-side) | "SSL" (sell-side)
    price: float
    touches: int = 0
    liq_score: float = 0.0  # 0.0-1.0
    members: list[int] = Field(default_factory=list)  # swing point indices
    swept: bool = False
    sweep_date: Optional[str] = None
    sweep_type: Optional[str] = None  # "sweep" | "run"


class LiquidityResult(BaseModel):
    levels: list[LiquidityLevel] = Field(default_factory=list)
    bsl: list[LiquidityLevel] = Field(default_factory=list)
    ssl: list[LiquidityLevel] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# Fibonacci
# ═══════════════════════════════════════════════════════════════

class FibZone(str, Enum):
    DEEP_DISCOUNT = "deep_discount"   # < 0.236
    DISCOUNT = "discount"             # 0.236 ~ 0.5
    EQUILIBRIUM = "equilibrium"       # ≈ 0.5
    PREMIUM = "premium"               # 0.5 ~ 0.764
    DEEP_PREMIUM = "deep_premium"     # > 0.764
    OTE = "ote"                       # 0.618 ~ 0.786
    UNKNOWN = "unknown"


class FibonacciResult(BaseModel):
    swing_high: float = 0.0
    swing_low: float = 0.0
    leg_score: float = 0.0
    levels: dict[str, float] = Field(default_factory=dict)
    current_zone: FibZone = FibZone.UNKNOWN
    current_fib: float = 0.0  # 目前價格的 fib 位置 0.0-1.0
    valid: bool = False  # 是否找到有效的 leg


# ═══════════════════════════════════════════════════════════════
# Market Regime
# ═══════════════════════════════════════════════════════════════

class MarketRegime(str, Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    HIGH_VOL = "high_volatility"
    LOW_VOL = "low_volatility"


class RegimeResult(BaseModel):
    regime: MarketRegime = MarketRegime.RANGING
    atr_percentile: float = 50.0


# ═══════════════════════════════════════════════════════════════
# 整合結果
# ═══════════════════════════════════════════════════════════════

class SmcResult(BaseModel):
    """統一 SMC 分析結果，所有下游模組只接受此型別"""
    ticker: str
    timeframe: str
    bar_count: int
    computed_at: str  # ISO datetime
    strategy_hash: str
    engine_version: str = "2.0.0"

    structure: StructureResult
    order_blocks: OrderBlockResult
    fvg: FvgResult
    liquidity: LiquidityResult
    fibonacci: FibonacciResult
    regime: RegimeResult

    warnings: list[str] = Field(default_factory=list)
    data_quality: str = "full"  # "full" | "partial" | "insufficient"
