from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    String, Integer, SmallInteger, Date, Numeric, Boolean, Text,
    ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from .backtest import TIMESTAMPTZ
from ..database import Base


# ---------------------------------------------------------------------------
# 1. Strategy Profile — 策略檔案
# ---------------------------------------------------------------------------

class StrategyProfile(Base):
    __tablename__ = "strategy_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 策略參數
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    overrides: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    stock_settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # 狀態
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 最近一次回測
    latest_backtest_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("backtest_results_v2.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationships
    backtest_results: Mapped[list[BacktestResultV2]] = relationship(
        "BacktestResultV2",
        foreign_keys="BacktestResultV2.profile_id",
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    signals: Mapped[list[StrategySignal]] = relationship(
        back_populates="profile", cascade="all, delete-orphan",
    )

    __table_args__ = (
        # 同時只有一個 active
        Index("idx_strategy_active", "is_active", unique=True, postgresql_where=(is_active == True)),
    )


# ---------------------------------------------------------------------------
# 2. Backtest Result V2 — 回測結果（主表，只存摘要）
# ---------------------------------------------------------------------------

class BacktestResultV2(Base):
    __tablename__ = "backtest_results_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("strategy_profiles.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 回測區間
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_capital: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=1_000_000)
    market_filter: Mapped[str] = mapped_column(String(10), nullable=False, default="ALL")

    # 可重現性
    params_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    strategy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    run_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    stock_universe: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    data_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # 績效（JSONB OK — 固定大小 ~2KB）
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # 診斷報告（JSONB OK — 固定大小 ~5KB）
    diagnosis: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 元數據
    duration_secs: Mapped[Optional[float]] = mapped_column(Numeric(10, 1), nullable=True)
    stock_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    trading_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending | running | done | failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 紀錄是誰跑的（nullable = 相容舊資料 / CLI 執行）
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)

    # relationships
    profile: Mapped[StrategyProfile] = relationship(
        foreign_keys=[profile_id], back_populates="backtest_results",
    )
    trades: Mapped[list[BacktestTrade]] = relationship(
        back_populates="backtest_result", cascade="all, delete-orphan",
    )
    equity_points: Mapped[list[BacktestEquity]] = relationship(
        back_populates="backtest_result", cascade="all, delete-orphan",
    )
    creator: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by])  # type: ignore

    __table_args__ = (
        Index("idx_bt2_profile", "profile_id"),
        Index("idx_bt2_run_hash", "run_hash"),
    )


# ---------------------------------------------------------------------------
# 3. Backtest Trade — 回測交易明細（拆表）
# ---------------------------------------------------------------------------

class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    backtest_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("backtest_results_v2.id", ondelete="CASCADE"), nullable=False,
    )

    # 股票
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    stock_group: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    # 進場
    signal_date: Mapped[date] = mapped_column(Date, nullable=False)
    fill_date: Mapped[date] = mapped_column(Date, nullable=False)
    fill_price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    entry_source: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    position_tier: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    conditions_met: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    position_size_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)

    # 出場
    exit_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    exit_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    exit_reason: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    stop_source: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    target_source: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    # 損益
    planned_rr: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    actual_rr: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    pnl_pct: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    pnl_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    trade_cost: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    net_pnl: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    holding_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # MAE / MFE
    mae_pct: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    mfe_pct: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)

    # 上下文
    smc_trend_at_entry: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    smc_trend_at_exit: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # relationship
    backtest_result: Mapped[BacktestResultV2] = relationship(back_populates="trades")

    __table_args__ = (
        Index("idx_bt_trades_backtest", "backtest_id"),
        Index("idx_bt_trades_ticker", "ticker"),
        Index("idx_bt_trades_exit_reason", "backtest_id", "exit_reason"),
    )


# ---------------------------------------------------------------------------
# 4. Backtest Equity — 權益曲線（拆表）
# ---------------------------------------------------------------------------

class BacktestEquity(Base):
    __tablename__ = "backtest_equity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    backtest_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("backtest_results_v2.id", ondelete="CASCADE"), nullable=False,
    )

    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    equity: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    drawdown_pct: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    cash: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    positions_value: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    open_positions: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)

    # relationship
    backtest_result: Mapped[BacktestResultV2] = relationship(back_populates="equity_points")

    __table_args__ = (
        Index("idx_bt_equity_backtest", "backtest_id", "trade_date"),
    )


# ---------------------------------------------------------------------------
# 5. Strategy Signal — 實戰信號追蹤
# ---------------------------------------------------------------------------

class StrategySignal(Base):
    __tablename__ = "strategy_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("strategy_profiles.id", ondelete="CASCADE"), nullable=False,
    )
    stock_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False,
    )

    # 策略信號
    signal_date: Mapped[date] = mapped_column(Date, nullable=False)
    signal_action: Mapped[str] = mapped_column(String(20), nullable=False)
    signal_entry: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    signal_stop: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    signal_target: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    signal_rr: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    signal_tier: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    signal_conditions: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)

    # 使用者操作
    followed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    actual_entry: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    actual_exit: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    actual_pnl_pct: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)

    # 事後追蹤
    outcome_if_followed: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)

    skip_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationship
    profile: Mapped[StrategyProfile] = relationship(back_populates="signals")

    __table_args__ = (
        UniqueConstraint("profile_id", "stock_id", "signal_date", name="uq_signal_per_stock_date"),
        Index("idx_signals_profile_date", "profile_id", "signal_date"),
        Index("idx_signals_followed", "profile_id", "followed", postgresql_where=(followed == None)),
    )
