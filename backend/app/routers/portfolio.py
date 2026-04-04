from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.stock import Stock
from ..models.portfolio import PortfolioTransaction, PortfolioHolding
from ..config import settings

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class BuyRequest(BaseModel):
    ticker: str
    shares: float
    price: float
    note: str = ""


class SellRequest(BaseModel):
    ticker: str
    shares: float
    price: float
    note: str = ""


@router.post("/buy")
async def buy(req: BuyRequest, db: AsyncSession = Depends(get_db)):
    ticker = req.ticker.upper()
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404, f"股票 {ticker} 不在追蹤清單")

    txn = PortfolioTransaction(
        stock_id=stock.id,
        action="BUY",
        shares=req.shares,
        price=req.price,
        total_cost=req.shares * req.price,
        note=req.note,
    )
    db.add(txn)

    # 更新或建立 holding
    h_result = await db.execute(select(PortfolioHolding).where(PortfolioHolding.stock_id == stock.id))
    holding = h_result.scalar_one_or_none()
    if holding:
        new_total = holding.total_shares + req.shares
        new_avg = (holding.avg_cost * holding.total_shares + req.price * req.shares) / new_total
        holding.total_shares = new_total
        holding.avg_cost = new_avg
        holding.highest_price = max(float(holding.highest_price), req.price)
    else:
        db.add(PortfolioHolding(
            stock_id=stock.id,
            total_shares=req.shares,
            avg_cost=req.price,
            highest_price=req.price,
        ))

    await db.commit()
    return {"message": f"買入 {ticker} x{req.shares} @ {req.price}"}


@router.post("/sell")
async def sell(req: SellRequest, db: AsyncSession = Depends(get_db)):
    ticker = req.ticker.upper()
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404)

    h_result = await db.execute(select(PortfolioHolding).where(PortfolioHolding.stock_id == stock.id))
    holding = h_result.scalar_one_or_none()
    if not holding or holding.total_shares < req.shares:
        raise HTTPException(400, "持股不足")

    txn = PortfolioTransaction(
        stock_id=stock.id,
        action="SELL",
        shares=req.shares,
        price=req.price,
        total_cost=req.shares * req.price,
        note=req.note,
    )
    db.add(txn)

    holding.total_shares -= req.shares
    if holding.total_shares <= 0:
        await db.delete(holding)

    await db.commit()
    pnl = (req.price - float(holding.avg_cost)) / float(holding.avg_cost) * 100
    return {"message": f"賣出 {ticker} x{req.shares} @ {req.price}", "pnl_pct": round(pnl, 2)}


@router.get("")
async def get_holdings(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(PortfolioHolding, Stock.ticker, Stock.market, Stock.name)
        .join(Stock)
    )).all()

    result = []
    for r in rows:
        avg = float(r.PortfolioHolding.avg_cost)
        shares = float(r.PortfolioHolding.total_shares)
        highest = float(r.PortfolioHolding.highest_price)
        result.append({
            "ticker": r.ticker,
            "market": r.market,
            "name": r.name,
            "shares": shares,
            "avg_cost": avg,
            "highest_price": highest,
            "cost_basis": round(avg * shares, 2),
            "stop_loss_price": round(avg * (1 - settings.STOP_LOSS_PCT), 2),
            "take_profit_price": round(avg * (1 + settings.TAKE_PROFIT_PCT), 2),
        })
    return result


@router.get("/transactions")
async def get_transactions(limit: int = 50, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(PortfolioTransaction, Stock.ticker, Stock.market)
        .join(Stock)
        .order_by(PortfolioTransaction.transacted_at.desc())
        .limit(limit)
    )).all()
    return [
        {
            "id": r.PortfolioTransaction.id,
            "ticker": r.ticker,
            "market": r.market,
            "action": r.PortfolioTransaction.action,
            "shares": float(r.PortfolioTransaction.shares),
            "price": float(r.PortfolioTransaction.price),
            "total": float(r.PortfolioTransaction.total_cost or 0),
            "note": r.PortfolioTransaction.note,
            "date": r.PortfolioTransaction.transacted_at.isoformat(),
        }
        for r in rows
    ]
