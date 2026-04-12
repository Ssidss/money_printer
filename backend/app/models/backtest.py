from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Integer, Date, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
TIMESTAMPTZ = DateTime(timezone=True)

from ..database import Base


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # 策略參數 snapshot
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # 績效指標
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # {
    #   total_return_pct, annual_return_pct,
    #   max_drawdown_pct, sharpe_ratio,
    #   win_rate, total_trades, profitable_trades,
    #   avg_profit_pct, avg_loss_pct,
    # }

    # 所有模擬交易紀錄
    trades: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # [ {ticker, buy_date, buy_price, sell_date, sell_price, pnl_pct, exit_reason}, ... ]

    # 資金曲線（每日資產）
    equity_curve: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # [ {date, equity}, ... ]

    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# V3 Backtest Result — 多策略回測歷史
# ---------------------------------------------------------------------------

class BacktestResultV3(Base):
    __tablename__ = "backtest_results_v3"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # 回測區間 + 策略
    split: Mapped[str] = mapped_column(String(30), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    strategies: Mapped[list] = mapped_column(JSONB, nullable=False)  # ["smc_v2", "momentum_breakout"]

    # 關鍵指標（方便列表查詢排序）
    total_return_pct: Mapped[Optional[float]] = mapped_column(nullable=True)
    cagr_pct: Mapped[Optional[float]] = mapped_column(nullable=True)
    max_drawdown_pct: Mapped[Optional[float]] = mapped_column(nullable=True)
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(nullable=True)
    win_rate_pct: Mapped[Optional[float]] = mapped_column(nullable=True)
    profit_factor: Mapped[Optional[float]] = mapped_column(nullable=True)
    total_trades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 參數快照
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # { initial_capital, min_conditions, min_rr, max_positions, risk_per_trade_pct, ... }

    # 完整報告（JSONB blob — portfolio_summary, strategy_breakdown, trade_log, equity_curve, ...）
    report: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # 元數據
    duration_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    stock_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    trading_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_bt3_created_at", "created_at"),
    )
