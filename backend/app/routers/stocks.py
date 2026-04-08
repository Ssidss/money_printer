from __future__ import annotations
from datetime import date
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db, AsyncSessionLocal
from ..models.stock import Stock, PriceHistory
from ..models.analysis import AnalysisResult, NewsArticle
from ..services.technical import load_price_df
from ..services.smc_v1 import run_smc_analysis, run_mtf_smc_analysis, find_structure, resample_to_weekly, resample_to_monthly
from ..services.fetcher import fetch_realtime_price, fetch_realtime_prices_batch
from ..sse.manager import emit_progress
from .analysis import _get_entry

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("")
async def list_stocks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Stock).where(Stock.is_active == True).order_by(Stock.market, Stock.ticker))
    stocks = result.scalars().all()
    return [{"id": s.id, "ticker": s.ticker, "name": s.name, "market": s.market} for s in stocks]


@router.get("/smc-trends")
async def get_smc_trends(db: AsyncSession = Depends(get_db)):
    """批次取得所有追蹤股票的 SMC 趨勢（含 MTF 多時間框架）"""
    result = await db.execute(select(Stock).where(Stock.is_active == True))
    stocks = result.scalars().all()

    trends: dict[str, dict | str] = {}
    for stock in stocks:
        df = await load_price_df(db, stock.id, limit=1260)
        if df is None:
            trends[stock.ticker] = "未知"
            continue
        try:
            # 日線結構
            struct = find_structure(df)
            daily_trend = struct.get("trend", "未知")

            # 週線結構
            weekly_trend = "未知"
            try:
                df_w = resample_to_weekly(df)
                if len(df_w) >= 20:
                    weekly_trend = find_structure(df_w).get("trend", "未知")
            except Exception:
                pass

            # 月線結構
            monthly_trend = "未知"
            try:
                df_m = resample_to_monthly(df)
                if len(df_m) >= 12:
                    monthly_trend = find_structure(df_m).get("trend", "未知")
            except Exception:
                pass

            trends[stock.ticker] = {
                "daily": daily_trend,
                "weekly": weekly_trend,
                "monthly": monthly_trend,
            }
        except Exception:
            trends[stock.ticker] = "未知"
    return trends


@router.get("/realtime")
async def get_realtime_prices(db: AsyncSession = Depends(get_db)):
    """批次取得所有追蹤股票的即時/盤中報價（手動觸發）"""
    result = await db.execute(select(Stock).where(Stock.is_active == True))
    stocks = result.scalars().all()
    tickers = [(s.ticker, s.market) for s in stocks]
    prices = await fetch_realtime_prices_batch(tickers)
    # 附上股票名稱
    name_map = {s.ticker: s.name for s in stocks}
    for ticker, data in prices.items():
        data["name"] = name_map.get(ticker)
    return prices


@router.get("/{ticker}/realtime")
async def get_realtime_price_single(ticker: str, db: AsyncSession = Depends(get_db)):
    """取得單支股票的即時/盤中報價（手動觸發）"""
    ticker = ticker.upper()
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404, f"股票 {ticker} 不存在")
    data = await fetch_realtime_price(ticker, stock.market)
    if not data:
        raise HTTPException(502, f"無法取得 {ticker} 即時報價")
    data["ticker"] = ticker
    data["name"] = stock.name
    data["market"] = stock.market
    return data


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
    timeframe: str = "daily",  # daily / weekly / monthly
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404, f"股票 {ticker} 不存在")

    # 週線/月線需要更多原始資料
    raw_limit = limit
    if timeframe == "weekly":
        raw_limit = limit * 5 + 50    # 每週約 5 個交易日
    elif timeframe == "monthly":
        raw_limit = limit * 22 + 100  # 每月約 22 個交易日

    q = select(PriceHistory).where(PriceHistory.stock_id == stock.id)
    if from_date:
        q = q.where(PriceHistory.date >= from_date)
    if to_date:
        q = q.where(PriceHistory.date <= to_date)
    q = q.order_by(PriceHistory.date.desc()).limit(raw_limit)

    rows = (await db.execute(q)).scalars().all()
    bars = [
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

    # 如果要週線/月線，用 pandas resample
    if timeframe in ("weekly", "monthly") and bars:
        import pandas as pd
        df = pd.DataFrame(bars)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        rule = "W" if timeframe == "weekly" else "ME"
        df = df.resample(rule).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna(subset=["close"]).tail(limit)
        bars = [
            {
                "date": idx.strftime("%Y-%m-%d"),
                "open": round(row["open"], 2) if row["open"] else None,
                "high": round(row["high"], 2) if row["high"] else None,
                "low": round(row["low"], 2) if row["low"] else None,
                "close": round(row["close"], 2) if row["close"] else None,
                "volume": int(row["volume"]) if row["volume"] else 0,
            }
            for idx, row in df.iterrows()
        ]

    return bars


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
async def get_smc(
    ticker: str,
    limit: int = 120,
    timeframe: str = "daily",
    db: AsyncSession = Depends(get_db),
):
    """SMC 分析（支援日/週/月線）：OB、FVG、結構、量能、機率"""
    result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404, f"股票 {ticker} 不存在")

    # 週線/月線需要更多原始日線資料來 resample
    if timeframe == "weekly":
        raw_limit = max(limit * 5, 1260)
    elif timeframe == "monthly":
        raw_limit = max(limit * 22, 1260)
    else:
        raw_limit = limit

    df = await load_price_df(db, stock.id, limit=raw_limit)
    if df is None:
        raise HTTPException(404, "股價資料不足")

    if timeframe == "weekly":
        df = resample_to_weekly(df)
        if len(df) > limit:
            df = df.iloc[-limit:]
    elif timeframe == "monthly":
        df = resample_to_monthly(df)
        if len(df) > limit:
            df = df.iloc[-limit:]

    if len(df) < 20:
        raise HTTPException(404, f"{timeframe} 資料不足（需至少 20 根K棒，目前 {len(df)} 根）")

    return run_smc_analysis(df)


# ── 批次更新 ─────────────────────────────────────────────────────

@router.post("/batch-fetch")
async def batch_fetch_stocks(
    days: int = 7,
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """批次更新所有追蹤股票的股價（背景執行）"""
    background_tasks.add_task(_run_batch_fetch, days)
    return {"message": f"批次股價更新已啟動（回補 {days} 天）"}


async def _run_batch_fetch(days: int):
    from ..services.fetcher import fetch_and_store_prices

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Stock).where(Stock.is_active == True))
        stocks = result.scalars().all()
        total = len(stocks)
        for i, stock in enumerate(stocks, 1):
            await emit_progress(
                f"更新 {stock.ticker} 股價 ({i}/{total})...",
                phase="batch_fetch", current=i, total=total, ticker=stock.ticker,
            )
            try:
                await fetch_and_store_prices(db, stock.ticker, stock.market, days=days)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"批次更新 {stock.ticker} 失敗: {e}")
        await emit_progress("批次股價更新完成", phase="done", current=total, total=total)


# ── 單股更新 ─────────────────────────────────────────────────────

@router.post("/{ticker}/fetch")
async def fetch_single_stock(
    ticker: str,
    days: int = 7,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """更新單支股票的股價資料（預設補最近 7 天）"""
    ticker = ticker.upper()
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404, f"股票 {ticker} 不存在")

    from ..services.fetcher import fetch_and_store_prices
    count = await fetch_and_store_prices(db, ticker, stock.market, days=days)
    return {"message": f"{ticker} 股價更新完成", "rows_added": count}


async def _run_single_analysis(ticker: str):
    """背景執行單股分析（爬新聞 + 技術分析 + 分層決策）"""
    from ..services.fetcher import fetch_and_store_prices
    from ..services.news_crawler import crawl_and_store_news
    from ..services.recommender import run_analysis_for_stock

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Stock).where(Stock.ticker == ticker))
        stock = result.scalar_one_or_none()
        if not stock:
            return

        await emit_progress(f"更新 {ticker} 股價...", phase="fetching", current=1, total=4, ticker=ticker)
        await fetch_and_store_prices(db, ticker, stock.market, days=7)

        await emit_progress(f"爬取 {ticker} 新聞...", phase="crawling_news", current=2, total=4, ticker=ticker)
        await crawl_and_store_news(db, stock, days=3)

        await emit_progress(f"分析 {ticker}...", phase="analyzing", current=3, total=4, ticker=ticker)
        res = await run_analysis_for_stock(db, stock)

        await emit_progress(
            f"{ticker} 分析完成" + (f"：{res['recommendation']}" if res else "（資料不足）"),
            phase="done", current=4, total=4, ticker=ticker,
        )


@router.post("/{ticker}/analyze")
async def analyze_single_stock(
    ticker: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    對單支股票執行完整分析流程（背景執行）：
    1. 更新股價（最近 7 天）
    2. 爬取最新新聞
    3. 執行分層決策分析
    """
    ticker = ticker.upper()
    background_tasks.add_task(_run_single_analysis, ticker)
    return {"message": f"{ticker} 分析已啟動，請訂閱 /sse/progress 查看進度"}


@router.post("/{ticker}/analyze/sync")
async def analyze_single_stock_sync(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """
    同步版：對單支股票執行完整分析，等待完成後回傳結果。
    適合 CLI / Claude 直接呼叫。
    """
    from ..services.fetcher import fetch_and_store_prices
    from ..services.news_crawler import crawl_and_store_news
    from ..services.recommender import run_analysis_for_stock

    ticker = ticker.upper()
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404, f"股票 {ticker} 不存在")

    # 1. 更新股價
    price_count = await fetch_and_store_prices(db, ticker, stock.market, days=7)

    # 2. 爬新聞
    news_count = await crawl_and_store_news(db, stock, days=3)

    # 3. 分析
    res = await run_analysis_for_stock(db, stock)

    if not res:
        raise HTTPException(422, f"{ticker} 分析失敗（資料不足）")

    return {
        "ticker": ticker,
        "prices_added": price_count,
        "news_added": news_count,
        "analysis": {
            "composite_score": res["composite_score"],
            "technical_score": res["technical_score"],
            "sentiment_score": res["sentiment_score"],
            "recommendation": res["recommendation"],
            "position_tier": res["position_tier"],
            "smc_trend": res["smc_trend"],
            "catalyst": res["catalyst"],
            "signals_met": res["signals_met"],
            "signals": res["signals"],
        },
    }


@router.delete("/{ticker}")
async def remove_stock(ticker: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(404)
    stock.is_active = False
    await db.commit()
    return {"message": f"{ticker} 已停止追蹤"}
