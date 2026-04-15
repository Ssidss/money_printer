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
