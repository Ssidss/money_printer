"""
Strategy Profile CRUD + Signal Tracking API
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.strategy import StrategyProfile, BacktestResultV2, StrategySignal
from ..models.stock import Stock
from ..schemas.strategy import (
    StrategyCreate, StrategyUpdate, StrategyOut, StrategyListItem,
    SignalOut, SignalFollowRequest, SignalSkipRequest,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.post("", response_model=StrategyOut)
async def create_strategy(body: StrategyCreate, db: AsyncSession = Depends(get_db)):
    profile = StrategyProfile(
        name=body.name,
        description=body.description,
        params=body.params,
        overrides=body.overrides,
        stock_settings=body.stock_settings,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return _to_out(profile)


@router.get("", response_model=list[StrategyListItem])
async def list_strategies(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(StrategyProfile).order_by(StrategyProfile.updated_at.desc())
    )).scalars().all()
    results = []
    for p in rows:
        item = StrategyListItem(
            id=p.id, name=p.name, description=p.description,
            is_active=p.is_active,
            latest_backtest_id=p.latest_backtest_id,
            latest_metrics=None,
            created_at=p.created_at, updated_at=p.updated_at,
        )
        # 附上最近回測 metrics
        if p.latest_backtest_id:
            bt = (await db.execute(
                select(BacktestResultV2.metrics).where(BacktestResultV2.id == p.latest_backtest_id)
            )).scalar_one_or_none()
            if bt:
                item.latest_metrics = bt
        results.append(item)
    return results


@router.get("/{profile_id}", response_model=StrategyOut)
async def get_strategy(profile_id: int, db: AsyncSession = Depends(get_db)):
    p = await _get_profile(profile_id, db)
    return _to_out(p, db)


@router.put("/{profile_id}", response_model=StrategyOut)
async def update_strategy(profile_id: int, body: StrategyUpdate, db: AsyncSession = Depends(get_db)):
    p = await _get_profile(profile_id, db)
    if body.name is not None:
        p.name = body.name
    if body.description is not None:
        p.description = body.description
    if body.params is not None:
        p.params = body.params
    if body.overrides is not None:
        p.overrides = body.overrides
    if body.stock_settings is not None:
        p.stock_settings = body.stock_settings
    await db.commit()
    await db.refresh(p)
    return _to_out(p)


@router.delete("/{profile_id}")
async def delete_strategy(profile_id: int, db: AsyncSession = Depends(get_db)):
    p = await _get_profile(profile_id, db)
    await db.delete(p)
    await db.commit()
    return {"ok": True}


@router.post("/{profile_id}/activate")
async def activate_strategy(profile_id: int, db: AsyncSession = Depends(get_db)):
    # 先全部停用
    await db.execute(
        update(StrategyProfile).where(StrategyProfile.is_active == True).values(is_active=False)
    )
    p = await _get_profile(profile_id, db)
    p.is_active = True
    await db.commit()
    return {"ok": True, "active_id": p.id}


@router.post("/{profile_id}/clone", response_model=StrategyOut)
async def clone_strategy(profile_id: int, db: AsyncSession = Depends(get_db)):
    src = await _get_profile(profile_id, db)
    clone = StrategyProfile(
        name=f"{src.name} (複製)",
        description=src.description,
        params=src.params.copy(),
        overrides=src.overrides.copy(),
        stock_settings=src.stock_settings.copy(),
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return _to_out(clone)


# ── Signals ──────────────────────────────────────────────────────────────────

@router.get("/{profile_id}/signals", response_model=list[SignalOut])
async def list_signals(
    profile_id: int,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    await _get_profile(profile_id, db)  # ensure exists
    rows = (await db.execute(
        select(StrategySignal, Stock.ticker)
        .join(Stock, StrategySignal.stock_id == Stock.id)
        .where(StrategySignal.profile_id == profile_id)
        .order_by(StrategySignal.signal_date.desc())
        .limit(limit).offset(offset)
    )).all()
    return [
        SignalOut(
            **{c.key: getattr(sig, c.key) for c in StrategySignal.__table__.columns},
            ticker=ticker,
        )
        for sig, ticker in rows
    ]


@router.post("/{profile_id}/signals/{signal_id}/follow")
async def follow_signal(
    profile_id: int, signal_id: int,
    body: SignalFollowRequest,
    db: AsyncSession = Depends(get_db),
):
    sig = await _get_signal(profile_id, signal_id, db)
    sig.followed = True
    if body.actual_entry is not None:
        sig.actual_entry = body.actual_entry
    if body.notes is not None:
        sig.notes = body.notes
    await db.commit()
    return {"ok": True}


@router.post("/{profile_id}/signals/{signal_id}/skip")
async def skip_signal(
    profile_id: int, signal_id: int,
    body: SignalSkipRequest,
    db: AsyncSession = Depends(get_db),
):
    sig = await _get_signal(profile_id, signal_id, db)
    sig.followed = False
    if body.skip_reason is not None:
        sig.skip_reason = body.skip_reason
    if body.notes is not None:
        sig.notes = body.notes
    await db.commit()
    return {"ok": True}


# ── helpers ──────────────────────────────────────────────────────────────────

async def _get_profile(pid: int, db: AsyncSession) -> StrategyProfile:
    p = (await db.execute(
        select(StrategyProfile).where(StrategyProfile.id == pid)
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(404, detail="Strategy profile not found")
    return p


async def _get_signal(pid: int, sid: int, db: AsyncSession) -> StrategySignal:
    s = (await db.execute(
        select(StrategySignal).where(
            StrategySignal.id == sid,
            StrategySignal.profile_id == pid,
        )
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(404, detail="Signal not found")
    return s


def _to_out(p: StrategyProfile, db=None) -> StrategyOut:
    return StrategyOut(
        id=p.id, name=p.name, description=p.description,
        params=p.params, overrides=p.overrides, stock_settings=p.stock_settings,
        is_active=p.is_active,
        latest_backtest_id=p.latest_backtest_id,
        latest_metrics=None,
        created_at=p.created_at, updated_at=p.updated_at,
    )
