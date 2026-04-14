"""
KINA-264: 測試 GET /api/v1/ai-notes/performance 路由順序修復

當前問題：/{note_id} 路由定義在 /performance 之前，導致無法匹配
症狀：GET /api/v1/ai-notes/performance 返回 422（試圖解析 "performance" 為整數）

修復：重新排序路由定義，使 /performance 在 /{note_id} 之前
驗證：測試路由匹配順序正確
"""

import pytest
from fastapi.testclient import TestClient
from app.routers.ai_notes import router as ai_notes_router
from fastapi import FastAPI


def test_performance_route_before_parameterized_route():
    """
    驗證 /performance 路由在 /{note_id} 路由之前被定義。

    FastAPI 路由匹配順序：按定義順序進行。
    如果 /{note_id} 先被定義，會捕捉 /performance，導致 422 錯誤。

    此測試檢查路由定義順序。
    """
    app = FastAPI()
    app.include_router(ai_notes_router, prefix="/api/v1")

    # 檢查 router 的 routes
    # 找出 /performance 和 /{note_id} 的索引
    routes = app.routes

    performance_idx = None
    note_id_idx = None

    for i, route in enumerate(routes):
        if hasattr(route, "path"):
            # 檢查路徑
            if route.path == "/api/v1/ai-notes/performance":
                performance_idx = i
            elif route.path == "/api/v1/ai-notes/{note_id}":
                note_id_idx = i

    # 驗證：/performance 應該在 /{note_id} 之前
    assert performance_idx is not None, (
        "Route /api/v1/ai-notes/performance not found in app routes. "
        "This indicates the route is missing or has a different path."
    )
    assert note_id_idx is not None, (
        "Route /api/v1/ai-notes/{note_id} not found in app routes. "
        "This indicates the route is missing or has a different path."
    )

    assert performance_idx < note_id_idx, (
        f"Route order is wrong! /performance (index {performance_idx}) should be "
        f"defined before /{{note_id}} (index {note_id_idx}). "
        f"Otherwise /performance will be captured by /{{note_id}} path parameter matching."
    )


