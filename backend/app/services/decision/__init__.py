"""
Decision Engine v2 — 整合入口

run_decision() 接收 SmcResult + 情緒分數 → 輸出 EntryPlan。
"""

from __future__ import annotations

from .entry import generate_entry_plan
from .sentiment_gate import evaluate_sentiment
from .mtf_gate import evaluate_mtf
from .position_sizer import calculate_position

__all__ = [
    "generate_entry_plan",
    "evaluate_sentiment",
    "evaluate_mtf",
    "calculate_position",
]
