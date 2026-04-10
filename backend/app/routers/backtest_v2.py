"""
Backtest V2 API — 執行回測 + 查詢結果
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db, AsyncSessionLocal
from ..models.strategy import (
    StrategyProfile, BacktestResultV2, BacktestTrade, BacktestEquity,
)
from ..schemas.strategy import (
    BacktestRunRequest, BacktestResultOut, BacktestTradeOut, BacktestEquityOut,
    BacktestCompareOut,
)
from ..services.backtester_v2 import run_backtest_v2
from ..sse.manager import emit_progress

router = APIRouter(prefix="/backtest", tags=["backtest_v2"])

_running = False


async def _run_and_save(req: BacktestRunRequest):
    """背景執行回測並存入 DB"""
    global _running
    _running = True
    bt_id: int | None = None

    try:
        async with AsyncSessionLocal() as db:
            # 讀取 profile
            profile = (await db.execute(
                select(StrategyProfile).where(StrategyProfile.id == req.profile_id)
            )).scalar_one_or_none()
            if not profile:
                await emit_progress("找不到策略檔案", "error", 0, 100)
                return

            # 建立 pending 記錄
            bt = BacktestResultV2(
                profile_id=profile.id,
                name=f"{profile.name} 回測",
                start_date=req.start_date,
                end_date=req.end_date,
                initial_capital=req.initial_capital,
                market_filter=req.market_filter,
                params_snapshot=profile.params,
                strategy_hash="",
                run_hash="",
                stock_universe=[],
                metrics={},
                status="running",
            )
            db.add(bt)
            await db.commit()
            await db.refresh(bt)
            bt_id = bt.id

            # 執行回測
            result = await run_backtest_v2(
                db=db,
                params=profile.params,
                overrides=profile.overrides,
                stock_settings=profile.stock_settings,
                start_date=req.start_date,
                end_date=req.end_date,
                initial_capital=req.initial_capital,
                market_filter=req.market_filter,
                progress_cb=emit_progress,
            )

            if "error" in result:
                bt.status = "failed"
                bt.error_message = result["error"]
                await db.commit()
                await emit_progress(f"回測失敗: {result['error']}", "error", 0, 100)
                return

            # 更新主表
            bt.strategy_hash = result["strategy_hash"]
            bt.run_hash = result["run_hash"]
            bt.data_hash = result.get("data_hash")
            bt.stock_universe = result["stock_universe"]
            bt.metrics = result["metrics"]
            bt.diagnosis = result.get("diagnosis")
            bt.duration_secs = result.get("duration_secs")
            bt.stock_count = result.get("stock_count")
            bt.trading_days = result.get("trading_days")
            bt.status = "done"

            # 批次寫入 trades
            for t in result["trades"]:
                db.add(BacktestTrade(
                    backtest_id=bt.id,
                    ticker=t["ticker"], market=t["market"], stock_group=t.get("stock_group"),
                    signal_date=t["signal_date"], fill_date=t["fill_date"],
                    fill_price=t["fill_price"], entry_source=t.get("entry_source"),
                    position_tier=t.get("position_tier"), conditions_met=t.get("conditions_met"),
                    position_size_pct=t.get("position_size_pct"),
                    exit_date=t.get("exit_date"), exit_price=t.get("exit_price"),
                    exit_reason=t.get("exit_reason"),
                    stop_source=t.get("stop_source"), target_source=t.get("target_source"),
                    planned_rr=t.get("planned_rr"), actual_rr=t.get("actual_rr"),
                    pnl_pct=t.get("pnl_pct"), pnl_amount=t.get("pnl_amount"),
                    trade_cost=t.get("trade_cost"), net_pnl=t.get("net_pnl"),
                    holding_days=t.get("holding_days"),
                    mae_pct=t.get("mae_pct"), mfe_pct=t.get("mfe_pct"),
                    smc_trend_at_entry=t.get("smc_trend_at_entry"),
                    smc_trend_at_exit=t.get("smc_trend_at_exit"),
                ))

            # 批次寫入 equity curve
            for e in result["equity_curve"]:
                db.add(BacktestEquity(
                    backtest_id=bt.id,
                    trade_date=e["trade_date"],
                    equity=e["equity"],
                    drawdown_pct=e.get("drawdown_pct"),
                    cash=e.get("cash"),
                    positions_value=e.get("positions_value"),
                    open_positions=e.get("open_positions"),
                ))

            # 更新 profile 的最近回測
            profile.latest_backtest_id = bt.id
            await db.commit()

            await emit_progress("回測完成並已儲存", "done", 100, 100)

    except Exception as e:
        if bt_id:
            try:
                async with AsyncSessionLocal() as db2:
                    bt2 = (await db2.execute(
                        select(BacktestResultV2).where(BacktestResultV2.id == bt_id)
                    )).scalar_one_or_none()
                    if bt2:
                        bt2.status = "failed"
                        bt2.error_message = str(e)
                        await db2.commit()
            except Exception:
                pass
        await emit_progress(f"回測失敗: {e}", "error", 0, 100)
    finally:
        _running = False


@router.post("/run")
async def trigger_backtest(req: BacktestRunRequest, background_tasks: BackgroundTasks):
    global _running
    if _running:
        return {"message": "回測已在執行中"}
    background_tasks.add_task(_run_and_save, req)
    return {"message": "回測已啟動，請訂閱 /sse/progress 查看進度"}


@router.get("/status")
async def backtest_status():
    return {"running": _running}


@router.get("/results", response_model=list[BacktestResultOut])
async def list_results(
    profile_id: int | None = None,
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = select(BacktestResultV2).order_by(BacktestResultV2.created_at.desc())
    if profile_id is not None:
        q = q.where(BacktestResultV2.profile_id == profile_id)
    q = q.limit(limit).offset(offset)
    rows = (await db.execute(q)).scalars().all()
    return rows


@router.get("/results/{result_id}", response_model=BacktestResultOut)
async def get_result(result_id: int, db: AsyncSession = Depends(get_db)):
    r = (await db.execute(
        select(BacktestResultV2).where(BacktestResultV2.id == result_id)
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(404)
    return r


@router.get("/results/{result_id}/trades", response_model=list[BacktestTradeOut])
async def get_trades(
    result_id: int,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(BacktestTrade)
        .where(BacktestTrade.backtest_id == result_id)
        .order_by(BacktestTrade.fill_date)
        .limit(limit).offset(offset)
    )).scalars().all()
    return rows


@router.get("/results/{result_id}/equity", response_model=list[BacktestEquityOut])
async def get_equity(result_id: int, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(BacktestEquity)
        .where(BacktestEquity.backtest_id == result_id)
        .order_by(BacktestEquity.trade_date)
    )).scalars().all()
    return rows


@router.get("/compare")
async def compare_results(
    a: int = Query(...), b: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    ra = (await db.execute(select(BacktestResultV2).where(BacktestResultV2.id == a))).scalar_one_or_none()
    rb = (await db.execute(select(BacktestResultV2).where(BacktestResultV2.id == b))).scalar_one_or_none()
    if not ra or not rb:
        raise HTTPException(404, "回測結果不存在")

    # params diff
    params_a = ra.params_snapshot or {}
    params_b = rb.params_snapshot or {}
    all_keys = sorted(set(list(params_a.keys()) + list(params_b.keys())))
    params_diff = [
        {"key": k, "a": params_a.get(k), "b": params_b.get(k)}
        for k in all_keys
        if params_a.get(k) != params_b.get(k)
    ]

    # equity curves (sampled weekly for comparison)
    eq_a = (await db.execute(
        select(BacktestEquity).where(BacktestEquity.backtest_id == a).order_by(BacktestEquity.trade_date)
    )).scalars().all()
    eq_b = (await db.execute(
        select(BacktestEquity).where(BacktestEquity.backtest_id == b).order_by(BacktestEquity.trade_date)
    )).scalars().all()

    return {
        "profile_a": {"id": ra.profile_id, "name": ra.name, "metrics": ra.metrics},
        "profile_b": {"id": rb.profile_id, "name": rb.name, "metrics": rb.metrics},
        "params_diff": params_diff,
        "metrics_comparison": {
            k: {"a": ra.metrics.get(k), "b": rb.metrics.get(k)}
            for k in ["total_return_pct", "max_drawdown_pct", "sharpe_ratio", "win_rate", "profit_factor", "total_trades"]
        },
        "equity_a": [{"date": str(e.trade_date), "equity": float(e.equity)} for e in eq_a],
        "equity_b": [{"date": str(e.trade_date), "equity": float(e.equity)} for e in eq_b],
    }
