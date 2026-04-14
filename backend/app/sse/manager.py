"""SSE Event Manager — 廣播即時進度給所有連線中的前端"""

import asyncio
import json
import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)


class SSEManager:
    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    def _new_queue(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._queues.append(q)
        return q

    def _remove_queue(self, q: asyncio.Queue):
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    async def broadcast(self, event: str, data: dict):
        """廣播事件給所有訂閱者"""
        msg = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        dead = []
        for q in self._queues:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._remove_queue(q)

    async def subscribe(self) -> AsyncIterator[str]:
        """生成器：讓 FastAPI SSE endpoint 訂閱事件流"""
        q = self._new_queue()
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=30)
                    yield msg
                except asyncio.TimeoutError:
                    # 定期發送 keepalive，維持連線但不中斷訂閱
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self._remove_queue(q)


# 全域單例
sse_manager = SSEManager()


async def emit_progress(
    message: str,
    phase: str = "running",
    current: int = 0,
    total: int = 100,
    ticker: str = "",
):
    """方便的進度推送函式"""
    await sse_manager.broadcast("progress", {
        "message": message,
        "phase": phase,
        "current": current,
        "total": total,
        "ticker": ticker,
        "pct": round(current / total * 100) if total > 0 else 0,
    })
