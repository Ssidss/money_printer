from __future__ import annotations
"""
AI 分析筆記 API
- POST   /ai-notes                      建立 AI 分析筆記
- GET    /ai-notes                      取得所有筆記（可過濾 ticker）
- GET    /ai-notes/latest               取得每支股票最新一筆 AI 筆記（用於清單頁顯示）
- GET    /ai-notes/strategy-memory      策略失誤分析 + 記憶摘要結構（KINA-277）
- GET    /ai-notes/{id}                 取得單筆筆記
- DELETE /ai-notes/{id}                 刪除筆記
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.stock import Stock
from ..models.user import User
from ..models.ai_note import AiAnalysisNote
from ..services.auth import get_optional_user
from ..services.ai_note_result_backfill import backfill_ai_note_results

router = APIRouter(prefix="/ai-notes", tags=["ai-notes"])


# ── Pydantic Response Models ────────────────────────────────────────


class StrategyPattern(BaseModel):
    """特定 smc_trend × recommendation 組合的績效統計"""
    smc_trend: str = Field(..., description="SMC 趨勢（上升趨勢 / 盤整 / 下降趨勢）")
    recommendation: str = Field(..., description="推薦等級（強力推薦 / 推薦 / 觀察 / 不推薦）")
    win_rate: float = Field(..., ge=0, le=1, description="勝率 = hit_target / total_sample")
    avg_return_pct: float = Field(..., description="平均回報百分比")
    sample_count: int = Field(..., ge=0, description="樣本數量")
    risk_level: str = Field(..., description="風險等級（low/medium/high）")


class FailurePattern(BaseModel):
    """失敗率高於 50% 的策略組合警告"""
    condition: str = Field(..., description="條件描述（smc_trend + recommendation）")
    failure_rate: float = Field(..., ge=0, le=1, description="失敗率 = (hit_stop + expired) / total")
    avg_loss_pct: float = Field(..., description="平均虧損百分比")
    warning: str = Field(..., description="警告訊息")


class StrategySummary(BaseModel):
    """策略分析摘要"""
    best_condition: Optional[str] = Field(None, description="最佳的策略組合條件")
    worst_condition: Optional[str] = Field(None, description="最差的策略組合條件")


class StrategyMemoryResponse(BaseModel):
    """策略記憶分析結果"""
    patterns: List[StrategyPattern] = Field(..., description="按 smc_trend × recommendation 分組的績效統計")
    top_failure_patterns: List[FailurePattern] = Field(..., description="失敗率 > 50% 的頂層組合（最多 5 筆）")
    total_analyzed: int = Field(..., ge=0, description="分析的已結束筆記總數")
    summary: StrategySummary = Field(..., description="策略分析摘要")


class AiNoteCreate(BaseModel):
    ticker: str
    analysis_type: str = "individual"       # individual / top_pick / portfolio / watchlist
    recommendation: str                     # 強力推薦 / 推薦 / 觀察 / 不推薦
    action: Optional[str] = None            # 買入 / 加碼 / 持有 / 減倉 / 出場 / 觀望
    summary: str                            # Markdown 分析內容
    price_at_analysis: Optional[float] = None
    composite_score: Optional[float] = None
    smc_trend: Optional[str] = None
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    rr_ratio: Optional[float] = None
    scenarios: Optional[dict] = None        # 情境分析 JSON


class AiNoteUpdate(BaseModel):
    """用於回填實際結果的 patch"""
    outcome_status: str                     # pending / hit_target / hit_stop / expired
    actual_return_pct: Optional[float] = None
    closed_price: Optional[float] = None
    closed_at: Optional[datetime] = None


def _note_to_dict(note: AiAnalysisNote, ticker: str | None = None) -> dict:
    return {
        "id": note.id,
        "stock_id": note.stock_id,
        "ticker": ticker,
        "analysis_type": note.analysis_type,
        "recommendation": note.recommendation,
        "action": note.action,
        "summary": note.summary,
        "price_at_analysis": float(note.price_at_analysis) if note.price_at_analysis else None,
        "composite_score": float(note.composite_score) if note.composite_score else None,
        "smc_trend": note.smc_trend,
        "entry_price": float(note.entry_price) if note.entry_price else None,
        "stop_price": float(note.stop_price) if note.stop_price else None,
        "target_price": float(note.target_price) if note.target_price else None,
        "rr_ratio": float(note.rr_ratio) if note.rr_ratio else None,
        "scenarios": note.scenarios,
        "outcome_status": note.outcome_status,
        "actual_return_pct": float(note.actual_return_pct) if note.actual_return_pct else None,
        "closed_price": float(note.closed_price) if note.closed_price else None,
        "closed_at": note.closed_at.isoformat() if note.closed_at else None,
        "created_by": note.created_by,
        "created_at": note.created_at.isoformat() if note.created_at else None,
    }


@router.post("")
async def create_ai_note(
    body: AiNoteCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """建立 AI 分析筆記"""
    ticker = body.ticker.upper()
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404, f"股票 {ticker} 不存在")

    note = AiAnalysisNote(
        stock_id=stock.id,
        analysis_type=body.analysis_type,
        recommendation=body.recommendation,
        action=body.action,
        summary=body.summary,
        price_at_analysis=body.price_at_analysis,
        composite_score=body.composite_score,
        smc_trend=body.smc_trend,
        entry_price=body.entry_price,
        stop_price=body.stop_price,
        target_price=body.target_price,
        rr_ratio=body.rr_ratio,
        scenarios=body.scenarios,
        created_by=user.id if user else None,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)

    return {"message": f"AI 分析筆記已建立 ({ticker})", "id": note.id}


@router.get("")
async def list_ai_notes(
    ticker: Optional[str] = None,
    analysis_type: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """列出 AI 分析筆記，可按 ticker 或 analysis_type 過濾"""
    q = select(AiAnalysisNote, Stock.ticker).join(Stock)

    if ticker:
        q = q.where(Stock.ticker == ticker.upper())
    if analysis_type:
        q = q.where(AiAnalysisNote.analysis_type == analysis_type)

    q = q.order_by(AiAnalysisNote.created_at.desc()).limit(limit)
    rows = (await db.execute(q)).all()

    return [_note_to_dict(note, t) for note, t in rows]


@router.get("/latest")
async def get_latest_notes(db: AsyncSession = Depends(get_db)):
    """取得每支股票最新一筆 AI 筆記（用於清單頁顯示最後分析時間 + 推薦等級）"""
    # Subquery: each stock's max created_at
    sub = (
        select(
            AiAnalysisNote.stock_id,
            func.max(AiAnalysisNote.id).label("max_id"),
        )
        .group_by(AiAnalysisNote.stock_id)
        .subquery()
    )

    q = (
        select(AiAnalysisNote, Stock.ticker)
        .join(sub, AiAnalysisNote.id == sub.c.max_id)
        .join(Stock, AiAnalysisNote.stock_id == Stock.id)
    )
    rows = (await db.execute(q)).all()

    return {
        t: {
            "id": note.id,
            "recommendation": note.recommendation,
            "action": note.action,
            "analysis_type": note.analysis_type,
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "summary_preview": note.summary[:100] + "..." if len(note.summary) > 100 else note.summary,
        }
        for note, t in rows
    }


@router.get("/strategy-memory", response_model=StrategyMemoryResponse)
async def get_strategy_memory_endpoint(db: AsyncSession = Depends(get_db)):
    """
    KINA-277: 策略失誤分析 API + 記憶摘要結構

    分析 AI 分析筆記的歷史績效，按照 SMC 趨勢和推薦等級進行分組統計，
    識別高失敗率的策略組合，供系統學習和調整。

    Returns:
    - patterns: 按 smc_trend × recommendation 分組的績效統計
    - top_failure_patterns: 失敗率 > 50% 的頂層組合（最多 5 筆）
    - total_analyzed: 分析的已結束筆記總數
    - summary: 最佳和最差的策略條件
    """
    return await get_strategy_memory(db)


# ── 具體路由 (KINA-264: 必須在通用路由 /{note_id} 之前定義) ──────────────


@router.post("/backfill-results")
async def trigger_backfill_results(db: AsyncSession = Depends(get_db)):
    """
    手動觸發 AI 分析筆記結果回填。
    檢查所有 pending 的筆記，根據當前股價更新 outcome_status 和 actual_return_pct。
    """
    stats = await backfill_ai_note_results(db)
    return {
        "message": "AI notes 結果回填完成",
        "stats": stats,
    }


async def get_strategy_memory(db: AsyncSession = Depends(get_db)) -> StrategyMemoryResponse:
    """
    (Internal function) 策略失誤分析和記憶摘要結構

    邏輯：
    1. 從 ai_analysis_notes 過濾 outcome_status != pending
    2. GROUP BY smc_trend × recommendation
    3. 計算每組的 win_rate、avg_return_pct、sample_count
    4. 識別失敗率 > 50% 的組合（top_failure_patterns）
    5. 確定最佳和最差的策略條件
    """
    # 獲取所有已結束的筆記
    completed = await db.execute(
        select(AiAnalysisNote).where(
            AiAnalysisNote.outcome_status != "pending"
        )
    )
    notes = completed.scalars().all()

    if not notes:
        return StrategyMemoryResponse(
            patterns=[],
            top_failure_patterns=[],
            total_analyzed=0,
            summary=StrategySummary(best_condition=None, worst_condition=None)
        )

    # 按 (smc_trend, recommendation) 分組
    pattern_groups: dict = {}
    for note in notes:
        key = (note.smc_trend, note.recommendation)
        if key not in pattern_groups:
            pattern_groups[key] = []
        pattern_groups[key].append(note)

    # 計算每組的統計
    patterns = []
    for (smc_trend, recommendation), group_notes in pattern_groups.items():
        sample_count = len(group_notes)
        hit_target_count = sum(1 for n in group_notes if n.outcome_status == "hit_target")

        # 計算勝率
        win_rate = hit_target_count / sample_count if sample_count > 0 else 0.0

        # 計算平均回報百分比
        returns = [float(n.actual_return_pct) for n in group_notes if n.actual_return_pct is not None]
        avg_return_pct = sum(returns) / len(returns) if returns else 0.0

        # 判定風險等級
        if win_rate < 0.4:
            risk_level = "high"
        elif win_rate < 0.6:
            risk_level = "medium"
        else:
            risk_level = "low"

        pattern = StrategyPattern(
            smc_trend=smc_trend,
            recommendation=recommendation,
            win_rate=round(win_rate, 2),
            avg_return_pct=round(avg_return_pct, 2),
            sample_count=sample_count,
            risk_level=risk_level
        )
        patterns.append(pattern)

    # 識別失敗率 > 50% 的組合
    failure_patterns = []
    for (smc_trend, recommendation), group_notes in pattern_groups.items():
        sample_count = len(group_notes)
        failed_count = sample_count - sum(1 for n in group_notes if n.outcome_status == "hit_target")
        failure_rate = failed_count / sample_count if sample_count > 0 else 0.0

        if failure_rate > 0.5:
            # 計算平均虧損百分比
            losses = [float(n.actual_return_pct) for n in group_notes if n.actual_return_pct is not None and n.actual_return_pct < 0]
            avg_loss_pct = sum(losses) / len(losses) if losses else 0.0

            condition = f"{smc_trend} + {recommendation}"
            warning = f"{smc_trend}市況下{recommendation}失誤率高達 {failure_rate*100:.0f}%，建議審視策略"

            failure_patterns.append(FailurePattern(
                condition=condition,
                failure_rate=round(failure_rate, 2),
                avg_loss_pct=round(avg_loss_pct, 2),
                warning=warning
            ))

    # 按失敗率降序排序，取前 5 筆
    failure_patterns = sorted(failure_patterns, key=lambda x: x.failure_rate, reverse=True)[:5]

    # 確定最佳和最差的策略條件
    best_condition = None
    worst_condition = None
    if patterns:
        best_pattern = max(patterns, key=lambda x: x.win_rate)
        worst_pattern = min(patterns, key=lambda x: x.win_rate)
        best_condition = f"{best_pattern.smc_trend} + {best_pattern.recommendation}"
        worst_condition = f"{worst_pattern.smc_trend} + {worst_pattern.recommendation}"

    summary = StrategySummary(
        best_condition=best_condition,
        worst_condition=worst_condition
    )

    return StrategyMemoryResponse(
        patterns=patterns,
        top_failure_patterns=failure_patterns,
        total_analyzed=len(notes),
        summary=summary
    )


@router.get("/performance")
async def get_ai_notes_performance(db: AsyncSession = Depends(get_db)):
    """
    獲取 AI 分析筆記績效統計。
    返回：
    - 總筆數
    - 各 recommendation 等級的統計
    - 平均回報 / 勝率 / 平均 R:R vs 實現 R:R
    """
    # 獲取所有已結束的筆記（outcome_status != pending）
    completed = await db.execute(
        select(AiAnalysisNote).where(
            AiAnalysisNote.outcome_status != "pending"
        )
    )
    notes = completed.scalars().all()

    if not notes:
        return {
            "total_notes": 0,
            "completed_notes": 0,
            "by_recommendation": {},
            "stats": {
                "win_rate": None,
                "avg_return_pct": None,
                "avg_rr_ratio": None,
                "avg_realized_rr_ratio": None,
                "hit_target": 0,
                "hit_stop": 0,
                "expired": 0,
            }
        }

    # 計算統計
    hits_target = sum(1 for n in notes if n.outcome_status == "hit_target")
    hits_stop = sum(1 for n in notes if n.outcome_status == "hit_stop")
    expired = sum(1 for n in notes if n.outcome_status == "expired")
    total_completed = len(notes)

    # 平均回報
    returns = [float(n.actual_return_pct) for n in notes if n.actual_return_pct is not None]
    avg_return = sum(returns) / len(returns) if returns else None

    # 勝率 = hit_target / total_completed
    win_rate = (hits_target / total_completed) if total_completed > 0 else None

    # 平均預期 R:R
    rr_ratios = [float(n.rr_ratio) for n in notes if n.rr_ratio is not None]
    avg_rr = sum(rr_ratios) / len(rr_ratios) if rr_ratios else None

    # 平均實現 R:R = 實現回報 / 風險（停損距離）
    realized_rr_ratios = []
    for n in notes:
        if n.actual_return_pct is not None and n.entry_price is not None and n.stop_price is not None:
            risk = float(n.entry_price) - float(n.stop_price)
            if risk != 0:
                realized_rr = float(n.actual_return_pct) / (risk / float(n.entry_price) * 100)
                realized_rr_ratios.append(realized_rr)
    avg_realized_rr = sum(realized_rr_ratios) / len(realized_rr_ratios) if realized_rr_ratios else None

    # 按推薦等級分組統計
    by_rec = {}
    for rec_type in ["強力推薦", "推薦", "觀察", "不推薦"]:
        rec_notes = [n for n in notes if n.recommendation == rec_type]
        if rec_notes:
            rec_hits = sum(1 for n in rec_notes if n.outcome_status == "hit_target")
            rec_returns = [float(n.actual_return_pct) for n in rec_notes if n.actual_return_pct is not None]
            by_rec[rec_type] = {
                "count": len(rec_notes),
                "hit_target": rec_hits,
                "win_rate": (rec_hits / len(rec_notes)) if len(rec_notes) > 0 else None,
                "avg_return_pct": (sum(rec_returns) / len(rec_returns)) if rec_returns else None,
            }

    # 所有未結束的筆記
    total_result = await db.execute(select(func.count(AiAnalysisNote.id)))
    total_notes = total_result.scalar()

    return {
        "total_notes": total_notes,
        "completed_notes": total_completed,
        "by_recommendation": by_rec,
        "stats": {
            "win_rate": win_rate,
            "avg_return_pct": avg_return,
            "avg_rr_ratio": avg_rr,
            "avg_realized_rr_ratio": avg_realized_rr,
            "hit_target": hits_target,
            "hit_stop": hits_stop,
            "expired": expired,
        }
    }


# ── 通用路由（參數路由） ───────────────────────────────────────


@router.get("/{note_id}")
async def get_ai_note(note_id: int, db: AsyncSession = Depends(get_db)):
    """取得單筆 AI 分析筆記"""
    result = await db.execute(
        select(AiAnalysisNote, Stock.ticker)
        .join(Stock)
        .where(AiAnalysisNote.id == note_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, f"筆記 #{note_id} 不存在")
    note, ticker = row
    return _note_to_dict(note, ticker)


@router.patch("/{note_id}/outcome")
async def update_ai_note_outcome(
    note_id: int,
    body: AiNoteUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新 AI 分析筆記的交易結果"""
    result = await db.execute(select(AiAnalysisNote).where(AiAnalysisNote.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(404, f"筆記 #{note_id} 不存在")

    note.outcome_status = body.outcome_status
    note.actual_return_pct = body.actual_return_pct
    note.closed_price = body.closed_price
    note.closed_at = body.closed_at

    await db.commit()
    await db.refresh(note)
    return {
        "message": f"筆記 #{note_id} 交易結果已更新",
        "outcome_status": note.outcome_status,
        "actual_return_pct": float(note.actual_return_pct) if note.actual_return_pct else None,
    }


@router.delete("/{note_id}")
async def delete_ai_note(note_id: int, db: AsyncSession = Depends(get_db)):
    """刪除 AI 分析筆記"""
    result = await db.execute(select(AiAnalysisNote).where(AiAnalysisNote.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(404, f"筆記 #{note_id} 不存在")
    await db.delete(note)
    await db.commit()
    return {"message": f"筆記 #{note_id} 已刪除"}
