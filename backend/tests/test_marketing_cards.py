"""Tests for marketing cards CRUD functionality"""

import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models import MarketingCard, Site, User
from app.routers.marketing_cards import sanitize_card_content


@pytest.mark.asyncio
async def test_sanitize_card_content_removes_scripts():
    """Test that HTML content is sanitized (script tags removed)"""
    html_with_script = "<p>Hello <script>alert('xss')</script> World</p>"
    result = sanitize_card_content(html_with_script)
    assert "script" not in result.lower()
    assert "alert" not in result
    assert "Hello" in result
    assert "World" in result


@pytest.mark.asyncio
async def test_sanitize_card_content_empty():
    """Test sanitizing empty/None content"""
    assert sanitize_card_content(None) is None
    assert sanitize_card_content("") == ""


@pytest.mark.asyncio
async def test_sanitize_card_content_strips_all_tags():
    """Test that all HTML tags are removed"""
    html = "<b>Bold</b> <i>italic</i> <u>underline</u>"
    result = sanitize_card_content(html)
    assert "<" not in result
    assert ">" not in result
    assert "Bold" in result
    assert "italic" in result


@pytest.mark.asyncio
async def test_create_marketing_card(db_session: AsyncSession):
    """Test creating a marketing card in the database"""
    # Create a site first
    site = Site(id="test-site", name="Test Site")
    db_session.add(site)
    await db_session.flush()

    # Create card
    card = MarketingCard(
        id="test-card-1",
        site_id="test-site",
        title="Test Card",
        image_url="https://example.com/image.jpg",
        link_url="https://example.com",
        bg_color="#ff0000",
        text_color="#ffffff",
        content_type="banner",
        card_text_content="Test content",
    )
    db_session.add(card)
    await db_session.commit()

    # Verify it was created
    result = await db_session.execute(
        select(MarketingCard).where(MarketingCard.id == "test-card-1")
    )
    retrieved_card = result.scalar_one_or_none()
    assert retrieved_card is not None
    assert retrieved_card.title == "Test Card"
    assert retrieved_card.site_id == "test-site"


@pytest.mark.asyncio
async def test_list_marketing_cards_by_site(db_session: AsyncSession):
    """Test listing marketing cards filtered by site_id"""
    # Create sites
    site1 = Site(id="site-1", name="Site 1")
    site2 = Site(id="site-2", name="Site 2")
    db_session.add_all([site1, site2])
    await db_session.flush()

    # Create cards for different sites
    card1 = MarketingCard(
        id="card-site1-1",
        site_id="site-1",
        title="Card 1 for Site 1",
    )
    card2 = MarketingCard(
        id="card-site1-2",
        site_id="site-1",
        title="Card 2 for Site 1",
    )
    card3 = MarketingCard(
        id="card-site2-1",
        site_id="site-2",
        title="Card 1 for Site 2",
    )
    db_session.add_all([card1, card2, card3])
    await db_session.commit()

    # Query for site-1 cards
    result = await db_session.execute(
        select(MarketingCard).where(MarketingCard.site_id == "site-1")
    )
    cards = result.scalars().all()

    assert len(cards) == 2
    assert all(card.site_id == "site-1" for card in cards)


@pytest.mark.asyncio
async def test_delete_marketing_card(db_session: AsyncSession):
    """Test deleting a marketing card"""
    # Create site and card
    site = Site(id="test-site", name="Test Site")
    card = MarketingCard(
        id="test-card-delete",
        site_id="test-site",
        title="To Delete",
    )
    db_session.add_all([site, card])
    await db_session.commit()

    # Verify it exists
    result = await db_session.execute(
        select(MarketingCard).where(MarketingCard.id == "test-card-delete")
    )
    assert result.scalar_one_or_none() is not None

    # Delete it
    await db_session.delete(card)
    await db_session.commit()

    # Verify it's gone
    result = await db_session.execute(
        select(MarketingCard).where(MarketingCard.id == "test-card-delete")
    )
    assert result.scalar_one_or_none() is None
