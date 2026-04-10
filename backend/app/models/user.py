from __future__ import annotations
"""
User Model — 多租戶使用者
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB

TIMESTAMPTZ = DateTime(timezone=True)

from ..database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    # 個人化設定（通知偏好、UI 偏好等）
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=text("NOW()"), onupdate=datetime.utcnow)

    # relationships
    holdings: Mapped[list["PortfolioHolding"]] = relationship(back_populates="user")  # type: ignore
    transactions: Mapped[list["PortfolioTransaction"]] = relationship(back_populates="user")  # type: ignore
