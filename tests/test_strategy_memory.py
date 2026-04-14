"""
KINA-277: 策略失誤分析 API + 記憶摘要結構測試
測試：
1. 策略失誤模式分析 API 端點
2. 按 smc_trend × recommendation 分組統計
3. Win rate 和 avg_return_pct 計算
4. Risk level 分類
5. Top failure patterns 識別（失敗率 > 50%）
6. 空資料時的合理預設值
"""

import pytest
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Stock, AiAnalysisNote
from app.routers.ai_notes import get_strategy_memory


@pytest.mark.asyncio
async def test_strategy_memory_empty_data(db_with_test_data):
    """驗證無已結束筆記時的響應"""
    session = db_with_test_data

    result = await get_strategy_memory(session)

    # 空資料時應該回傳合理預設值
    assert result["total_analyzed"] == 0
    assert result["patterns"] == []
    assert result["top_failure_patterns"] == []
    assert result["summary"]["best_condition"] is None
    assert result["summary"]["worst_condition"] is None


@pytest.mark.asyncio
async def test_strategy_memory_single_pattern(db_with_test_data):
    """驗證單一 smc_trend × recommendation 組合的統計"""
    session = db_with_test_data

    # 建立測試股票
    result = await session.execute(select(Stock).limit(1))
    stock = result.scalar_one()

    # 建立 10 個已結束的筆記（6 成功 + 4 失敗）
    for i in range(6):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="推薦",
            smc_trend="上升趨勢",
            summary=f"Test note {i}",
            entry_price=100.0,
            outcome_status="hit_target",
            actual_return_pct=5.0 + i,
            closed_price=105.0 + i,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    for i in range(4):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="推薦",
            smc_trend="上升趨勢",
            summary=f"Failed note {i}",
            entry_price=100.0,
            outcome_status="hit_stop",
            actual_return_pct=-3.0,
            closed_price=97.0,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    await session.commit()

    # 獲取策略記憶
    memory = await get_strategy_memory(session)

    assert memory["total_analyzed"] == 10
    assert len(memory["patterns"]) == 1

    pattern = memory["patterns"][0]
    assert pattern["smc_trend"] == "上升趨勢"
    assert pattern["recommendation"] == "推薦"
    assert pattern["sample_count"] == 10
    assert pattern["win_rate"] == 0.6  # 6/10
    assert pattern["risk_level"] == "medium"  # win_rate between 0.4 and 0.6


@pytest.mark.asyncio
async def test_strategy_memory_multiple_patterns(db_with_test_data):
    """驗證多個 smc_trend × recommendation 組合"""
    session = db_with_test_data

    result = await session.execute(select(Stock).limit(1))
    stock = result.scalar_one()

    # 組合 1: 上升 + 推薦 (8成功/2失敗 = 0.8 win rate)
    for i in range(8):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="推薦",
            smc_trend="上升趨勢",
            summary=f"Pattern 1 success {i}",
            entry_price=100.0,
            outcome_status="hit_target",
            actual_return_pct=6.0,
            closed_price=106.0,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    for i in range(2):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="推薦",
            smc_trend="上升趨勢",
            summary=f"Pattern 1 fail {i}",
            entry_price=100.0,
            outcome_status="hit_stop",
            actual_return_pct=-2.0,
            closed_price=98.0,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    # 組合 2: 盤整 + 強力推薦 (3成功/7失敗 = 0.3 win rate, failure rate = 0.7)
    for i in range(3):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="強力推薦",
            smc_trend="盤整",
            summary=f"Pattern 2 success {i}",
            entry_price=100.0,
            outcome_status="hit_target",
            actual_return_pct=4.0,
            closed_price=104.0,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    for i in range(7):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="強力推薦",
            smc_trend="盤整",
            summary=f"Pattern 2 fail {i}",
            entry_price=100.0,
            outcome_status="hit_stop",
            actual_return_pct=-4.0,
            closed_price=96.0,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    # 組合 3: 下降 + 觀察 (2成功/3失敗 = 0.4 win rate)
    for i in range(2):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="觀察",
            smc_trend="下降趨勢",
            summary=f"Pattern 3 success {i}",
            entry_price=100.0,
            outcome_status="hit_target",
            actual_return_pct=3.0,
            closed_price=103.0,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    for i in range(3):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="觀察",
            smc_trend="下降趨勢",
            summary=f"Pattern 3 fail {i}",
            entry_price=100.0,
            outcome_status="hit_stop",
            actual_return_pct=-3.5,
            closed_price=96.5,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    await session.commit()

    memory = await get_strategy_memory(session)

    assert memory["total_analyzed"] == 20
    assert len(memory["patterns"]) == 3

    # 驗證風險等級
    pattern_map = {
        (p["smc_trend"], p["recommendation"]): p
        for p in memory["patterns"]
    }

    # 上升 + 推薦: win_rate = 0.8 → low risk
    assert pattern_map[("上升趨勢", "推薦")]["risk_level"] == "low"

    # 盤整 + 強力推薦: win_rate = 0.3 → high risk
    assert pattern_map[("盤整", "強力推薦")]["risk_level"] == "high"

    # 下降 + 觀察: win_rate = 0.4 → high risk (邊界 < 0.4)
    assert pattern_map[("下降趨勢", "觀察")]["risk_level"] == "high"


@pytest.mark.asyncio
async def test_strategy_memory_top_failure_patterns(db_with_test_data):
    """驗證 top_failure_patterns 只包含失敗率 > 50% 的組合"""
    session = db_with_test_data

    result = await session.execute(select(Stock).limit(1))
    stock = result.scalar_one()

    # 高失敗率組合: 盤整 + 強力推薦 (2成功/8失敗 = 失敗率 0.8)
    for i in range(2):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="強力推薦",
            smc_trend="盤整",
            summary=f"High fail success {i}",
            entry_price=100.0,
            outcome_status="hit_target",
            actual_return_pct=5.0,
            closed_price=105.0,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    for i in range(8):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="強力推薦",
            smc_trend="盤整",
            summary=f"High fail {i}",
            entry_price=100.0,
            outcome_status="hit_stop",
            actual_return_pct=-5.2,
            closed_price=94.8,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    # 低失敗率組合: 上升 + 推薦 (9成功/1失敗 = 失敗率 0.1)
    for i in range(9):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="推薦",
            smc_trend="上升趨勢",
            summary=f"Low fail success {i}",
            entry_price=100.0,
            outcome_status="hit_target",
            actual_return_pct=6.0,
            closed_price=106.0,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    for i in range(1):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="推薦",
            smc_trend="上升趨勢",
            summary=f"Low fail {i}",
            entry_price=100.0,
            outcome_status="hit_stop",
            actual_return_pct=-2.0,
            closed_price=98.0,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    await session.commit()

    memory = await get_strategy_memory(session)

    # 只有失敗率 > 50% 的組合會出現在 top_failure_patterns
    assert len(memory["top_failure_patterns"]) == 1

    failure_pattern = memory["top_failure_patterns"][0]
    assert failure_pattern["condition"] == "盤整 + 強力推薦"
    assert failure_pattern["failure_rate"] == 0.8
    assert failure_pattern["avg_loss_pct"] == -5.2
    assert "warning" in failure_pattern


@pytest.mark.asyncio
async def test_strategy_memory_summary(db_with_test_data):
    """驗證 summary 中的 best/worst condition"""
    session = db_with_test_data

    result = await session.execute(select(Stock).limit(1))
    stock = result.scalar_one()

    # 最佳: 上升 + 推薦 (9成功/1失敗 = win_rate 0.9)
    for i in range(9):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="推薦",
            smc_trend="上升趨勢",
            summary=f"Best {i}",
            entry_price=100.0,
            outcome_status="hit_target",
            actual_return_pct=8.0,
            closed_price=108.0,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    for i in range(1):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="推薦",
            smc_trend="上升趨勢",
            summary=f"Best fail {i}",
            entry_price=100.0,
            outcome_status="hit_stop",
            actual_return_pct=-2.0,
            closed_price=98.0,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    # 最差: 盤整 + 強力推薦 (1成功/9失敗 = win_rate 0.1)
    for i in range(1):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="強力推薦",
            smc_trend="盤整",
            summary=f"Worst success {i}",
            entry_price=100.0,
            outcome_status="hit_target",
            actual_return_pct=5.0,
            closed_price=105.0,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    for i in range(9):
        note = AiAnalysisNote(
            stock_id=stock.id,
            analysis_type="individual",
            recommendation="強力推薦",
            smc_trend="盤整",
            summary=f"Worst {i}",
            entry_price=100.0,
            outcome_status="hit_stop",
            actual_return_pct=-5.0,
            closed_price=95.0,
            closed_at=datetime.utcnow(),
        )
        session.add(note)

    await session.commit()

    memory = await get_strategy_memory(session)

    summary = memory["summary"]
    assert summary["best_condition"] == "上升趨勢 + 推薦"
    assert summary["worst_condition"] == "盤整 + 強力推薦"


@pytest.mark.asyncio
async def test_strategy_memory_ignore_pending_notes(db_with_test_data):
    """驗證 pending 筆記被忽略"""
    session = db_with_test_data

    result = await session.execute(select(Stock).limit(1))
    stock = result.scalar_one()

    # 建立已結束的筆記
    note_completed = AiAnalysisNote(
        stock_id=stock.id,
        analysis_type="individual",
        recommendation="推薦",
        smc_trend="上升趨勢",
        summary="Completed",
        entry_price=100.0,
        outcome_status="hit_target",
        actual_return_pct=5.0,
        closed_price=105.0,
        closed_at=datetime.utcnow(),
    )
    session.add(note_completed)

    # 建立 pending 筆記
    note_pending = AiAnalysisNote(
        stock_id=stock.id,
        analysis_type="individual",
        recommendation="推薦",
        smc_trend="上升趨勢",
        summary="Pending",
        entry_price=100.0,
        outcome_status="pending",
    )
    session.add(note_pending)

    await session.commit()

    memory = await get_strategy_memory(session)

    # 只應該統計 1 個（completed）
    assert memory["total_analyzed"] == 1
    assert len(memory["patterns"]) == 1
    assert memory["patterns"][0]["sample_count"] == 1


@pytest.mark.asyncio
async def test_strategy_memory_limit_failure_patterns(db_with_test_data):
    """驗證 top_failure_patterns 最多返回 5 筆"""
    session = db_with_test_data

    result = await session.execute(select(Stock).limit(1))
    stock = result.scalar_one()

    # 建立 6 個高失敗率組合
    for combo in range(6):
        for i in range(6):
            note = AiAnalysisNote(
                stock_id=stock.id,
                analysis_type="individual",
                recommendation=["推薦", "強力推薦", "觀察", "不推薦", "推薦", "觀察"][combo],
                smc_trend=["上升趨勢", "盤整", "下降趨勢", "上升趨勢", "盤整", "下降趨勢"][combo],
                summary=f"Fail {combo} {i}",
                entry_price=100.0,
                outcome_status="hit_stop",
                actual_return_pct=-3.0,
                closed_price=97.0,
                closed_at=datetime.utcnow(),
            )
            session.add(note)

    await session.commit()

    memory = await get_strategy_memory(session)

    # 應該最多返回 5 筆
    assert len(memory["top_failure_patterns"]) <= 5
