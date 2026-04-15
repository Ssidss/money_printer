"""
Pipeline Router — 回測迭代 Pipeline API

Endpoints:
  POST /api/v1/pipeline/run    — 啟動 pipeline（背景執行）
  GET  /api/v1/pipeline/status — 查詢當前狀態
  GET  /api/v1/pipeline/report — 取得最新驗證報告
"""

import asyncio
import logging
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


# ── Request / Response schemas ────────────────────────────────────────────────

class PipelineRunRequest(BaseModel):
    """Pipeline 運行請求"""
    symbols: list[str]
    train_start: str  # YYYY-MM-DD
    train_end: str    # YYYY-MM-DD
    val_start: str    # YYYY-MM-DD
    val_end: str      # YYYY-MM-DD
    strategies: list[str] = ["smc_v2"]
    timeframe: str = "1d"
    max_iterations: int = 5
    convergence_threshold: float = 0.02

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: list[str]) -> list[str]:
        if not v or len(v) == 0:
            raise ValueError("symbols list cannot be empty")
        return v

    @field_validator("train_start", "train_end", "val_start", "val_end")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError(f"Invalid date format: '{v}', expected YYYY-MM-DD")
        return v


class PipelineStatus(BaseModel):
    """Pipeline 狀態回應"""
    running: bool
    current_iteration: int
    win_rate_history: list[float]
    status: str  # "idle" | "running" | "completed" | "failed"
    error: Optional[str] = None


class PipelineReport(BaseModel):
    """驗證報告"""
    symbols: list[str]
    total_trades: int
    total_wins: int
    total_losses: int
    avg_win_rate: float
    avg_return: float


# ── Global State ──────────────────────────────────────────────────────────────

_pipeline_lock = asyncio.Lock()
_current_run: Optional[dict] = None  # { 'status', 'iterations', 'win_rate_history', ... }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/run")
async def trigger_pipeline(req: PipelineRunRequest, background_tasks: BackgroundTasks):
    """
    啟動 Pipeline。

    背景執行，通過 SSE `/sse/progress` 推送進度。

    Request:
    ```json
    {
      "symbols": ["2330", "2454"],
      "train_start": "2024-01-01",
      "train_end": "2024-12-31",
      "val_start": "2025-01-01",
      "val_end": "2025-03-31",
      "strategies": ["smc_v2"],
      "timeframe": "1d",
      "max_iterations": 5,
      "convergence_threshold": 0.02
    }
    ```

    Response:
    ```json
    {
      "message": "Pipeline started",
      "run_id": "pipeline-xxxxx"
    }
    ```
    """
    global _current_run

    # 檢查是否已有 pipeline 運行中（使用同步全域狀態作為原子判斷）
    # asyncio 單執行緒保證此判斷為原子操作
    if _current_run is not None and _current_run.get("status") == "running":
        raise HTTPException(
            status_code=409,
            detail="Pipeline is already running. Wait for completion or check /pipeline/status"
        )

    # 解析日期
    try:
        train_start = date.fromisoformat(req.train_start)
        train_end = date.fromisoformat(req.train_end)
        val_start = date.fromisoformat(req.val_start)
        val_end = date.fromisoformat(req.val_end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 驗證日期範圍
    if train_end <= train_start:
        raise HTTPException(status_code=400, detail="train_end must be after train_start")
    if val_end <= val_start:
        raise HTTPException(status_code=400, detail="val_end must be after val_start")

    run_id = f"pipeline-{uuid.uuid4().hex[:8]}"
    _current_run = {
        "run_id": run_id,
        "status": "running",
        "current_iteration": 0,
        "win_rate_history": [],
        "error": None,
    }

    # 加入背景任務
    background_tasks.add_task(
        _run_pipeline_background,
        symbols=req.symbols,
        train_start=train_start,
        train_end=train_end,
        val_start=val_start,
        val_end=val_end,
        strategies=req.strategies,
        timeframe=req.timeframe,
        max_iterations=req.max_iterations,
        convergence_threshold=req.convergence_threshold,
    )

    logger.info(f"Pipeline started: {run_id}")

    return {
        "message": "Pipeline started, subscribe to /sse/progress for updates",
        "run_id": run_id,
    }


@router.get("/status")
async def get_pipeline_status() -> PipelineStatus:
    """
    查詢 Pipeline 當前狀態。

    Response:
    ```json
    {
      "running": true,
      "current_iteration": 2,
      "win_rate_history": [45.2, 48.5],
      "status": "running",
      "error": null
    }
    ```
    """
    global _current_run

    if _current_run is None:
        return PipelineStatus(
            running=False,
            current_iteration=0,
            win_rate_history=[],
            status="idle",
        )

    return PipelineStatus(
        running=_current_run["status"] == "running",
        current_iteration=_current_run.get("current_iteration", 0),
        win_rate_history=_current_run.get("win_rate_history", []),
        status=_current_run["status"],
        error=_current_run.get("error"),
    )


@router.get("/report")
async def get_pipeline_report() -> dict:
    """
    取得最新驗證報告。

    Response:
    ```json
    {
      "symbols": ["2330", "2454"],
      "total_trades": 150,
      "total_wins": 90,
      "total_losses": 60,
      "avg_win_rate": 0.6,
      "avg_return": 0.085
    }
    ```
    """
    global _current_run

    if _current_run is None or _current_run.get("validation_report") is None:
        return {
            "symbols": [],
            "total_trades": 0,
            "total_wins": 0,
            "total_losses": 0,
            "avg_win_rate": 0,
            "avg_return": 0,
        }

    return _current_run["validation_report"]


# ── Background Task ───────────────────────────────────────────────────────────

async def _run_pipeline_background(
    symbols: list[str],
    train_start: date,
    train_end: date,
    val_start: date,
    val_end: date,
    strategies: list[str],
    timeframe: str,
    max_iterations: int,
    convergence_threshold: float,
):
    """背景執行 Pipeline"""
    global _current_run

    async with _pipeline_lock:
        try:
            from ..services.run_memory_pipeline import run_pipeline

            result = await run_pipeline(
                symbols=symbols,
                train_start=train_start,
                train_end=train_end,
                val_start=val_start,
                val_end=val_end,
                strategies=strategies,
                timeframe=timeframe,
                max_iterations=max_iterations,
                convergence_threshold=convergence_threshold,
            )

            # 更新全域狀態
            if _current_run is not None:
                _current_run.update(result)
                _current_run["status"] = result.get("status", "unknown")

            logger.info(f"Pipeline completed: {result}")

        except Exception as e:
            logger.error(f"Pipeline background task failed: {e}", exc_info=True)
            if _current_run is not None:
                _current_run["status"] = "failed"
                _current_run["error"] = str(e)
