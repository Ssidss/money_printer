from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.stock import Stock, PriceHistory
from ..models.analysis import AnalysisResult, NewsArticle
from ..services.technical import load_price_df
from ..services.smc import run_smc_analysis, find_structure
from .analysis import _get_entry

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("")
async def list_stocks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Stock).where(Stock.is_active == True).order_by(Stock.market, Stock.ticker))
    stocks = result.scalars().all()
    return [{"id": s.id, "ticker": s.ticker, "name": s.name, "market": s.market} for s in stocks]


@router.get("/smc-trends")
async def get_smc_trends(db: AsyncSession = Depends(get_db)):
    """批次取得所有追蹤股票的 SMC 趨勢（輕量版，只算 Market Structure）"""
    result = await db.execute(select(Stock).where(Stock.is_active == True))
    stocks = result.scalars().all()

    trends: dict[str, str] = {}
    for stock in stocks:
        df = await load_price_df(db, stock.id, limit=60)
        if df is None:
            trends[stock.ticker] = "未知"
            continue
        try:
            struct = find_structure(df)
            trends[stock.ticker] = struct.get("trend", "未知")
        except Exception:
            trends[stock.ticker] = "未知"
    return trends


@router.get("/{ticker}")
async def get_stock(ticker: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404, f"股票 {ticker} 不存在")
    return {"id": stock.id, "ticker": stock.ticker, "name": stock.name, "market": stock.market, "is_active": stock.is_active}


@router.get("/{ticker}/prices")
async def get_prices(
    ticker: str,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 120,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404, f"股票 {ticker} 不存在")

    q = select(PriceHistory).where(PriceHistory.stock_id == stock.id)
    if from_date:
        q = q.where(PriceHistory.date >= from_date)
    if to_date:
        q = q.where(PriceHistory.date <= to_date)
    q = q.order_by(PriceHistory.date.desc()).limit(limit)

    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "date": r.date.isoformat(),
            "open": float(r.open) if r.open else None,
            "high": float(r.high) if r.high else None,
            "low": float(r.low) if r.low else None,
            "close": float(r.close) if r.close else None,
            "volume": r.volume,
        }
        for r in reversed(rows)
    ]


@router.get("/{ticker}/analysis")
async def get_analysis(ticker: str, limit: int = 30, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404, f"股票 {ticker} 不存在")

    rows = (await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.stock_id == stock.id)
        .order_by(AnalysisResult.analysis_date.desc())
        .limit(limit)
    )).scalars().all()

    return [
        {
            "date": r.analysis_date.isoformat(),
            "composite_score": float(r.composite_score) if r.composite_score else None,
            "technical_score": float(r.technical_score) if r.technical_score else None,
            "sentiment_score": float(r.sentiment_score) if r.sentiment_score else None,
            "recommendation": r.recommendation,
            "rsi": float(r.rsi) if r.rsi else None,
            "macd": float(r.macd) if r.macd else None,
            "close_price": float(r.close_price) if r.close_price else None,
            "signals": r.signals,
            "news_summary": r.news_summary,
            "entry_suggestion": _get_entry(r),
        }
        for r in reversed(rows)
    ]


@router.get("/{ticker}/news")
async def get_news(ticker: str, limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404, f"股票 {ticker} 不存在")

    rows = (await db.execute(
        select(NewsArticle)
        .where(NewsArticle.stock_id == stock.id)
        .order_by(NewsArticle.published_at.desc())
        .limit(limit)
    )).scalars().all()

    return [
        {
            "id": r.id,
            "title": r.title,
            "url": r.url,
            "source": r.source,
            "published_at": r.published_at.isoformat() if r.published_at else None,
            "sentiment_score": float(r.sentiment_score) if r.sentiment_score else None,
        }
        for r in rows
    ]


@router.post("")
async def add_stock(ticker: str, market: str, name: str = "", db: AsyncSession = Depends(get_db)):
    """手動新增追蹤股票"""
    ticker = ticker.upper()
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    existing = result.scalar_one_or_none()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            await db.commit()
        return {"message": f"{ticker} 已加入追蹤", "id": existing.id}

    stock = Stock(ticker=ticker, market=market.upper(), name=name or None)
    db.add(stock)
    await db.commit()
    return {"message": f"{ticker} 新增成功", "id": stock.id}


@router.get("/{ticker}/smc")
async def get_smc(ticker: str, limit: int = 120, db: AsyncSession = Depends(get_db)):
    """SMC 分析：Order Blocks、FVG、市場結構、量能分佈、走勢機率"""
    result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404, f"股票 {ticker} 不存在")
    df = await load_price_df(db, stock.id, limit=limit)
    if df is None:
        raise HTTPException(404, "股價資料不足（需至少 30 根K棒）")
    return run_smc_analysis(df)


@router.delete("/{ticker}")
async def remove_stock(ticker: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404)
    stock.is_active = False
    await db.commit()
    return {"message": f"{ticker} 已停止追蹤"}
