from __future__ import annotations
"""
AI 分析筆記 Model
儲存 Claude 對個股的深度分析記錄，包含策略建議、情境分析等
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Numeric, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
TIMESTAMPTZ = DateTime(timezone=True)

from ..database import Base


class AiAnalysisNote(Base):
    __tablename__ = "ai_analysis_notes"
    __table_args__ = (
        Index("idx_ai_note_stock_created", "stock_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)

    # 分析類型
    analysis_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # "individual" = 單支個股深度分析
    # "top_pick"   = 批次分析中的高分推薦
    # "portfolio"  = 持倉健檢
    # "watchlist"  = 觀察名單評估

    # AI 判斷
    recommendation: Mapped[str] = mapped_column(String(20), nullable=False)
    # 推薦等級：強力推薦 / 推薦 / 觀察 / 不推薦
    action: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # 建議操作：買入 / 加碼 / 持有 / 減倉 / 出場 / 觀望

    # AI 分析內容（Markdown）
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    # 分析時的市場快照
    price_at_analysis: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    composite_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    smc_trend: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # 進場建議快照
    entry_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    stop_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    target_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    rr_ratio: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)

    # 額外結構化資料（如情境分析、觸發條件等）
    scenarios: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)

    stock: Mapped["Stock"] = relationship(back_populates="ai_notes")  # type: ignore
