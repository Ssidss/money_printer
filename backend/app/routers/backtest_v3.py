"""
Backtest V3 API — Multi-Strategy Engine

Phase 1B endpoints:
  POST /backtest-v3/run     — 啟動回測（背景執行）
  GET  /backtest-v3/status   — 查詢執行狀態
  GET  /backtest-v3/result   — 取得最近一次結果
  GET  /backtest-v3/splits   — 列出可用 data splits
"""
from __future__ import annotations

import logging
import time
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from ..database import AsyncSessionLocal
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


class SplitInfo(BaseModel):
    name: str
    start_date: str
    end_date: str


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
