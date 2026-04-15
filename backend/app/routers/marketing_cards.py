"""Marketing Cards CRUD API endpoints"""

import uuid
import bleach
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import MarketingCard, Site, User
from ..schemas.marketing_card import MarketingCardCreate, MarketingCardUpdate, MarketingCardOut
from ..services.auth import get_current_user

router = APIRouter(prefix="/marketing-cards", tags=["marketing_cards"])


def sanitize_card_content(text: Optional[str]) -> Optional[str]:
    """Remove all HTML from card text content, keep text only"""
    if not text:
        return text
    return bleach.clean(text, tags=[], strip=True)


async def get_marketing_card(
    card_id: str,
    db: AsyncSession,
) -> MarketingCard:
    """Helper to get a card and raise 404 if not found"""
    result = await db.execute(
        select(MarketingCard).where(MarketingCard.id == card_id)
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Marketing card not found")
    return card


async def get_site(site_id: str, db: AsyncSession) -> Site:
    """Helper to verify site exists"""
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.post(
    "",
    response_model=MarketingCardOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_marketing_card(
    req: MarketingCardCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new marketing card"""
    # Verify site exists
    await get_site(req.site_id, db)

    # Sanitize HTML content
    sanitized_content = sanitize_card_content(req.card_text_content)

    # Create card
    card = MarketingCard(
        id=str(uuid.uuid4()),
        site_id=req.site_id,
        title=req.title,
        image_url=req.image_url,
        link_url=req.link_url,
        bg_color=req.bg_color,
        text_color=req.text_color,
        content_type=req.content_type,
        card_text_content=sanitized_content,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)

    return MarketingCardOut.from_orm(card)


@router.get("", response_model=list[MarketingCardOut])
async def list_marketing_cards(
    site_id: str = Query(..., description="Filter by site_id"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List marketing cards for a specific site"""
    # Verify site exists
    await get_site(site_id, db)

    result = await db.execute(
        select(MarketingCard)
        .where(MarketingCard.site_id == site_id)
        .order_by(MarketingCard.created_at.desc())
    )
    cards = result.scalars().all()

    return [MarketingCardOut.from_orm(card) for card in cards]


@router.get("/{card_id}", response_model=MarketingCardOut)
async def get_marketing_card_endpoint(
    card_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific marketing card"""
    card = await get_marketing_card(card_id, db)
    return MarketingCardOut.from_orm(card)


@router.patch("/{card_id}", response_model=MarketingCardOut)
async def update_marketing_card(
    card_id: str,
    req: MarketingCardUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a marketing card"""
    card = await get_marketing_card(card_id, db)

    # Update fields
    if req.title is not None:
        card.title = req.title
    if req.image_url is not None:
        card.image_url = req.image_url
    if req.link_url is not None:
        card.link_url = req.link_url
    if req.bg_color is not None:
        card.bg_color = req.bg_color
    if req.text_color is not None:
        card.text_color = req.text_color
    if req.content_type is not None:
        card.content_type = req.content_type
    if req.card_text_content is not None:
        card.card_text_content = sanitize_card_content(req.card_text_content)

    await db.commit()
    await db.refresh(card)

    return MarketingCardOut.from_orm(card)


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_marketing_card(
    card_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a marketing card"""
    card = await get_marketing_card(card_id, db)
    await db.delete(card)
    await db.commit()
