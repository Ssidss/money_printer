"""
Decision Engine v2 — 決策結果 Schema
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SentimentGate(BaseModel):
    """情緒紅綠燈"""
    score: Optional[float] = None  # 0-100
    signal: str = "neutral"  # "green" | "yellow" | "red" | "neutral"
    reason: str = ""


class MtfGate(BaseModel):
    """多時間框架決策"""
    monthly_trend: str = "unknown"
    weekly_trend: str = "unknown"
    daily_trend: str = "unknown"
    action: str = ""  # 來自決策矩陣
    max_position_tier: str = "none"  # "核心" | "標準" | "探索" | "none"
    max_position_pct: float = 0.0


class EntryPlan(BaseModel):
    """完整進場計畫"""
    ticker: str
    recommendation: str = "不推薦"  # "強力推薦" | "推薦" | "觀察" | "觀望" | "不推薦"
    action: str = "不操作"  # "買入" | "等回調" | "觀望" | "不操作"

    entry_price: Optional[float] = None
    entry_source: str = ""  # "OB(7.8)" | "FVG" | "SwingLow" | "OTE"

    stop_price: Optional[float] = None
    stop_source: str = ""

    target_price: Optional[float] = None
    target_source: str = ""

    rr_ratio: Optional[float] = None

    position_tier: str = "none"  # "核心" | "標準" | "探索" | "none"
    max_position_pct: float = 0.0

    conditions_met: int = 0
    conditions_detail: dict[str, bool] = Field(default_factory=dict)

    sentiment: SentimentGate = Field(default_factory=SentimentGate)
    mtf: MtfGate = Field(default_factory=MtfGate)

    current_price: float = 0.0
    distance_to_entry_pct: Optional[float] = None  # 現價離進場價的距離 %

    warnings: list[str] = Field(default_factory=list)
