"""Migration: Add multi-tenant support (users table, user_id on portfolio, created_by on backtest/notes)"""
import sys; sys.path.insert(0, '.')
import asyncio
import bcrypt
from sqlalchemy import text
from app.database import engine, Base
from app.models import (
    User, Stock, PriceHistory, AnalysisResult, NewsArticle,
    PortfolioTransaction, PortfolioHolding, BacktestResult, AiAnalysisNote,
    StrategyProfile, BacktestResultV2, BacktestTrade, BacktestEquity, StrategySignal,
)


async def migrate():
    async with engine.begin() as conn:
        # 1. Drop 剛用 raw SQL 建的不完整 users 表，重新讓 SQLAlchemy 建
        await conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
        print("dropped old users table")

        # 2. 用 SQLAlchemy metadata 建所有表
        await conn.run_sync(Base.metadata.create_all)
        print("all tables synced via SQLAlchemy")

        # 3. 建預設 admin 用戶
        pw_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
        await conn.execute(text(
            "INSERT INTO users (email, password_hash, display_name, is_active, is_admin) "
            "VALUES (:email, :pw, :name, TRUE, TRUE) "
            "ON CONFLICT (email) DO NOTHING"
        ), {"email": "admin@moneyprinter.local", "pw": pw_hash, "name": "Admin"})
        r = await conn.execute(text("SELECT id FROM users WHERE email = 'admin@moneyprinter.local'"))
        default_uid = r.scalar()
        print(f"admin user created (id={default_uid})")

        # 4. portfolio_holdings: 加 user_id
        col_exists = await conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'portfolio_holdings' AND column_name = 'user_id'"
        ))
        if not col_exists.fetchone():
            await conn.execute(text(
                "ALTER TABLE portfolio_holdings "
                "DROP CONSTRAINT IF EXISTS portfolio_holdings_stock_id_key"
            ))
            await conn.execute(text(
                f"ALTER TABLE portfolio_holdings "
                f"ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE DEFAULT {default_uid}"
            ))
            await conn.execute(text("ALTER TABLE portfolio_holdings ALTER COLUMN user_id SET NOT NULL"))
            await conn.execute(text("ALTER TABLE portfolio_holdings ALTER COLUMN user_id DROP DEFAULT"))
            # 新的 unique constraint: (user_id, stock_id)
            await conn.execute(text(
                "ALTER TABLE portfolio_holdings "
                "ADD CONSTRAINT uq_holding_user_stock UNIQUE (user_id, stock_id)"
            ))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_holding_user ON portfolio_holdings (user_id)"))
            print("portfolio_holdings: user_id migrated")
        else:
            print("portfolio_holdings: user_id already exists")

        # 5. portfolio_transactions: 加 user_id
        col_exists = await conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'portfolio_transactions' AND column_name = 'user_id'"
        ))
        if not col_exists.fetchone():
            await conn.execute(text(
                f"ALTER TABLE portfolio_transactions "
                f"ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE DEFAULT {default_uid}"
            ))
            await conn.execute(text("ALTER TABLE portfolio_transactions ALTER COLUMN user_id SET NOT NULL"))
            await conn.execute(text("ALTER TABLE portfolio_transactions ALTER COLUMN user_id DROP DEFAULT"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_txn_user ON portfolio_transactions (user_id)"))
            print("portfolio_transactions: user_id migrated")
        else:
            print("portfolio_transactions: user_id already exists")

        # 6. backtest_results_v2: 加 created_by (nullable)
        col_exists = await conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'backtest_results_v2' AND column_name = 'created_by'"
        ))
        if not col_exists.fetchone():
            await conn.execute(text(
                "ALTER TABLE backtest_results_v2 "
                "ADD COLUMN created_by INTEGER REFERENCES users(id) ON DELETE SET NULL"
            ))
            print("backtest_results_v2: created_by added")
        else:
            print("backtest_results_v2: created_by already exists")

        # 7. ai_analysis_notes: 加 created_by (nullable)
        col_exists = await conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'ai_analysis_notes' AND column_name = 'created_by'"
        ))
        if not col_exists.fetchone():
            await conn.execute(text(
                "ALTER TABLE ai_analysis_notes "
                "ADD COLUMN created_by INTEGER REFERENCES users(id) ON DELETE SET NULL"
            ))
            print("ai_analysis_notes: created_by added")
        else:
            print("ai_analysis_notes: created_by already exists")

    print("\nMigration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
