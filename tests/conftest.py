"""
pytest 配置和通用 fixtures
"""

import os
import sys
from pathlib import Path

# 添加 backend 模組到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

import pytest
from pytest_asyncio import fixture


@pytest.fixture
def temp_pgdata_dir(tmp_path):
    """提供臨時的 PostgreSQL 資料目錄"""
    return str(tmp_path / "pgdata")


@pytest.fixture
def mock_settings():
    """提供測試用的 Settings 物件"""
    from app.config import Settings

    settings = Settings(
        DB_HOST=None,  # 使用嵌入式 PostgreSQL 模式
        DB_PORT=54330,
        DB_USER="postgres",
        DB_PASSWORD="",
        DB_NAME="money_printer",
        DATA_DIR=None,  # 使用預設 ~/.kingarmy/db/
        EMBEDDED_PG_PORT=54330,
    )
    return settings


@fixture(scope="function")
async def db_with_test_data():
    """
    提供含有測試資料的 AsyncSession
    用於 briefing 性能測試和功能驗證

    注意：此 fixture 需要實際的 PostgreSQL 資料庫連線
    測試應使用 test 資料庫或臨時資料庫進行隔離
    """
    import os
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from datetime import datetime, timedelta, date as date_type
    from app.database import Base
    from app.models import Stock, AnalysisResult, AiAnalysisNote, PortfolioHolding, User

    # 使用實際的 PostgreSQL 連線進行測試
    # 從環境變數讀取，或使用本機 postgres 測試用戶
    db_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres@localhost/money_printer_test"
    )

    engine = create_async_engine(db_url, echo=False)

    # 建立所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)  # 清除舊資料
        await conn.run_sync(Base.metadata.create_all)

    # 建立 session factory
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 建立測試資料
    async with async_session() as session:
        # 0. 建立測試用戶（Portfolio 需要 user_id）
        # ✓ 修正：User 需要 email, password_hash, display_name
        test_user = User(
            email="test@example.com",
            password_hash="hashed_password_123",
            display_name="Test User"
        )
        session.add(test_user)
        await session.flush()

        # 1. 建立股票
        stocks = [
            Stock(ticker="SPY", name="SPDR S&P 500 ETF", market="US"),
            Stock(ticker="QQQ", name="Invesco QQQ Trust", market="US"),
            Stock(ticker="SOXX", name="SOXX ETF", market="US"),
            Stock(ticker="AAPL", name="Apple Inc", market="US"),
            Stock(ticker="TSLA", name="Tesla Inc", market="US"),
        ]
        session.add_all(stocks)
        await session.flush()

        # 2. 建立分析結果
        # ✓ 修正：使用實際存在的欄位 (composite_score 代替 momentum_score，recommendation 代替 smc_trend)
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        analysis_results = [
            AnalysisResult(stock_id=stocks[0].id, analysis_date=today, composite_score=75.0, recommendation="推薦"),
            AnalysisResult(stock_id=stocks[0].id, analysis_date=yesterday, composite_score=73.0, recommendation="推薦"),
            AnalysisResult(stock_id=stocks[1].id, analysis_date=today, composite_score=70.0, recommendation="推薦"),
            AnalysisResult(stock_id=stocks[1].id, analysis_date=yesterday, composite_score=68.0, recommendation="觀察"),
            AnalysisResult(stock_id=stocks[2].id, analysis_date=today, composite_score=72.0, recommendation="推薦"),
            AnalysisResult(stock_id=stocks[2].id, analysis_date=yesterday, composite_score=71.0, recommendation="推薦"),
            AnalysisResult(stock_id=stocks[3].id, analysis_date=today, composite_score=65.0, recommendation="推薦"),
            AnalysisResult(stock_id=stocks[4].id, analysis_date=today, composite_score=45.0, recommendation="不推薦"),
        ]
        session.add_all(analysis_results)
        await session.flush()

        # 3. 建立持倉
        # ✓ 修正：shares → total_shares，加入 user_id 和 highest_price
        holdings = [
            PortfolioHolding(
                user_id=test_user.id,
                stock_id=stocks[3].id,
                total_shares=100.0,
                avg_cost=150.50,
                highest_price=155.00
            ),
            PortfolioHolding(
                user_id=test_user.id,
                stock_id=stocks[4].id,
                total_shares=50.0,
                avg_cost=200.00,
                highest_price=210.00
            ),
        ]
        session.add_all(holdings)
        await session.flush()

        # 4. 建立 AI 筆記
        ai_notes = [
            AiAnalysisNote(stock_id=stocks[3].id, analysis_type="individual", summary="看漲訊號"),
            AiAnalysisNote(stock_id=stocks[0].id, analysis_type="individual", summary="大盤穩定"),
        ]
        session.add_all(ai_notes)

        await session.commit()

    # 回傳 session 供測試使用
    async with async_session() as session:
        # 暴露引擎參考供測試使用（需要同步引擎進行查詢監聽）
        session._engine = engine
        yield session

    # 清理：刪除所有資料
    async with engine.begin() as conn:
        # ✓ 修正：驗證 DB 名稱，防止意外刪除生產資料庫
        if not db_url.endswith("_test"):
            raise RuntimeError(
                f"Safety check: database URL {db_url} does not end with '_test'. "
                "Cannot drop_all on non-test databases."
            )
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
