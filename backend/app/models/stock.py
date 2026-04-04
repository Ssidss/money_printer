from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Boolean, Numeric, BigInteger, Date, Text, Integer, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
TIMESTAMPTZ = DateTime(timezone=True)

from ..database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(100))
    market: Mapped[str] = mapped_column(String(10), nullable=False)   # "US" | "TW"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow, onupdate=datetime.utcnow)

    prices: Mapped[list["PriceHistory"]] = relationship(back_populates="stock", cascade="all, delete-orphan")
    analyses: Mapped[list["AnalysisResult"]] = relationship(back_populates="stock", cascade="all, delete-orphan")
    news: Mapped[list["NewsArticle"]] = relationship(back_populates="stock", cascade="all, delete-orphan")
    holdings: Mapped[list["PortfolioHolding"]] = relationship(back_populates="stock")
    transactions: Mapped[list["PortfolioTransaction"]] = relationship(back_populates="stock")


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (
        UniqueConstraint("stock_id", "date"),
        Index("idx_price_stock_date", "stock_id", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    high: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    low: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    close: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)

    stock: Mapped["Stock"] = relationship(back_populates="prices")
