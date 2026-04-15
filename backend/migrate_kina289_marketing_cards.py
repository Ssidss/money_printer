"""Migration for KINA-289: Create marketing_cards table"""

import sys
sys.path.insert(0, '.')
import asyncio
from sqlalchemy import text
from app.database import engine


async def migrate():
    """Create marketing_cards table idempotently"""

    async with engine.begin() as conn:
        # Check if table exists
        result = await conn.execute(
            text("""
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'marketing_cards'
            """)
        )

        if result.fetchone():
            print("✓ marketing_cards table already exists, skipping")
            return

        # Create table
        await conn.execute(text("""
            CREATE TABLE marketing_cards (
                id VARCHAR(50) PRIMARY KEY,
                site_id VARCHAR(50) NOT NULL,
                title VARCHAR(200),
                image_url VARCHAR(500),
                link_url VARCHAR(500),
                bg_color VARCHAR(20) NOT NULL DEFAULT '#ffffff',
                text_color VARCHAR(20) NOT NULL DEFAULT '#000000',
                content_type VARCHAR(50) NOT NULL DEFAULT 'banner',
                card_text_content TEXT,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                CONSTRAINT fk_marketing_cards_site_id
                    FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
            )
        """))
        print("✓ Created marketing_cards table")

        # Create index for site_id queries
        await conn.execute(text("""
            CREATE INDEX idx_marketing_cards_site_id ON marketing_cards(site_id)
        """))
        print("✓ Created index on site_id")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
