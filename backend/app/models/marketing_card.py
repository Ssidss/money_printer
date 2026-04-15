"""MarketingCard model for KINA-289"""

from __future__ import annotations
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from ..database import Base

if TYPE_CHECKING:
    from .site import Site

TIMESTAMPTZ = DateTime(timezone=True)


class MarketingCard(Base):
    """Marketing card model for displaying promotional content"""
    __tablename__ = "marketing_cards"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    site_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(200))
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    link_url: Mapped[Optional[str]] = mapped_column(String(500))
    bg_color: Mapped[str] = mapped_column(String(20), default="#ffffff")
    text_color: Mapped[str] = mapped_column(String(20), default="#000000")
    content_type: Mapped[str] = mapped_column(String(50), default="banner")
    card_text_content: Mapped[Optional[str]] = mapped_column(Text)  # sanitized HTML
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationship (avoid circular import with TYPE_CHECKING)
    site: Mapped[Optional[Site]] = relationship("Site", foreign_keys=[site_id])
