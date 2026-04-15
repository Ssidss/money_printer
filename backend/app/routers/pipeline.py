"""
Pipeline Router — 回測迭代 Pipeline API

Endpoints:
  POST /api/v1/pipeline/run    — 啟動 pipeline（背景執行）
  GET  /api/v1/pipeline/status — 查詢當前狀態
  GET  /api/v1/pipeline/report — 取得最新驗證報告
  POST /api/v1/pipeline/stop   — 停止運行中的 pipeline
"""

import asyncio
import logging
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, field_validator

from ..sse.manager import sse_manager

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
    status: str  # "idle" | "running" | "completed" | "failed" | "stopped"
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
_cancel_event = asyncio.Event()  # 用於停止信號


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/run")
async def trigger_pipeline(req: PipelineRunRequest, background_tasks: BackgroundTasks):
    """
    啟動 Pipeline。

    背景執行，通過 SSE `/sse/progress` 推送進度。
    Pipeline 運行記錄會被保存到數據庫。

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
    from ..services.pipeline_service import PipelineService

    global _current_run, _cancel_event

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

    # 重置 cancel event
    _cancel_event.clear()

    run_id = f"pipeline-{uuid.uuid4().hex[:8]}"
    _current_run = {
        "run_id": run_id,
        "status": "running",
        "current_iteration": 0,
        "win_rate_history": [],
        "error": None,
    }

    # 建立 pipeline run 記錄到數據庫
    try:
        await PipelineService.create_pipeline_run(
            run_id=run_id,
            symbols=req.symbols,
            train_start=train_start,
            train_end=train_end,
            val_start=val_start,
            val_end=val_end,
            status="running",
            strategies=req.strategies,
            timeframe=req.timeframe,
            max_iterations=req.max_iterations,
            convergence_threshold=req.convergence_threshold,
        )
        logger.info(f"Pipeline run record created in database: {run_id}")
    except Exception as e:
        logger.error(f"Failed to create pipeline run record: {e}", exc_info=True)
        # 不中斷流程，即使數據庫記錄失敗

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


@router.post("/stop")
async def stop_pipeline():
    """
    停止運行中的 Pipeline。

    如果沒有 pipeline 運行中，返回 409。
    如果成功停止，返回 200 並設置取消信號。

    Pipeline 會在下一個迴圈檢查點停止並設置狀態為 cancelled。
    cancelled 狀態會被記錄到數據庫。

    Response:
    ```json
    {
      "message": "Pipeline stopped",
      "status": "stopped"
    }
    ```
    """
    from ..services.pipeline_service import PipelineService

    global _current_run, _cancel_event

    # 檢查是否有運行中的 pipeline
    if _current_run is None or _current_run.get("status") != "running":
        raise HTTPException(
            status_code=409,
            detail="Pipeline is not running"
        )

    run_id = _current_run.get("run_id")

    # 設置取消信號
    _cancel_event.set()

    # 更新狀態為 stopped（待背景任務更新為 cancelled）
    _current_run["status"] = "stopped"

    # 記錄 cancelled 狀態到數據庫
    try:
        await PipelineService.mark_as_cancelled(run_id)
        logger.info(f"Pipeline {run_id} marked as cancelled in database")
    except Exception as e:
        logger.error(f"Failed to record cancelled state: {e}", exc_info=True)
        # 不中斷流程，即使數據庫記錄失敗

    logger.info("Pipeline stop requested")

    # 發送停止事件
    await sse_manager.broadcast("pipeline_stop_requested", {
        "status": "stop_requested",
        "run_id": run_id,
    })

    return {
        "message": "Pipeline stopped",
        "status": "stopped",
    }


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
    from ..services.pipeline_service import PipelineService
    from ..services.run_memory_pipeline import run_pipeline

    global _current_run, _cancel_event

    async with _pipeline_lock:
        try:
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
                cancel_event=_cancel_event,
            )

            # 更新全域狀態
            run_id = None
            if _current_run is not None:
                run_id = _current_run.get("run_id")
                _current_run.update(result)
                _current_run["status"] = result.get("status", "unknown")

            # 更新數據庫中的狀態
            if run_id:
                try:
                    await PipelineService.update_pipeline_run(
                        run_id,
                        status=result.get("status", "unknown"),
                        current_iteration=result.get("iterations", 0),
                        win_rate_history=result.get("win_rate_history", []),
                        converged=result.get("converged", False),
                        validation_report=result.get("validation_report"),
                        error=result.get("error"),
                    )
                    logger.info(f"Pipeline run record updated in database: {run_id}")
                except Exception as e:
                    logger.error(f"Failed to update pipeline run record: {e}", exc_info=True)

            logger.info(f"Pipeline completed: {result}")

        except Exception as e:
            logger.error(f"Pipeline background task failed: {e}", exc_info=True)
            if _current_run is not None:
                _current_run["status"] = "failed"
                _current_run["error"] = str(e)

                # 也更新數據庫中的狀態
                run_id = _current_run.get("run_id")
                if run_id:
                    try:
                        from ..services.pipeline_service import PipelineService
                        await PipelineService.update_pipeline_run(
                            run_id,
                            status="failed",
                            error=str(e),
                        )
                    except Exception as db_error:
                        logger.error(f"Failed to update failed status in database: {db_error}", exc_info=True)
        finally:
            # 清除 cancel event 供下次使用
            _cancel_event.clear()
