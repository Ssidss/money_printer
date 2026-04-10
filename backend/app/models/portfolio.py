from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Numeric, Integer, ForeignKey, Text, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime
TIMESTAMPTZ = DateTime(timezone=True)

from ..database import Base


class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transactions"
    __table_args__ = (
        Index("idx_txn_stock", "stock_id"),
        Index("idx_txn_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)   # BUY | SELL
    shares: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    total_cost: Mapped[Optional[float]] = mapped_column(Numeric(16, 4))
    note: Mapped[Optional[str]] = mapped_column(Text)
    transacted_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)

    stock: Mapped["Stock"] = relationship(back_populates="transactions")  # type: ignore
    user: Mapped["User"] = relationship(back_populates="transactions")  # type: ignore


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    __table_args__ = (
        # 同一個 user 對同一支股票只有一筆 holding
        UniqueConstraint("user_id", "stock_id", name="uq_holding_user_stock"),
        Index("idx_holding_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False)
    total_shares: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    avg_cost: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    highest_price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)  # 追蹤停損用
    status: Mapped[str] = mapped_column(String(20), default="持有觀察")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow, onupdate=datetime.utcnow)

    stock: Mapped["Stock"] = relationship(back_populates="holdings")  # type: ignore
    user: Mapped["User"] = relationship(back_populates="holdings")  # type: ignore
