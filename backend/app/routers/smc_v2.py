"""
API v2 — SMC 驅動的分析 endpoints

原則（ENGINEERING.md §廿一）：API 不跑分析，API 只讀結果。
- GET endpoints 全部從 DB 讀取 JSONB，不做即時運算
- POST /analysis/run 觸發 BackgroundTasks
- 回傳帶 computed_at + stale 旗標
"""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db, AsyncSessionLocal
from ..models.stock import Stock
from ..models.analysis import AnalysisResult
from ..services.smc_worker import run_smc_for_ticker, run_smc_batch
from ..sse.manager import sse_manager, emit_progress

router = APIRouter(prefix="/smc", tags=["smc-v2"])


# ────────────────────────────────────────────────────────────
# GET /api/v2/smc/stocks/{ticker}  —  完整 SmcResult
# ────────────────────────────────────────────────────────────
@router.get("/stocks/{ticker}")
async def get_smc_result(ticker: str, db: AsyncSession = Depends(get_db)):
    """
    取得股票最新的 SMC v2 分析結果。

    從 DB 的 smc_data JSONB 直接回傳，不做即時計算。
    包含 stale 旗標（>24h 為 stale）。
    """
    row = await _get_latest_smc_row(db, ticker)
    if not row or not row.smc_data:
        raise HTTPException(404, f"{ticker} 尚無 SMC v2 分析結果，請先 POST /api/v2/smc/analysis/run")

    stale = _is_stale(row.smc_computed_at)

    return {
        "ticker": ticker,
        "analysis_date": row.analysis_date.isoformat(),
        "computed_at": row.smc_computed_at.isoformat() if row.smc_computed_at else None,
        "stale": stale,
        "smc": row.smc_data,
    }


# ────────────────────────────────────────────────────────────
# GET /api/v2/smc/stocks/{ticker}/entry  —  EntryPlan
# ────────────────────────────────────────────────────────────
@router.get("/stocks/{ticker}/entry")
async def get_entry_plan(ticker: str, db: AsyncSession = Depends(get_db)):
    """
    取得股票的 SMC 進場計畫。

    從 DB 的 entry_plan JSONB 直接回傳。
    """
    row = await _get_latest_smc_row(db, ticker)
    if not row or not row.entry_plan:
        raise HTTPException(404, f"{ticker} 尚無進場計畫")

    stale = _is_stale(row.smc_computed_at)

    return {
        "ticker": ticker,
        "analysis_date": row.analysis_date.isoformat(),
        "computed_at": row.smc_computed_at.isoformat() if row.smc_computed_at else None,
        "stale": stale,
        "entry_plan": row.entry_plan,
    }


# ────────────────────────────────────────────────────────────
# GET /api/v2/smc/stocks/{ticker}/summary  —  精簡摘要
# ────────────────────────────────────────────────────────────
@router.get("/stocks/{ticker}/summary")
async def get_smc_summary(ticker: str, db: AsyncSession = Depends(get_db)):
    """
    取得精簡的 SMC + 進場摘要（給前端 card 用）。
    """
    row = await _get_latest_smc_row(db, ticker)
    if not row or not row.smc_data:
        raise HTTPException(404, f"{ticker} 尚無分析結果")

    smc = row.smc_data
    ep = row.entry_plan or {}

    return {
        "ticker": ticker,
        "analysis_date": row.analysis_date.isoformat(),
        "stale": _is_stale(row.smc_computed_at),
        "trend": smc.get("structure", {}).get("trend", "unknown"),
        "regime": row.regime,
        "recommendation": ep.get("recommendation", "未分析"),
        "action": ep.get("action", "不操作"),
        "entry_price": ep.get("entry_price"),
        "stop_price": ep.get("stop_price"),
        "target_price": ep.get("target_price"),
        "rr_ratio": ep.get("rr_ratio"),
        "position_tier": ep.get("position_tier", "none"),
        "current_price": float(row.close_price) if row.close_price else None,
        "warnings": ep.get("warnings", []),
    }


# ────────────────────────────────────────────────────────────
# GET /api/v2/smc/analysis/top-picks  —  SMC 推薦排名
# ────────────────────────────────────────────────────────────
@router.get("/analysis/top-picks")
async def smc_top_picks(
    n: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    取得 SMC v2 推薦排名。

    排序邏輯：recommendation 等級 → R:R → conditions_met
    只回傳有 smc_data 且推薦等級 >= 觀察 的股票。
    """
    # 取最新日期有 smc_data 的所有股票
    from sqlalchemy import func
    latest_date_q = await db.execute(
        select(func.max(AnalysisResult.analysis_date)).where(
            AnalysisResult.smc_data.isnot(None)
        )
    )
    latest_date = latest_date_q.scalar_one_or_none()
    if not latest_date:
        return {"date": None, "picks": []}

    rows = (await db.execute(
        select(AnalysisResult, Stock.ticker, Stock.market, Stock.name)
        .join(Stock)
        .where(
            AnalysisResult.analysis_date == latest_date,
            AnalysisResult.smc_data.isnot(None),
            Stock.is_active == True,
        )
    )).all()

    # 解析 + 排序
    REC_RANK = {"強力推薦": 4, "推薦": 3, "觀察": 2, "觀望": 1, "不推薦": 0}
    picks = []
    for r in rows:
        ep = r.AnalysisResult.entry_plan or {}
        rec = ep.get("recommendation", "不推薦")
        if REC_RANK.get(rec, 0) < 2:  # 過濾掉觀望和不推薦
            continue

        picks.append({
            "ticker": r.ticker,
            "market": r.market,
            "name": r.name,
            "trend": (r.AnalysisResult.smc_data or {}).get("structure", {}).get("trend", "unknown"),
            "regime": r.AnalysisResult.regime,
            "recommendation": rec,
            "action": ep.get("action", "不操作"),
            "entry_price": ep.get("entry_price"),
            "stop_price": ep.get("stop_price"),
            "target_price": ep.get("target_price"),
            "rr_ratio": ep.get("rr_ratio"),
            "position_tier": ep.get("position_tier", "none"),
            "max_position_pct": ep.get("max_position_pct", 0),
            "conditions_met": ep.get("conditions_met", 0),
            "current_price": float(r.AnalysisResult.close_price) if r.AnalysisResult.close_price else None,
        })

    # 排序：推薦等級 desc → R:R desc → conditions desc
    picks.sort(key=lambda p: (
        REC_RANK.get(p["recommendation"], 0),
        p["rr_ratio"] or 0,
        p["conditions_met"],
    ), reverse=True)

    return {
        "date": latest_date.isoformat(),
        "count": len(picks),
        "picks": picks[:n],
    }


# ────────────────────────────────────────────────────────────
# GET /api/v2/smc/analysis/trends  —  全部趨勢一覽
# ────────────────────────────────────────────────────────────
@router.get("/analysis/trends")
async def smc_trends(db: AsyncSession = Depends(get_db)):
    """全部股票的 SMC 趨勢一覽表。"""
    from sqlalchemy import func
    latest_date_q = await db.execute(
        select(func.max(AnalysisResult.analysis_date)).where(
            AnalysisResult.smc_data.isnot(None)
        )
    )
    latest_date = latest_date_q.scalar_one_or_none()
    if not latest_date:
        return {"date": None, "stocks": []}

    rows = (await db.execute(
        select(AnalysisResult, Stock.ticker, Stock.market, Stock.name)
        .join(Stock)
        .where(
            AnalysisResult.analysis_date == latest_date,
            AnalysisResult.smc_data.isnot(None),
            Stock.is_active == True,
        )
        .order_by(Stock.market, Stock.ticker)
    )).all()

    stocks = []
    for r in rows:
        smc = r.AnalysisResult.smc_data or {}
        ep = r.AnalysisResult.entry_plan or {}
        stocks.append({
            "ticker": r.ticker,
            "market": r.market,
            "name": r.name,
            "trend": smc.get("structure", {}).get("trend", "unknown"),
            "regime": r.AnalysisResult.regime,
            "recommendation": ep.get("recommendation", "未分析"),
            "action": ep.get("action", "不操作"),
            "rr_ratio": ep.get("rr_ratio"),
            "current_price": float(r.AnalysisResult.close_price) if r.AnalysisResult.close_price else None,
        })

    return {"date": latest_date.isoformat(), "count": len(stocks), "stocks": stocks}


# ────────────────────────────────────────────────────────────
# POST /api/v2/smc/analysis/run  —  觸發 SMC 分析
# ────────────────────────────────────────────────────────────
_smc_running = False


@router.post("/analysis/run")
async def trigger_smc_analysis(
    background_tasks: BackgroundTasks,
    ticker: str | None = None,
):
    """
    觸發 SMC v2 分析（背景執行）。

    - ticker=None → 批次分析所有股票
    - ticker="NVDA" → 只分析單一股票
    """
    global _smc_running
    if _smc_running:
        return {"message": "SMC 分析已在執行中", "running": True}

    if ticker:
        background_tasks.add_task(_run_single, ticker)
    else:
        background_tasks.add_task(_run_batch)

    return {
        "message": f"SMC 分析已啟動{'（' + ticker + '）' if ticker else '（全部）'}",
        "running": True,
    }


@router.get("/analysis/status")
async def smc_analysis_status():
    return {"running": _smc_running}


# ── Background task wrappers ──

async def _run_single(ticker: str):
    global _smc_running
    _smc_running = True
    try:
        async with AsyncSessionLocal() as db:
            # 找 market
            stock = (await db.execute(
                select(Stock).where(Stock.ticker == ticker)
            )).scalar_one_or_none()
            if not stock:
                await sse_manager.broadcast("smc_error", {"error": f"{ticker} not found"})
                return

            result = await run_smc_for_ticker(
                db, ticker, stock.market,
                progress_cb=emit_progress,
            )
            if result:
                await sse_manager.broadcast("smc_complete", {
                    "ticker": ticker,
                    "trend": result["smc"].structure.trend.value,
                    "recommendation": result["entry_plan"].recommendation,
                })
            else:
                await sse_manager.broadcast("smc_error", {"error": f"{ticker} 分析失敗"})
    except Exception as e:
        await sse_manager.broadcast("smc_error", {"error": str(e)})
    finally:
        _smc_running = False


async def _run_batch():
    global _smc_running
    _smc_running = True
    try:
        async with AsyncSessionLocal() as db:
            summary = await run_smc_batch(db, progress_cb=emit_progress)
            await sse_manager.broadcast("smc_batch_complete", summary)
    except Exception as e:
        await sse_manager.broadcast("smc_error", {"error": str(e)})
    finally:
        _smc_running = False


# ── Helpers ──

async def _get_latest_smc_row(
    db: AsyncSession,
    ticker: str,
) -> AnalysisResult | None:
    """取得指定 ticker 最新的有 smc_data 的 AnalysisResult。"""
    result = await db.execute(
        select(AnalysisResult)
        .join(Stock)
        .where(
            Stock.ticker == ticker,
            AnalysisResult.smc_data.isnot(None),
        )
        .order_by(desc(AnalysisResult.analysis_date))
        .limit(1)
    )
    return result.scalar_one_or_none()


def _is_stale(computed_at: datetime | None, hours: int = 24) -> bool:
    """檢查分析是否過時（預設 24 小時）。"""
    if not computed_at:
        return True
    now = datetime.now(timezone.utc)
    if computed_at.tzinfo is None:
        computed_at = computed_at.replace(tzinfo=timezone.utc)
    return (now - computed_at) > timedelta(hours=hours)
