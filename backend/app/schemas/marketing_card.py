"""Pydantic schemas for MarketingCard"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class MarketingCardCreate(BaseModel):
    """Create request for marketing card"""
    site_id: str = Field(..., min_length=1, max_length=50)
    title: Optional[str] = Field(None, max_length=200)
    image_url: Optional[str] = Field(None, max_length=500)
    link_url: Optional[str] = Field(None, max_length=500)
    bg_color: str = Field(default="#ffffff", max_length=20)
    text_color: str = Field(default="#000000", max_length=20)
    content_type: str = Field(default="banner", max_length=50)
    card_text_content: Optional[str] = None  # Will be sanitized


class MarketingCardUpdate(BaseModel):
    """Partial update request for marketing card"""
    title: Optional[str] = Field(None, max_length=200)
    image_url: Optional[str] = Field(None, max_length=500)
    link_url: Optional[str] = Field(None, max_length=500)
    bg_color: Optional[str] = Field(None, max_length=20)
    text_color: Optional[str] = Field(None, max_length=20)
    content_type: Optional[str] = Field(None, max_length=50)
    card_text_content: Optional[str] = None  # Will be sanitized


class MarketingCardOut(BaseModel):
    """Response model for marketing card"""
    id: str
    site_id: str
    title: Optional[str]
    image_url: Optional[str]
    link_url: Optional[str]
    bg_color: str
    text_color: str
    content_type: str
    card_text_content: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
