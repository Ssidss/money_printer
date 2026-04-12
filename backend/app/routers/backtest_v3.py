"""
Backtest V3 API — Multi-Strategy Engine

Phase 1B + Phase E endpoints:
  POST /backtest-v3/run          — 啟動回測（背景執行）
  GET  /backtest-v3/status       — 查詢執行狀態
  GET  /backtest-v3/result       — 取得最近一次結果
  GET  /backtest-v3/splits       — 列出可用 data splits

Phase E (History + Compare):
  GET  /backtest-v3/history      — 列出歷史回測結果
  GET  /backtest-v3/history/{id} — 取得單筆歷史結果
  DELETE /backtest-v3/history/{id} — 刪除單筆歷史結果
  GET  /backtest-v3/compare      — 比較兩筆回測結果
"""
from __future__ import annotations

import logging
import time
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.orm import load_only

from ..database import AsyncSessionLocal
from ..models.backtest import BacktestResultV3
from ..services.backtester_v2 import load_all_price_data
from ..services.backtest_v3 import (
    BacktestEngine, HistoricalProvider,
    SMCStrategy, MomentumBreakoutStrategy, ExplosionScannerStrategy,
    SizingModel, ExecutionModel, KillSwitch,
    calculate_metrics,
)
from ..services.backtest_v3.provider import DATA_SPLITS, get_split_dates
from ..sse.manager import emit_progress

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest-v3", tags=["backtest_v3"])

# ── In-memory state ───────────────────────────────────────────────
_running = False
_last_result: Optional[dict] = None
_last_error: Optional[str] = None


# ── Request / Response schemas ────────────────────────────────────

class V3RunRequest(BaseModel):
    split: str = "validation"
    start_date: Optional[str] = None  # YYYY-MM-DD, overrides split
    end_date: Optional[str] = None
    initial_capital: float = 100_000
    min_conditions: int = 3
    min_rr: float = 2.0
    max_positions: int = 8
    risk_per_trade_pct: float = 1.0
    max_daily_loss_pct: float = 8.0
    market_filter: str = "US"
    strategies: list[str] = ["smc_v2"]  # "smc_v2", "momentum_breakout", "explosion_scanner"
    save_name: Optional[str] = None  # Phase E: optional name for history


class SplitInfo(BaseModel):
    name: str
    start_date: str
    end_date: str


# ── Persistence helper ───────────────────────────────────────────

async def _save_result(report: dict, req: V3RunRequest, split_name: str, start: date, end: date):
    """把回測結果存入 DB"""
    s = report.get("portfolio_summary", {})
    meta = report.get("metadata", {})

    record = BacktestResultV3(
        name=req.save_name,
        split=split_name,
        start_date=start,
        end_date=end,
        strategies=req.strategies,
        total_return_pct=s.get("total_return_pct"),
        cagr_pct=s.get("cagr_pct"),
        max_drawdown_pct=s.get("max_drawdown_pct"),
        sharpe_ratio=s.get("sharpe_ratio"),
        win_rate_pct=s.get("win_rate_pct"),
        profit_factor=s.get("profit_factor"),
        total_trades=s.get("total_trades"),
        params={
            "initial_capital": req.initial_capital,
            "min_conditions": req.min_conditions,
            "min_rr": req.min_rr,
            "max_positions": req.max_positions,
            "risk_per_trade_pct": req.risk_per_trade_pct,
            "max_daily_loss_pct": req.max_daily_loss_pct,
            "market_filter": req.market_filter,
        },
        report=report,
        duration_seconds=meta.get("duration_seconds"),
        stock_count=meta.get("stock_count"),
        trading_days=meta.get("trading_days"),
    )

    async with AsyncSessionLocal() as db:
        db.add(record)
        await db.commit()
        await db.refresh(record)
        logger.info(f"V3 回測結果已保存 (id={record.id})")
        return record.id


# ── Background runner ─────────────────────────────────────────────

async def _run_v3(req: V3RunRequest):
    global _running, _last_result, _last_error
    _running = True
    _last_error = None

    try:
        # Resolve dates
        if req.start_date and req.end_date:
            start = date.fromisoformat(req.start_date)
            end = date.fromisoformat(req.end_date)
            split_name = "custom"
        else:
            start, end = get_split_dates(req.split)
            split_name = req.split

        await emit_progress(f"載入 {req.market_filter} 市場數據...", "loading", 0, 100)

        t0 = time.time()
        async with AsyncSessionLocal() as db:
            stocks_info, price_data = await load_all_price_data(db, market_filter=req.market_filter)

        await emit_progress(
            f"已載入 {len(price_data)} 檔股票 ({time.time()-t0:.1f}s)",
            "loaded", 5, 100,
        )

        # Build engine
        provider = HistoricalProvider(
            price_data=price_data,
            stocks_info=stocks_info,
            start_date=start,
            end_date=end,
        )

        # Build strategy list
        STRATEGY_BUILDERS = {
            "smc_v2": lambda: SMCStrategy(
                min_conditions=req.min_conditions,
                min_rr=req.min_rr,
                market=req.market_filter,
            ),
            "momentum_breakout": lambda: MomentumBreakoutStrategy(
                min_rr=req.min_rr,
            ),
            "explosion_scanner": lambda: ExplosionScannerStrategy(),
        }
        strategies = []
        for name in req.strategies:
            builder = STRATEGY_BUILDERS.get(name)
            if builder:
                strategies.append(builder())
            else:
                logger.warning(f"Unknown strategy: {name}")
        if not strategies:
            await emit_progress(f"未知策略: {req.strategies}，使用預設 SMC", "warning", 5, 100)
            strategies = [SMCStrategy(min_conditions=req.min_conditions, min_rr=req.min_rr)]

        sizing = SizingModel(
            risk_per_trade_pct=req.risk_per_trade_pct,
            max_position_pct=20.0,
            max_positions=req.max_positions,
        )

        execution = ExecutionModel(
            fill_type="next_open",
            slippage_pct=0.05,
            gap_threshold_pct=5.0,
        )

        kill_switch = KillSwitch(
            enabled=True,
            max_drawdown_pct=50.0,      # 放寬到 50%，避免長期回測被提前終止
            max_consecutive_losses=20,   # 放寬連虧上限
            max_daily_loss_pct=req.max_daily_loss_pct,
        )

        engine = BacktestEngine(
            strategies=strategies,
            provider=provider,
            initial_capital=req.initial_capital,
            sizing=sizing,
            execution=execution,
            kill_switch=kill_switch,
        )

        # Run
        t0 = time.time()

        async def progress_cb(msg, pct):
            # Map engine progress (0-100) to overall (10-90)
            overall = 10 + pct * 0.8
            await emit_progress(msg, "running", overall, 100)

        result = await engine.run(progress_cb=progress_cb)
        duration = time.time() - t0

        await emit_progress("計算指標...", "metrics", 92, 100)

        report = calculate_metrics(result)
        report["metadata"] = {
            "split": split_name,
            "start_date": str(start),
            "end_date": str(end),
            "initial_capital": req.initial_capital,
            "min_conditions": req.min_conditions,
            "min_rr": req.min_rr,
            "max_positions": req.max_positions,
            "risk_per_trade_pct": req.risk_per_trade_pct,
            "max_daily_loss_pct": req.max_daily_loss_pct,
            "strategies": req.strategies,
            "duration_seconds": round(duration, 1),
            "stock_count": len(price_data),
            "trading_days": provider.total_days,
        }

        _last_result = report

        # Phase E: persist to DB
        try:
            saved_id = await _save_result(report, req, split_name, start, end)
            report["metadata"]["saved_id"] = saved_id
        except Exception as e:
            logger.warning(f"Failed to save V3 result to DB: {e}")

        await emit_progress("V3 回測完成", "done", 100, 100)

    except Exception as e:
        logger.exception("V3 backtest failed")
        _last_error = str(e)
        await emit_progress(f"V3 回測失敗: {e}", "error", 0, 100)
    finally:
        _running = False


# ── Endpoints ─────────────────────────────────────────────────────

@router.post("/run")
async def trigger_v3(req: V3RunRequest, background_tasks: BackgroundTasks):
    global _running
    if _running:
        return {"message": "V3 回測正在執行中", "status": "running"}
    background_tasks.add_task(_run_v3, req)
    return {"message": "V3 回測已啟動，訂閱 /sse/progress 查看進度", "status": "started"}


@router.get("/status")
async def v3_status():
    return {
        "running": _running,
        "has_result": _last_result is not None,
        "error": _last_error,
    }


@router.get("/result")
async def v3_result():
    if _running:
        raise HTTPException(202, "回測執行中，請稍候")
    if _last_result is None:
        raise HTTPException(404, "尚無回測結果，請先執行 POST /backtest-v3/run")
    return _last_result


@router.get("/result/summary")
async def v3_summary():
    """只回傳 portfolio_summary + metadata（輕量）"""
    if _last_result is None:
        raise HTTPException(404, "尚無回測結果")
    return {
        "portfolio_summary": _last_result["portfolio_summary"],
        "metadata": _last_result.get("metadata", {}),
    }


@router.get("/result/trades")
async def v3_trades(
    limit: int = Query(50, le=500),
    offset: int = 0,
    strategy: Optional[str] = None,
    tier: Optional[str] = None,
):
    """Trade log with optional filters"""
    if _last_result is None:
        raise HTTPException(404, "尚無回測結果")
    trades = _last_result.get("trade_log", [])
    if strategy:
        trades = [t for t in trades if t.get("strategy_name") == strategy]
    if tier:
        trades = [t for t in trades if t.get("position_tier") == tier]
    return {
        "total": len(trades),
        "trades": trades[offset:offset + limit],
    }


@router.get("/result/equity")
async def v3_equity():
    """Equity curve"""
    if _last_result is None:
        raise HTTPException(404, "尚無回測結果")
    return _last_result.get("equity_curve", [])


@router.get("/splits", response_model=list[SplitInfo])
async def list_splits():
    return [
        SplitInfo(name=name, start_date=str(s), end_date=str(e))
        for name, (s, e) in DATA_SPLITS.items()
    ]


# ── Phase E: History endpoints ───────────────────────────────────

@router.get("/history")
async def list_history(
    limit: int = Query(20, le=100),
    offset: int = 0,
    strategy: Optional[str] = None,
):
    """列出歷史回測結果（摘要，不含完整報告）"""
    # 不載入 report blob — 列表只需要摘要欄位
    _list_cols = load_only(
        BacktestResultV3.id, BacktestResultV3.name,
        BacktestResultV3.split, BacktestResultV3.start_date, BacktestResultV3.end_date,
        BacktestResultV3.strategies,
        BacktestResultV3.total_return_pct, BacktestResultV3.cagr_pct,
        BacktestResultV3.max_drawdown_pct, BacktestResultV3.sharpe_ratio,
        BacktestResultV3.win_rate_pct, BacktestResultV3.profit_factor,
        BacktestResultV3.total_trades, BacktestResultV3.params,
        BacktestResultV3.duration_seconds, BacktestResultV3.stock_count,
        BacktestResultV3.trading_days, BacktestResultV3.created_at,
    )

    async with AsyncSessionLocal() as db:
        q = select(BacktestResultV3).options(_list_cols).order_by(desc(BacktestResultV3.created_at))

        # 按策略篩選（JSONB contains）
        if strategy:
            q = q.where(BacktestResultV3.strategies.contains([strategy]))

        q = q.offset(offset).limit(limit)
        rows = (await db.execute(q)).scalars().all()

        count_q = select(func.count(BacktestResultV3.id))
        if strategy:
            count_q = count_q.where(BacktestResultV3.strategies.contains([strategy]))
        total = (await db.execute(count_q)).scalar() or 0

    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "split": r.split,
                "start_date": str(r.start_date),
                "end_date": str(r.end_date),
                "strategies": r.strategies,
                "total_return_pct": r.total_return_pct,
                "cagr_pct": r.cagr_pct,
                "max_drawdown_pct": r.max_drawdown_pct,
                "sharpe_ratio": r.sharpe_ratio,
                "win_rate_pct": r.win_rate_pct,
                "profit_factor": r.profit_factor,
                "total_trades": r.total_trades,
                "params": r.params,
                "duration_seconds": r.duration_seconds,
                "stock_count": r.stock_count,
                "trading_days": r.trading_days,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/history/{result_id}")
async def get_history_detail(result_id: int):
    """取得單筆歷史回測的完整報告"""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(BacktestResultV3).where(BacktestResultV3.id == result_id)
        )).scalar_one_or_none()

    if not row:
        raise HTTPException(404, f"回測結果 {result_id} 不存在")

    return row.report


@router.delete("/history/{result_id}")
async def delete_history(result_id: int):
    """刪除單筆歷史回測結果"""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(BacktestResultV3).where(BacktestResultV3.id == result_id)
        )).scalar_one_or_none()

        if not row:
            raise HTTPException(404, f"回測結果 {result_id} 不存在")

        await db.delete(row)
        await db.commit()

    return {"message": f"回測結果 {result_id} 已刪除"}


@router.get("/compare")
async def compare_results(
    a: int = Query(..., description="回測結果 A 的 ID"),
    b: int = Query(..., description="回測結果 B 的 ID"),
):
    """比較兩筆回測結果 — 回傳並排指標 + 參數差異"""
    async with AsyncSessionLocal() as db:
        row_a = (await db.execute(
            select(BacktestResultV3).where(BacktestResultV3.id == a)
        )).scalar_one_or_none()
        row_b = (await db.execute(
            select(BacktestResultV3).where(BacktestResultV3.id == b)
        )).scalar_one_or_none()

    if not row_a:
        raise HTTPException(404, f"回測結果 {a} 不存在")
    if not row_b:
        raise HTTPException(404, f"回測結果 {b} 不存在")

    def _extract_summary(row):
        report = row.report or {}
        s = report.get("portfolio_summary", {})
        return {
            "id": row.id,
            "name": row.name,
            "split": row.split,
            "start_date": str(row.start_date),
            "end_date": str(row.end_date),
            "strategies": row.strategies,
            "params": row.params,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "metrics": {
                "total_return_pct": s.get("total_return_pct"),
                "cagr_pct": s.get("cagr_pct"),
                "max_drawdown_pct": s.get("max_drawdown_pct"),
                "sharpe_ratio": s.get("sharpe_ratio"),
                "sortino_ratio": s.get("sortino_ratio"),
                "win_rate_pct": s.get("win_rate_pct"),
                "profit_factor": s.get("profit_factor"),
                "total_trades": s.get("total_trades"),
                "avg_holding_days": s.get("avg_holding_days"),
                "expectancy": s.get("expectancy"),
                "avg_win_pct": s.get("avg_win_pct"),
                "avg_loss_pct": s.get("avg_loss_pct"),
                "tail_risk_cvar_5pct": s.get("tail_risk_cvar_5pct"),
                "avg_exposure_pct": s.get("avg_exposure_pct"),
            },
            "strategy_breakdown": report.get("strategy_breakdown", {}),
        }

    sa = _extract_summary(row_a)
    sb = _extract_summary(row_b)

    # 參數差異
    params_diff = {}
    all_keys = set(list(sa["params"].keys()) + list(sb["params"].keys()))
    for k in sorted(all_keys):
        va = sa["params"].get(k)
        vb = sb["params"].get(k)
        if va != vb:
            params_diff[k] = {"a": va, "b": vb}

    return {
        "a": sa,
        "b": sb,
        "params_diff": params_diff,
    }
