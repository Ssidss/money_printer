from __future__ import annotations
from datetime import date
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db, AsyncSessionLocal
from ..models.backtest import BacktestResult
from ..services.backtester import run_backtest, optimize_weights
from ..sse.manager import emit_progress

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    name: str = "回測"
    start_date: date
    end_date: date
    buy_threshold: float = 60.0
    stop_loss_pct: float = 0.07
    trailing_stop_pct: float = 0.05
    initial_capital: float = 1_000_000
    position_size_pct: float = 0.1
    max_positions: int = 5
    use_smc_filter: bool = True
    smc_exit_on_downtrend: bool = True


_backtest_running = False


async def _run_and_save(req: BacktestRequest):
    global _backtest_running
    _backtest_running = True
    try:
        async with AsyncSessionLocal() as db:
            result = await run_backtest(
                db,
                start_date=req.start_date,
                end_date=req.end_date,
                buy_threshold=req.buy_threshold,
                stop_loss_pct=req.stop_loss_pct,
                trailing_stop_pct=req.trailing_stop_pct,
                initial_capital=req.initial_capital,
                position_size_pct=req.position_size_pct,
                max_positions=req.max_positions,
                use_smc_filter=req.use_smc_filter,
                smc_exit_on_downtrend=req.smc_exit_on_downtrend,
                progress_cb=emit_progress,
            )
            if "error" not in result:
                record = BacktestResult(
                    name=req.name,
                    start_date=req.start_date,
                    end_date=req.end_date,
                    config=result["config"],
                    metrics=result["metrics"],
                    trades=result["trades"],
                    equity_curve=result["equity_curve"],
                )
                db.add(record)
                await db.commit()
                await emit_progress("回測完成並已儲存", phase="done", current=100, total=100)
    except Exception as e:
        await emit_progress(f"回測失敗: {e}", phase="error", current=0, total=100)
    finally:
        _backtest_running = False


@router.post("/run")
async def trigger_backtest(req: BacktestRequest, background_tasks: BackgroundTasks):
    global _backtest_running
    if _backtest_running:
        return {"message": "回測已在執行中"}
    background_tasks.add_task(_run_and_save, req)
    return {"message": "回測已啟動，請訂閱 /sse/progress 查看進度"}


@router.get("/results")
async def list_results(limit: int = 20, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(BacktestResult).order_by(BacktestResult.created_at.desc()).limit(limit)
    )).scalars().all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "start_date": r.start_date.isoformat(),
            "end_date": r.end_date.isoformat(),
            "metrics": r.metrics,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/results/{result_id}")
async def get_result(result_id: int, db: AsyncSession = Depends(get_db)):
    r = (await db.execute(select(BacktestResult).where(BacktestResult.id == result_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(404)
    return {
        "id": r.id, "name": r.name,
        "start_date": r.start_date.isoformat(), "end_date": r.end_date.isoformat(),
        "config": r.config, "metrics": r.metrics,
        "trades": r.trades, "equity_curve": r.equity_curve,
    }


@router.post("/optimize")
async def trigger_optimize(
    start_date: date, end_date: date,
    background_tasks: BackgroundTasks,
):
    async def _run():
        async with AsyncSessionLocal() as db:
            results = await optimize_weights(db, start_date, end_date, progress_cb=emit_progress)
            await emit_progress("最佳化完成", phase="done", current=100, total=100)
            from ..sse.manager import sse_manager
            await sse_manager.broadcast("optimize_complete", {"results": results})
    background_tasks.add_task(_run)
    return {"message": "最佳化已啟動"}


@router.get("/status")
async def backtest_status():
    return {"running": _backtest_running}
