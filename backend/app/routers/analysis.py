from __future__ import annotations
import asyncio
from datetime import date
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db, AsyncSessionLocal
from ..models.stock import Stock
from ..models.analysis import AnalysisResult
from ..services.recommender import run_full_analysis
from ..services.news_crawler import crawl_and_store_news
from ..services.smc_worker import run_smc_batch
from ..sse.manager import sse_manager, emit_progress


def _compute_entry(close, ma20, bb_lower, recommendation: str) -> dict | None:
    """舊版 MA 進場建議（向後相容用，新分析都用 SMC 驅動版）"""
    if not close:
        return None
    c = float(close)
    supports = []
    if ma20:   supports.append(float(ma20))
    if bb_lower: supports.append(float(bb_lower))
    valid = [s for s in supports if s < c * 1.02]
    entry = max(valid) if valid else c * 0.97
    entry = min(entry, c)
    stop   = round(entry * 0.93, 2)
    target = round(entry * 1.15, 2)
    rr     = round((target - entry) / max(entry - stop, 0.01), 1)
    return {"entry": round(entry, 2), "stop": stop, "target": target, "rr": rr}


def _get_entry(row) -> dict | None:
    """優先取 SMC 驅動的 entry_suggestion，否則回退舊版 MA 計算"""
    stored = getattr(row, "entry_suggestion", None) if hasattr(row, "entry_suggestion") else None
    if stored and isinstance(stored, dict) and "entry" in stored:
        return stored
    # 回退：舊資料沒有 SMC entry，用 MA 計算
    return _compute_entry(
        getattr(row, "close_price", None),
        getattr(row, "ma20", None),
        getattr(row, "bb_lower", None),
        getattr(row, "recommendation", ""),
    )

def _extract_smc_summary(row: AnalysisResult) -> dict | None:
    """從 AnalysisResult 提取 SMC v2 精簡摘要，無 v2 數據回傳 None。"""
    if not row.smc_data:
        return None
    smc = row.smc_data
    ep = row.entry_plan or {}
    return {
        "trend": smc.get("structure", {}).get("trend", "unknown"),
        "regime": row.regime,
        "recommendation": ep.get("recommendation"),
        "action": ep.get("action"),
        "entry_price": ep.get("entry_price"),
        "stop_price": ep.get("stop_price"),
        "target_price": ep.get("target_price"),
        "rr_ratio": ep.get("rr_ratio"),
        "position_tier": ep.get("position_tier"),
    }


router = APIRouter(prefix="/analysis", tags=["analysis"])

_running = False   # 防止同時多次觸發


async def _run_pipeline(news_days: int = 3):
    """完整分析流程（跑在 background task 中）"""
    global _running
    if _running:
        return
    _running = True
    try:
        async with AsyncSessionLocal() as db:
            # Step 1: 爬新聞
            result = await db.execute(select(Stock).where(Stock.is_active == True))
            stocks = result.scalars().all()
            total = len(stocks)

            for i, stock in enumerate(stocks, 1):
                await emit_progress(
                    f"爬取 {stock.ticker} 新聞...",
                    phase="crawling_news", current=i, total=total, ticker=stock.ticker
                )
                await crawl_and_store_news(db, stock, days=news_days)

            # Step 2: v1 分析評分
            result = await run_full_analysis(db, progress_cb=emit_progress)

            # Step 3: SMC v2 分析（利用 Step 1 爬到的新聞情緒）
            await emit_progress("SMC v2 批次分析...", phase="smc_v2_batch")
            smc_summary = await run_smc_batch(db, progress_cb=emit_progress)

            await sse_manager.broadcast("analysis_complete", {
                "top_picks": result["top_picks"],
                "summary": result["summary"],
                "smc_v2": smc_summary,
            })
    except Exception as e:
        await sse_manager.broadcast("analysis_error", {"error": str(e)})
    finally:
        _running = False


@router.post("/run")
async def trigger_analysis(background_tasks: BackgroundTasks, news_days: int = 3):
    """觸發一次完整分析（非同步背景執行）"""
    global _running
    if _running:
        return {"message": "分析已在執行中", "running": True}
    background_tasks.add_task(_run_pipeline, news_days)
    return {"message": "分析已啟動，請訂閱 /sse/progress 查看進度", "running": True}


@router.get("/status")
async def analysis_status():
    return {"running": _running}


@router.get("/top-picks")
async def top_picks(analysis_date: date | None = None, n: int = 3, db: AsyncSession = Depends(get_db)):
    """取得指定日期（預設今天）的 Top N 推薦"""
    target = analysis_date or date.today()
    rows = (await db.execute(
        select(AnalysisResult, Stock.ticker, Stock.market, Stock.name)
        .join(Stock)
        .where(AnalysisResult.analysis_date == target, Stock.is_active == True)
        .order_by(AnalysisResult.composite_score.desc())
        .limit(n)
    )).all()

    return [
        {
            "ticker": r.ticker,
            "market": r.market,
            "name": r.name,
            "composite_score": float(r.AnalysisResult.composite_score or 0),
            "technical_score": float(r.AnalysisResult.technical_score or 0),
            "sentiment_score": float(r.AnalysisResult.sentiment_score or 0),
            "recommendation": r.AnalysisResult.recommendation,
            "rsi": float(r.AnalysisResult.rsi or 0),
            "close_price": float(r.AnalysisResult.close_price or 0),
            "signals": r.AnalysisResult.signals,
            "news_summary": r.AnalysisResult.news_summary,
            "entry_suggestion": _get_entry(r.AnalysisResult),
            "smc_v2": _extract_smc_summary(r.AnalysisResult),
        }
        for r in rows
    ]


@router.get("/latest")
async def latest_analysis(db: AsyncSession = Depends(get_db)):
    """取得最新一次分析的完整結果"""
    from sqlalchemy import func
    latest_date_result = await db.execute(select(func.max(AnalysisResult.analysis_date)))
    latest_date = latest_date_result.scalar_one_or_none()
    if not latest_date:
        return {"date": None, "results": []}

    rows = (await db.execute(
        select(AnalysisResult, Stock.ticker, Stock.market, Stock.name)
        .join(Stock)
        .where(AnalysisResult.analysis_date == latest_date, Stock.is_active == True)
        .order_by(AnalysisResult.composite_score.desc())
    )).all()

    return {
        "date": latest_date.isoformat(),
        "results": [
            {
                "ticker": r.ticker,
                "market": r.market,
                "name": r.name,
                "composite_score": float(r.AnalysisResult.composite_score or 0),
                "technical_score": float(r.AnalysisResult.technical_score or 0),
                "sentiment_score": float(r.AnalysisResult.sentiment_score or 0),
                "recommendation": r.AnalysisResult.recommendation,
                "rsi": float(r.AnalysisResult.rsi or 0),
                "close_price": float(r.AnalysisResult.close_price or 0),
                "signals": r.AnalysisResult.signals,
                "smc_v2": _extract_smc_summary(r.AnalysisResult),
                "news_summary": r.AnalysisResult.news_summary,
                "entry_suggestion": _get_entry(r.AnalysisResult),
            }
            for r in rows
        ]
    }
