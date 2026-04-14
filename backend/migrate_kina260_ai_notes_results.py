"""Migration: Add AI notes results tracking columns (KINA-260)

Adds outcome_status, actual_return_pct, closed_price, closed_at columns
to ai_analysis_notes table for trade result tracking.
"""
import sys
sys.path.insert(0, '.')
import asyncio
from sqlalchemy import text
from app.database import engine


async def migrate():
    async with engine.begin() as conn:
        # 1. Add outcome_status column
        col_exists = await conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'ai_analysis_notes' AND column_name = 'outcome_status'"
        ))
        if not col_exists.fetchone():
            await conn.execute(text(
                "ALTER TABLE ai_analysis_notes "
                "ADD COLUMN outcome_status VARCHAR(20) NOT NULL DEFAULT 'pending'"
            ))
            print("ai_analysis_notes: outcome_status column added")
        else:
            print("ai_analysis_notes: outcome_status column already exists")

        # 2. Add actual_return_pct column
        col_exists = await conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'ai_analysis_notes' AND column_name = 'actual_return_pct'"
        ))
        if not col_exists.fetchone():
            await conn.execute(text(
                "ALTER TABLE ai_analysis_notes "
                "ADD COLUMN actual_return_pct NUMERIC(6, 2)"
            ))
            print("ai_analysis_notes: actual_return_pct column added")
        else:
            print("ai_analysis_notes: actual_return_pct column already exists")

        # 3. Add closed_price column
        col_exists = await conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'ai_analysis_notes' AND column_name = 'closed_price'"
        ))
        if not col_exists.fetchone():
            await conn.execute(text(
                "ALTER TABLE ai_analysis_notes "
                "ADD COLUMN closed_price NUMERIC(14, 4)"
            ))
            print("ai_analysis_notes: closed_price column added")
        else:
            print("ai_analysis_notes: closed_price column already exists")

        # 4. Add closed_at column
        col_exists = await conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'ai_analysis_notes' AND column_name = 'closed_at'"
        ))
        if not col_exists.fetchone():
            await conn.execute(text(
                "ALTER TABLE ai_analysis_notes "
                "ADD COLUMN closed_at TIMESTAMP WITH TIME ZONE"
            ))
            print("ai_analysis_notes: closed_at column added")
        else:
            print("ai_analysis_notes: closed_at column already exists")

    print("\nMigration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
