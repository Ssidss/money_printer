"""
測試 memory-context endpoint (KINA-278)
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.main import app
from app.database import get_db
from app.models.stock import Stock
from app.models.ai_note import AiAnalysisNote


@pytest.fixture
async def client():
    """FastAPI TestClient"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def db_session():
    """Database session fixture"""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        yield session


@pytest.mark.asyncio
async def test_memory_context_no_data(client: AsyncClient, db_session: AsyncSession):
    """測試：無歷史數據時"""
    response = await client.get(
        "/api/v1/ai-notes/memory-context",
        params={
            "smc_trend": "上升趨勢",
            "recommendation_hint": "推薦"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_memory"] is False
    assert data["confidence_adjustment"] == 0.0
    assert data["historical_pattern"] is None


@pytest.mark.asyncio
async def test_memory_context_insufficient_sample(
    client: AsyncClient, db_session: AsyncSession
):
    """測試：樣本數不足（< 5）"""
    # 創建 test stock
    stock = Stock(ticker="TEST", name="Test Stock", market="US")
    db_session.add(stock)
    await db_session.commit()

    # 創建 3 筆 AI 分析筆記（樣本不足）
    for i in range(3):
        note = AiAnalysisNote(
            stock_id=stock.id,
            recommendation="推薦",
            smc_trend="上升趨勢",
            outcome_status="hit_target" if i < 2 else "hit_stop",
            actual_return_pct=2.5 if i < 2 else -1.5,
            created_by=None,
        )
        db_session.add(note)
    await db_session.commit()

    response = await client.get(
        "/api/v1/ai-notes/memory-context",
        params={
            "smc_trend": "上升趨勢",
            "recommendation_hint": "推薦"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_memory"] is False
    assert len(data["warnings"]) > 0
    assert "樣本數不足" in data["warnings"][0]


@pytest.mark.asyncio
async def test_memory_context_sufficient_sample_good_performance(
    client: AsyncClient, db_session: AsyncSession
):
    """測試：樣本足夠且績效良好（勝率 > 60%）"""
    # 創建 test stock
    stock = Stock(ticker="TEST2", name="Test Stock 2", market="US")
    db_session.add(stock)
    await db_session.commit()

    # 創建 8 筆 AI 分析筆記（勝率 75%）
    for i in range(8):
        note = AiAnalysisNote(
            stock_id=stock.id,
            recommendation="推薦",
            smc_trend="上升趨勢",
            outcome_status="hit_target" if i < 6 else "hit_stop",
            actual_return_pct=3.5 if i < 6 else -2.0,
            created_by=None,
        )
        db_session.add(note)
    await db_session.commit()

    response = await client.get(
        "/api/v1/ai-notes/memory-context",
        params={
            "smc_trend": "上升趨勢",
            "recommendation_hint": "推薦"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_memory"] is True
    assert data["historical_pattern"]["win_rate"] == 0.75
    assert data["historical_pattern"]["sample_count"] == 8
    # confidence_adjustment = (0.75 - 0.5) * 0.3 = 0.075
    assert data["confidence_adjustment"] == 0.07  # rounded


@pytest.mark.asyncio
async def test_memory_context_low_win_rate(
    client: AsyncClient, db_session: AsyncSession
):
    """測試：勝率低於 40%，應該生成警告"""
    # 創建 test stock
    stock = Stock(ticker="TEST3", name="Test Stock 3", market="US")
    db_session.add(stock)
    await db_session.commit()

    # 創建 5 筆 AI 分析筆記（勝率 20%）
    for i in range(5):
        note = AiAnalysisNote(
            stock_id=stock.id,
            recommendation="推薦",
            smc_trend="盤整",
            outcome_status="hit_target" if i == 0 else "hit_stop",
            actual_return_pct=1.5 if i == 0 else -3.5,
            created_by=None,
        )
        db_session.add(note)
    await db_session.commit()

    response = await client.get(
        "/api/v1/ai-notes/memory-context",
        params={
            "smc_trend": "盤整",
            "recommendation_hint": "推薦"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_memory"] is True
    assert data["historical_pattern"]["win_rate"] == 0.2
    assert len(data["warnings"]) > 0
    assert "勝率" in data["warnings"][0]


@pytest.mark.asyncio
async def test_memory_context_negative_return(
    client: AsyncClient, db_session: AsyncSession
):
    """測試：平均回報為負（< -3%），應該生成警告"""
    # 創建 test stock
    stock = Stock(ticker="TEST4", name="Test Stock 4", market="US")
    db_session.add(stock)
    await db_session.commit()

    # 創建 5 筆 AI 分析筆記（平均回報 -4%）
    for i in range(5):
        note = AiAnalysisNote(
            stock_id=stock.id,
            recommendation="觀察",
            smc_trend="下降趨勢",
            outcome_status="hit_target" if i < 2 else "hit_stop",
            actual_return_pct=2.0 if i < 2 else -6.0,
            created_by=None,
        )
        db_session.add(note)
    await db_session.commit()

    response = await client.get(
        "/api/v1/ai-notes/memory-context",
        params={
            "smc_trend": "下降趨勢",
            "recommendation_hint": "觀察"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_memory"] is True
    assert len(data["warnings"]) > 0
    assert "平均回報" in data["warnings"][0]


@pytest.mark.asyncio
async def test_memory_context_no_matching_pattern(
    client: AsyncClient, db_session: AsyncSession
):
    """測試：無匹配的歷史模式"""
    # 創建 test stock
    stock = Stock(ticker="TEST5", name="Test Stock 5", market="US")
    db_session.add(stock)
    await db_session.commit()

    # 創建 5 筆 AI 分析筆記（上升趨勢 + 推薦）
    for i in range(5):
        note = AiAnalysisNote(
            stock_id=stock.id,
            recommendation="推薦",
            smc_trend="上升趨勢",
            outcome_status="hit_target",
            actual_return_pct=3.0,
            created_by=None,
        )
        db_session.add(note)
    await db_session.commit()

    # 查詢不同的組合
    response = await client.get(
        "/api/v1/ai-notes/memory-context",
        params={
            "smc_trend": "盤整",
            "recommendation_hint": "強力推薦"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_memory"] is False
    assert "無該推薦等級" in data["context_summary"]
