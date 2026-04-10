from __future__ import annotations
"""
量價異常掃描器 API

GET  /scanner          — 取得最新掃描結果（僅追蹤股票，快速）
POST /scanner/run      — 啟動完整掃描（追蹤 + 外部池，背景）
GET  /scanner/tracked  — 僅掃描追蹤股票（同步，快速）
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db, AsyncSessionLocal
from ..services.scanner import scan_tracked_stocks, scan_all
from ..sse.manager import emit_progress

router = APIRouter(prefix="/scanner", tags=["scanner"])

# 快取最新掃描結果（記憶體中，重啟後消失）
_latest_scan: dict | None = None
_scan_running = False


@router.get("")
async def get_latest_scan():
    """取得最新掃描結果（如果有的話）"""
    if _latest_scan is None:
        return {"scan_date": None, "results": [], "total_count": 0, "message": "尚未執行掃描，請先觸發 POST /scanner/run"}
    return _latest_scan


@router.get("/tracked")
async def scan_tracked_only(
    min_score: float = Query(15, description="最低爆擊分數門檻"),
    db: AsyncSession = Depends(get_db),
):
    """僅掃描追蹤股票（同步，快速）"""
    results = await scan_tracked_stocks(db, min_score=min_score)
    return {
        "scan_date": __import__("datetime").date.today().isoformat(),
        "tracked_count": len(results),
        "external_count": 0,
        "total_count": len(results),
        "results": [r.to_dict() for r in results],
    }


@router.post("/run")
async def trigger_full_scan(
    include_external: bool = Query(True, description="是否掃描外部股票池"),
    min_score: float = Query(15, description="最低爆擊分數門檻"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """啟動完整掃描（追蹤 + 外部池，背景執行）"""
    global _scan_running
    if _scan_running:
        return {"message": "掃描進行中…", "running": True}

    _scan_running = True
    background_tasks.add_task(_run_full_scan, include_external, min_score)
    return {"message": "掃描已啟動", "running": True}


@router.get("/status")
async def scan_status():
    """掃描狀態"""
    return {"running": _scan_running}


async def _run_full_scan(include_external: bool, min_score: float):
    global _latest_scan, _scan_running
    try:
        async with AsyncSessionLocal() as db:
            result = await scan_all(
                db,
                include_external=include_external,
                min_score=min_score,
                progress_cb=_progress_cb,
            )
            _latest_scan = result
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"掃描失敗: {e}")
        await emit_progress(f"掃描失敗: {e}", phase="error")
    finally:
        _scan_running = False


async def _progress_cb(msg: str, **kwargs):
    await emit_progress(msg, **kwargs)
