from __future__ import annotations
"""
FastAPI App 主體
startup 時：
  1. 若 AUTO_DB 啟用，自動啟動嵌入式 PostgreSQL
  2. 建立 DB 表
  3. 匯入追蹤股票清單
"""

import logging
import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .config import settings
from .database import engine, AsyncSessionLocal, Base
from .embedded_postgres import PostgreSQLManager
from .models import (
    User,
    Stock, PriceHistory, AnalysisResult, NewsArticle,
    PortfolioTransaction, PortfolioHolding, BacktestResult, BacktestResultV3,
    AiAnalysisNote,
    StrategyProfile, BacktestResultV2, BacktestTrade, BacktestEquity, StrategySignal,
)
from .routers import stocks, analysis, portfolio, backtest, sse, telegram, ai_notes, briefing, smc_v2
from .routers import strategies, backtest_v2, backtest_v3, auth, scanner, signals, backtest_vbt
from .services.fetcher import ensure_stock_exists

logger = logging.getLogger(__name__)

# 全域 PostgreSQL 管理器實例
_pg_manager: PostgreSQLManager | None = None


async def _init_stocks(db):
    """把 settings 中的股票清單寫入 DB"""
    for ticker in settings.US_STOCKS:
        await ensure_stock_exists(db, ticker, "US")
    for ticker in settings.TW_STOCKS:
        await ensure_stock_exists(db, ticker, "TW")
    await db.commit()
    logger.info(f"股票清單初始化完成：US {len(settings.US_STOCKS)} 支，TW {len(settings.TW_STOCKS)} 支")


async def _run_migrations():
    """執行所有資料庫遷移"""
    # 動態導入遷移模組
    backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    from migrate_kina260_ai_notes_results import migrate as migrate_kina260
    await migrate_kina260()
    logger.info("✓ 遷移 KINA-260 完成")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────
    global _pg_manager

    logger.info("Money Printer 啟動中...")

    # 若啟用 AUTO_DB，自動啟動嵌入式 PostgreSQL
    if settings.AUTO_DB:
        logger.info("AUTO_DB 已啟用，嘗試啟動嵌入式 PostgreSQL...")
        _pg_manager = PostgreSQLManager(
            pgdata_dir="~/.money_printer/pgdata",
            db_user=settings.DB_USER,
            db_password=settings.DB_PASSWORD,
            db_port=settings.DB_PORT,
        )
        try:
            startup_info = await _pg_manager.start()
            logger.info(f"✓ PostgreSQL 啟動成功: {startup_info}")
            # 確保目標資料庫存在
            await _pg_manager.ensure_database_exists(settings.DB_NAME)
        except Exception as e:
            logger.error(f"✗ PostgreSQL 啟動失敗: {e}")
            raise
    else:
        logger.info("AUTO_DB 未啟用，使用外部 PostgreSQL 或 DATABASE_URL 環境變數")

    # 建立所有 DB 表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB 表建立完成")

    # 執行資料庫遷移 (KINA-260: 添加 AI notes 結果追蹤欄位)
    await _run_migrations()
    logger.info("DB 遷移完成")

    async with AsyncSessionLocal() as db:
        await _init_stocks(db)

    logger.info("排程已關閉，請手動觸發分析（POST /api/v1/stocks/{ticker}/analyze/sync 或批次分析）")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────
    await engine.dispose()
    logger.info("Money Printer 關閉")

    # 若啟用 AUTO_DB，優雅停止嵌入式 PostgreSQL
    if _pg_manager is not None:
        logger.info("停止嵌入式 PostgreSQL...")
        try:
            await _pg_manager.stop()
            logger.info("✓ PostgreSQL 已停止")
        except Exception as e:
            logger.error(f"✗ PostgreSQL 停止失敗: {e}")


app = FastAPI(
    title="Money Printer API",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── v1 routes ────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(stocks.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(portfolio.router, prefix="/api/v1")
app.include_router(backtest.router, prefix="/api/v1")
app.include_router(backtest_vbt.router, prefix="/api/v1")
app.include_router(telegram.router, prefix="/api/v1")
app.include_router(ai_notes.router, prefix="/api/v1")
app.include_router(briefing.router, prefix="/api/v1")
app.include_router(scanner.router, prefix="/api/v1")

# ── v2 routes ────────────────────────────────────────────────────────
app.include_router(smc_v2.router, prefix="/api/v2")
app.include_router(strategies.router, prefix="/api/v2")
app.include_router(backtest_v2.router, prefix="/api/v2")

# ── v3 routes ────────────────────────────────────────────────────────
app.include_router(backtest_v3.router, prefix="/api/v3")
app.include_router(signals.router, prefix="/api/v3")

# ── SSE ──────────────────────────────────────────────────────────────
app.include_router(sse.router)


@app.get("/")
async def root():
    return {
        "name": "Money Printer API",
        "version": "2.1.0",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
