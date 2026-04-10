from __future__ import annotations
"""
AI 分析筆記 API
- POST   /ai-notes           建立 AI 分析筆記
- GET    /ai-notes            取得所有筆記（可過濾 ticker）
- GET    /ai-notes/latest     取得每支股票最新一筆 AI 筆記（用於清單頁顯示）
- GET    /ai-notes/{id}       取得單筆筆記
- DELETE /ai-notes/{id}       刪除筆記
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.stock import Stock
from ..models.user import User
from ..models.ai_note import AiAnalysisNote
from ..services.auth import get_optional_user

router = APIRouter(prefix="/ai-notes", tags=["ai-notes"])


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
