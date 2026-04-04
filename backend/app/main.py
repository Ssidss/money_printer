from __future__ import annotations
"""
FastAPI App 主體
startup 時：
  1. 建立 DB 表
  2. 匯入追蹤股票清單
  3. 自動補齊缺失股價
  4. 若今天尚無分析結果 → 觸發分析
  5. 啟動定時排程
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from .config import settings
from .database import engine, AsyncSessionLocal, Base
from .models import Stock, PriceHistory, AnalysisResult, NewsArticle, PortfolioTransaction, PortfolioHolding, BacktestResult
from .routers import stocks, analysis, portfolio, backtest, sse, telegram
from .services.fetcher import fetch_all_stocks, ensure_stock_exists
from .services.news_crawler import crawl_and_store_news
from .services.recommender import run_full_analysis
from .services.telegram import notify_daily_report
from .sse.manager import emit_progress

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Asia/Taipei")


async def _init_stocks(db):
    """把 settings 中的股票清單寫入 DB"""
    for ticker in settings.US_STOCKS:
        await ensure_stock_exists(db, ticker, "US")
    for ticker in settings.TW_STOCKS:
        await ensure_stock_exists(db, ticker, "TW")
    await db.commit()
    logger.info(f"股票清單初始化完成：US {len(settings.US_STOCKS)} 支，TW {len(settings.TW_STOCKS)} 支")


async def _startup_fill_prices():
    """Startup：補齊所有缺失的歷史股價"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Stock).where(Stock.is_active == True))
        stocks = result.scalars().all()
        us = [s.ticker for s in stocks if s.market == "US"]
        tw = [s.ticker for s in stocks if s.market == "TW"]

        logger.info(f"開始補齊股價（{len(us)} 美股 + {len(tw)} 台股）...")
        await fetch_all_stocks(db, us, tw, days=settings.PRICE_HISTORY_DAYS)
        logger.info("股價補齊完成")


async def _startup_run_analysis():
    """Startup：若今天尚無分析 → 跑一次"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AnalysisResult).where(AnalysisResult.analysis_date == date.today()).limit(1)
        )
        if result.scalar_one_or_none():
            logger.info("今日已有分析結果，跳過 startup 分析")
            return

        logger.info("今日尚無分析，開始執行...")
        result2 = await db.execute(select(Stock).where(Stock.is_active == True))
        stocks = result2.scalars().all()
        for stock in stocks:
            await crawl_and_store_news(db, stock, days=3)

        result = await run_full_analysis(db)
        await notify_daily_report(result["top_picks"], result["summary"])
        logger.info("Startup 分析完成")


async def _daily_analysis_job():
    """定時分析任務（每天台股收盤後 + 美股收盤後各跑一次）"""
    logger.info("定時分析任務啟動...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Stock).where(Stock.is_active == True))
        stocks = result.scalars().all()
        us = [s.ticker for s in stocks if s.market == "US"]
        tw = [s.ticker for s in stocks if s.market == "TW"]

        await emit_progress("定時任務：補齊股價...", phase="scheduled", current=0, total=100)
        await fetch_all_stocks(db, us, tw, days=7)

        await emit_progress("定時任務：爬取新聞...", phase="scheduled", current=30, total=100)
        for stock in stocks:
            await crawl_and_store_news(db, stock, days=3)

        await emit_progress("定時任務：執行分析...", phase="scheduled", current=60, total=100)
        result = await run_full_analysis(db, progress_cb=emit_progress)

        from .sse.manager import sse_manager
        await sse_manager.broadcast("analysis_complete", {
            "top_picks": result["top_picks"],
            "summary": result["summary"],
            "source": "scheduled",
        })

        # Telegram 推播
        await notify_daily_report(result["top_picks"], result["summary"])
        logger.info("定時分析任務完成")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────
    logger.info("Money Printer 啟動中...")

    # 建立所有 DB 表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB 表建立完成")

    async with AsyncSessionLocal() as db:
        await _init_stocks(db)

    # 補齊股價（背景執行，不阻塞 server 啟動）
    asyncio.create_task(_startup_fill_prices())

    # 今日分析（背景執行）
    asyncio.create_task(_startup_run_analysis())

    # 定時排程
    scheduler.add_job(
        _daily_analysis_job,
        CronTrigger(hour=settings.SCHEDULE_TW_HOUR, minute=settings.SCHEDULE_TW_MINUTE),
        id="tw_analysis",
        replace_existing=True,
    )
    scheduler.add_job(
        _daily_analysis_job,
        CronTrigger(hour=settings.SCHEDULE_US_HOUR, minute=settings.SCHEDULE_US_MINUTE),
        id="us_analysis",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"排程已啟動：台股 {settings.SCHEDULE_TW_HOUR}:{settings.SCHEDULE_TW_MINUTE:02d} / 美股 {settings.SCHEDULE_US_HOUR}:{settings.SCHEDULE_US_MINUTE:02d}")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    await engine.dispose()
    logger.info("Money Printer 關閉")


app = FastAPI(
    title="Money Printer API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(portfolio.router, prefix="/api/v1")
app.include_router(backtest.router, prefix="/api/v1")
app.include_router(telegram.router, prefix="/api/v1")
app.include_router(sse.router)


@app.get("/")
async def root():
    return {
        "name": "Money Printer API",
        "version": "2.0.0",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
