from __future__ import annotations
"""
FastAPI App 主體
startup 時：
  1. 建立 DB 表
  2. 匯入追蹤股票清單
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .config import settings
from .database import engine, AsyncSessionLocal, Base
from .models import Stock, PriceHistory, AnalysisResult, NewsArticle, PortfolioTransaction, PortfolioHolding, BacktestResult
from .routers import stocks, analysis, portfolio, backtest, sse, telegram, ai_notes, briefing
from .services.fetcher import ensure_stock_exists

logger = logging.getLogger(__name__)


async def _init_stocks(db):
    """把 settings 中的股票清單寫入 DB"""
    for ticker in settings.US_STOCKS:
        await ensure_stock_exists(db, ticker, "US")
    for ticker in settings.TW_STOCKS:
        await ensure_stock_exists(db, ticker, "TW")
    await db.commit()
    logger.info(f"股票清單初始化完成：US {len(settings.US_STOCKS)} 支，TW {len(settings.TW_STOCKS)} 支")


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

    logger.info("排程已關閉，請手動觸發分析（POST /api/v1/stocks/{ticker}/analyze/sync 或批次分析）")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────
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
app.include_router(ai_notes.router, prefix="/api/v1")
app.include_router(briefing.router, prefix="/api/v1")
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
