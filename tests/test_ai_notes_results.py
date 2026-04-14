"""
KINA-260: AI Analysis Notes 結果追蹤測試
測試：
1. Model 新欄位 (outcome_status, actual_return_pct, closed_price, closed_at)
2. 結果回填邏輯 (hit_target, hit_stop, expired)
3. Performance 統計 API
4. 現有 API 不受影響
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Stock, AiAnalysisNote, PriceHistory, User
from app.routers.ai_notes import AiNoteCreate, AiNoteUpdate
from app.services.ai_note_result_backfill import backfill_ai_note_results


@pytest.mark.asyncio
async def test_ai_note_model_has_outcome_fields(db_with_test_data):
    """驗證 AiAnalysisNote model 包含新欄位"""
    async with db_with_test_data._engine.begin() as conn:
        # 檢查表結構
        from sqlalchemy import inspect
        inspector = inspect(AiAnalysisNote)
        columns = {c.name for c in inspector.columns}

    assert "outcome_status" in columns, "outcome_status 欄位缺失"
    assert "actual_return_pct" in columns, "actual_return_pct 欄位缺失"
    assert "closed_price" in columns, "closed_price 欄位缺失"
    assert "closed_at" in columns, "closed_at 欄位缺失"


@pytest.mark.asyncio
async def test_ai_note_default_outcome_status(db_with_test_data):
    """驗證新建立的 AI note outcome_status 預設為 pending"""
    session = db_with_test_data

    # 獲取第一支股票
    result = await session.execute(select(Stock).limit(1))
    stock = result.scalar_one()

    # 建立新的 AI note
    note = AiAnalysisNote(
        stock_id=stock.id,
        analysis_type="individual",
        recommendation="推薦",
        action="買入",
        summary="Test note",
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
    )
    session.add(note)
    await session.commit()

    # 驗證 outcome_status 為 pending
    assert note.outcome_status == "pending"
    assert note.actual_return_pct is None
    assert note.closed_price is None
    assert note.closed_at is None


@pytest.mark.asyncio
async def test_ai_note_update_outcome(db_with_test_data):
    """驗證可以更新 AI note 的交易結果"""
    session = db_with_test_data

    # 獲取現有的 AI note
    result = await session.execute(select(AiAnalysisNote).limit(1))
    note = result.scalar_one()

    # 更新交易結果
    note.outcome_status = "hit_target"
    note.closed_price = 110.0
    note.actual_return_pct = 5.5
    note.closed_at = datetime.utcnow()

    await session.commit()
    await session.refresh(note)

    assert note.outcome_status == "hit_target"
    assert float(note.actual_return_pct) == 5.5
    assert float(note.closed_price) == 110.0
    assert note.closed_at is not None


@pytest.mark.asyncio
async def test_backfill_ai_note_hit_target(db_with_test_data):
    """驗證結果回填邏輯 — hit_target"""
    session = db_with_test_data

    # 建立股票和 AI note
    result = await session.execute(select(Stock).limit(1))
    stock = result.scalar_one()

    note = AiAnalysisNote(
        stock_id=stock.id,
        analysis_type="individual",
        recommendation="推薦",
        action="買入",
        summary="Test backfill",
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
    )
    session.add(note)
    await session.commit()

    # 新增價格數據 >= target_price
    price = PriceHistory(
        stock_id=stock.id,
        date=datetime.utcnow().date(),
        close=112.0,
    )
    session.add(price)
    await session.commit()

    # 執行回填
    stats = await backfill_ai_note_results(session)

    # 驗證結果
    assert stats["hit_target"] >= 1
    await session.refresh(note)
    assert note.outcome_status == "hit_target"
    assert float(note.closed_price) == 112.0
    assert note.actual_return_pct is not None


@pytest.mark.asyncio
async def test_backfill_ai_note_hit_stop(db_with_test_data):
    """驗證結果回填邏輯 — hit_stop"""
    session = db_with_test_data

    # 建立股票和 AI note
    result = await session.execute(select(Stock).limit(1))
    stock = result.scalar_one()

    note = AiAnalysisNote(
        stock_id=stock.id,
        analysis_type="individual",
        recommendation="推薦",
        action="買入",
        summary="Test stop loss",
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
    )
    session.add(note)
    await session.commit()

    # 新增價格數據 <= stop_price
    price = PriceHistory(
        stock_id=stock.id,
        date=datetime.utcnow().date(),
        close=93.0,
    )
    session.add(price)
    await session.commit()

    # 執行回填
    stats = await backfill_ai_note_results(session)

    # 驗證結果
    assert stats["hit_stop"] >= 1
    await session.refresh(note)
    assert note.outcome_status == "hit_stop"
    assert float(note.closed_price) == 93.0
    assert note.actual_return_pct is not None


@pytest.mark.asyncio
async def test_backfill_ai_note_expired(db_with_test_data):
    """驗證結果回填邏輯 — expired (>30 days)"""
    session = db_with_test_data

    # 建立股票和 AI note（建立時間為 31 天前）
    result = await session.execute(select(Stock).limit(1))
    stock = result.scalar_one()

    old_time = datetime.utcnow() - timedelta(days=31)
    note = AiAnalysisNote(
        stock_id=stock.id,
        analysis_type="individual",
        recommendation="推薦",
        action="買入",
        summary="Test expired",
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
        created_at=old_time,
    )
    session.add(note)
    await session.commit()

    # 執行回填
    stats = await backfill_ai_note_results(session)

    # 驗證結果
    assert stats["expired"] >= 1
    await session.refresh(note)
    assert note.outcome_status == "expired"
    assert note.closed_at is not None


@pytest.mark.asyncio
async def test_performance_api_empty(db_with_test_data):
    """驗證 /api/v1/ai-notes/performance 在無已結束筆記時的響應"""
    from app.routers.ai_notes import get_ai_notes_performance

    result = await get_ai_notes_performance(db_with_test_data)

    assert result["total_notes"] >= 0
    assert result["completed_notes"] == 0
    assert result["stats"]["win_rate"] is None
    assert result["stats"]["avg_return_pct"] is None


@pytest.mark.asyncio
async def test_performance_api_with_data(db_with_test_data):
    """驗證 /api/v1/ai-notes/performance 返回正確統計"""
    from app.routers.ai_notes import get_ai_notes_performance

    session = db_with_test_data

    # 建立測試資料
    result = await session.execute(select(Stock).limit(1))
    stock = result.scalar_one()

    # 建立已結束的筆記
    completed_note = AiAnalysisNote(
        stock_id=stock.id,
        analysis_type="individual",
        recommendation="推薦",
        action="買入",
        summary="Test completed",
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
        outcome_status="hit_target",
        actual_return_pct=5.0,
        closed_price=105.0,
        closed_at=datetime.utcnow(),
    )
    session.add(completed_note)
    await session.commit()

    # 獲取績效統計
    perf = await get_ai_notes_performance(session)

    assert perf["total_notes"] >= 1
    assert perf["completed_notes"] >= 1
    assert perf["stats"]["hit_target"] >= 1
    assert perf["stats"]["win_rate"] is not None
    assert perf["stats"]["avg_return_pct"] is not None


@pytest.mark.asyncio
async def test_existing_ai_notes_api_unaffected(db_with_test_data):
    """驗證現有 AI notes API (POST, GET) 不受影響"""
    from app.routers.ai_notes import create_ai_note, list_ai_notes

    session = db_with_test_data

    # 獲取第一支股票
    result = await session.execute(select(Stock).limit(1))
    stock = result.scalar_one()

    # 建立 AI note（舊 API）
    body = AiNoteCreate(
        ticker=stock.ticker,
        analysis_type="individual",
        recommendation="強力推薦",
        action="買入",
        summary="Test existing API",
        price_at_analysis=150.0,
        composite_score=75.0,
        smc_trend="上升",
        entry_price=150.0,
        stop_price=145.0,
        target_price=160.0,
        rr_ratio=2.0,
    )

    # POST 應該正常工作
    response = await create_ai_note(body, session)
    assert "id" in response

    # GET 應該能列出筆記
    notes = await list_ai_notes(None, None, 20, session)
    assert len(notes) > 0

    # 驗證新欄位有預設值
    last_note = notes[0]
    assert last_note["outcome_status"] == "pending"
    assert last_note["actual_return_pct"] is None
