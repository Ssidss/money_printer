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
        DB_HOST="localhost",
        DB_PORT=5432,
        DB_USER="postgres",
        DB_PASSWORD="",
        DB_NAME="money_printer",
    )
    return settings


@fixture(scope="function")
async def db_with_test_data():
    """
    提供含有測試資料的 AsyncSession
    用於 briefing 性能測試和功能驗證
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from datetime import datetime, timedelta
    from app.database import Base
    from app.models import Stock, AnalysisResult, AiAnalysisNote, PortfolioHolding

    # 使用記憶體 SQLite 進行測試（快速，不需外部 DB）
    # 如果需要 PostgreSQL 測試，改用 postgresql://... URL
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # 建立所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 建立 session factory
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 建立測試資料
    async with async_session() as session:
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
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        analysis_results = [
            AnalysisResult(stock_id=stocks[0].id, analysis_date=today, smc_trend="上升", momentum_score=75),
            AnalysisResult(stock_id=stocks[0].id, analysis_date=yesterday, smc_trend="上升", momentum_score=73),
            AnalysisResult(stock_id=stocks[1].id, analysis_date=today, smc_trend="上升", momentum_score=70),
            AnalysisResult(stock_id=stocks[1].id, analysis_date=yesterday, smc_trend="盤整", momentum_score=68),
            AnalysisResult(stock_id=stocks[2].id, analysis_date=today, smc_trend="上升", momentum_score=72),
            AnalysisResult(stock_id=stocks[2].id, analysis_date=yesterday, smc_trend="上升", momentum_score=71),
            AnalysisResult(stock_id=stocks[3].id, analysis_date=today, smc_trend="上升", momentum_score=65),
            AnalysisResult(stock_id=stocks[4].id, analysis_date=today, smc_trend="下降", momentum_score=45),
        ]
        session.add_all(analysis_results)
        await session.flush()

        # 3. 建立持倉
        holdings = [
            PortfolioHolding(stock_id=stocks[3].id, shares=100, avg_cost=150.50),
            PortfolioHolding(stock_id=stocks[4].id, shares=50, avg_cost=200.00),
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
        yield session

    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
