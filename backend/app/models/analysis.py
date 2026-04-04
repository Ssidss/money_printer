from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Numeric, Integer, ForeignKey, UniqueConstraint, Index, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
TIMESTAMPTZ = DateTime(timezone=True)

from ..database import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        UniqueConstraint("stock_id", "analysis_date"),
        Index("idx_analysis_stock_date", "stock_id", "analysis_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    composite_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    technical_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    sentiment_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    recommendation: Mapped[Optional[str]] = mapped_column(String(20))   # 強力推薦 | 推薦 | 觀察 | 不推薦

    rsi: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    macd: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    macd_signal: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    ma5: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    ma20: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    ma60: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    bb_upper: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    bb_lower: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))
    volume_ratio: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    close_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 4))

    signals: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    news_summary: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)

    stock: Mapped["Stock"] = relationship(back_populates="analyses")  # type: ignore


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        Index("idx_news_stock_published", "stock_id", "published_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1000))
    source: Mapped[Optional[str]] = mapped_column(String(100))
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)

    stock: Mapped["Stock"] = relationship(back_populates="news")  # type: ignore
