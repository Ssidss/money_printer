"""
PipelineRun 模型 — 記錄 pipeline 執行狀態

用於持久化 pipeline 的執行歷史，確保 cancelled 狀態等不會丟失。
"""

from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Integer, Date, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
TIMESTAMPTZ = DateTime(timezone=True)

from ..database import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    # 狀態：running | completed | failed | cancelled | stopped
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")

    # Pipeline 參數
    symbols: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    train_start: Mapped[date] = mapped_column(Date, nullable=False)
    train_end: Mapped[date] = mapped_column(Date, nullable=False)
    val_start: Mapped[date] = mapped_column(Date, nullable=False)
    val_end: Mapped[date] = mapped_column(Date, nullable=False)

    strategies: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=lambda: ["smc_v2"])
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, default="1d")
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    convergence_threshold: Mapped[float] = mapped_column(nullable=False, default=0.02)

    # 執行進度
    current_iteration: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate_history: Mapped[list[float]] = mapped_column(JSONB, nullable=False, default=list)

    # 結果
    converged: Mapped[bool] = mapped_column(nullable=False, default=False)
    validation_report: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 錯誤訊息（若有）
    error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # 時間戳
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow, onupdate=datetime.utcnow)
