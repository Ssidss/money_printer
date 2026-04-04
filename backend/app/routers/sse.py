from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..sse.manager import sse_manager

router = APIRouter(tags=["sse"])


@router.get("/sse/progress")
async def sse_progress():
    """SSE 端點：訂閱所有進度事件（分析進度、回測進度）"""
    async def event_stream():
        async for msg in sse_manager.subscribe():
            yield msg

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
