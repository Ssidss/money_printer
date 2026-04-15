"""Migration for KINA-284: Create sites table (dependency for marketing_cards)"""

import sys
sys.path.insert(0, '.')
import asyncio
from sqlalchemy import text
from app.database import engine


async def migrate():
    """Create sites table idempotently"""

    async with engine.begin() as conn:
        # Check if table exists
        result = await conn.execute(
            text("""
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'sites'
            """)
        )

        if result.fetchone():
            print("✓ sites table already exists, skipping")
            return

        # Create table
        await conn.execute(text("""
            CREATE TABLE sites (
                id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """))
        print("✓ Created sites table")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
