"""
Test Pipeline API — Pipeline REST endpoints 的完整測試

測試端點：
  POST /api/v1/pipeline/run    — 啟動 pipeline
  GET  /api/v1/pipeline/status — 查詢狀態
  GET  /api/v1/pipeline/report — 取得驗證報告
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


class TestPipelineRunEndpoint:
    """POST /api/v1/pipeline/run 端點測試"""

    def test_valid_request(self):
        """測試有效的 pipeline 啟動請求"""
        payload = {
            "symbols": ["2330", "2454"],
            "train_start": "2024-01-01",
            "train_end": "2024-12-31",
            "val_start": "2025-01-01",
            "val_end": "2025-03-31",
            "strategies": ["smc_v2"],
            "timeframe": "1d",
            "max_iterations": 3,
            "convergence_threshold": 0.02,
        }

        with patch("backend.app.routers.pipeline._current_run", None):
            response = client.post("/api/v1/pipeline/run", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "run_id" in data
        assert data["run_id"].startswith("pipeline-")

    def test_invalid_date_format(self):
        """測試無效的日期格式"""
        payload = {
            "symbols": ["2330"],
            "train_start": "2024/01/01",  # 錯誤格式
            "train_end": "2024-12-31",
            "val_start": "2025-01-01",
            "val_end": "2025-03-31",
        }

        response = client.post("/api/v1/pipeline/run", json=payload)
        assert response.status_code == 422  # 驗證錯誤

    def test_invalid_date_range(self):
        """測試無效的日期範圍（train_end <= train_start）"""
        payload = {
            "symbols": ["2330"],
            "train_start": "2024-12-31",
            "train_end": "2024-01-01",  # 結束早於開始
            "val_start": "2025-01-01",
            "val_end": "2025-03-31",
        }

        with patch("backend.app.routers.pipeline._current_run", None):
            response = client.post("/api/v1/pipeline/run", json=payload)

        assert response.status_code == 400
        assert "train_end must be after train_start" in response.json()["detail"]

    def test_pipeline_already_running(self):
        """測試 pipeline 已在運行時的請求

        並發控制：asyncio 單執行緒保證 _current_run 的檢查與設定為原子操作。
        若 _current_run["status"] == "running"，則視為已有 pipeline 運行中，
        返回 409 Conflict。
        """
        payload = {
            "symbols": ["2330"],
            "train_start": "2024-01-01",
            "train_end": "2024-12-31",
            "val_start": "2025-01-01",
            "val_end": "2025-03-31",
        }

        # 模擬已有 pipeline 運行中的狀態
        running_state = {
            "run_id": "pipeline-existing",
            "status": "running",
            "current_iteration": 0,
            "win_rate_history": [],
            "error": None,
        }

        with patch("backend.app.routers.pipeline._current_run", running_state):
            response = client.post("/api/v1/pipeline/run", json=payload)

        assert response.status_code == 409
        assert "already running" in response.json()["detail"]

    def test_empty_symbols_list(self):
        """測試空 symbols list 的驗證"""
        payload = {
            "symbols": [],  # 空列表
            "train_start": "2024-01-01",
            "train_end": "2024-12-31",
            "val_start": "2025-01-01",
            "val_end": "2025-03-31",
        }

        response = client.post("/api/v1/pipeline/run", json=payload)
        assert response.status_code == 422  # 驗證錯誤
        assert "symbols" in response.json()["detail"][0]["loc"]


class TestPipelineStatusEndpoint:
    """GET /api/v1/pipeline/status 端點測試"""

    def test_idle_status(self):
        """測試無運行中 pipeline 時的狀態"""
        with patch("backend.app.routers.pipeline._current_run", None):
            response = client.get("/api/v1/pipeline/status")

        assert response.status_code == 200
        data = response.json()
        assert data["running"] is False
        assert data["current_iteration"] == 0
        assert data["win_rate_history"] == []
        assert data["status"] == "idle"

    def test_running_status(self):
        """測試運行中的 pipeline 狀態"""
        running_state = {
            "run_id": "pipeline-test-123",
            "status": "running",
            "current_iteration": 2,
            "win_rate_history": [0.45, 0.48],
            "error": None,
        }

        with patch("backend.app.routers.pipeline._current_run", running_state):
            response = client.get("/api/v1/pipeline/status")

        assert response.status_code == 200
        data = response.json()
        assert data["running"] is True
        assert data["current_iteration"] == 2
        assert data["win_rate_history"] == [0.45, 0.48]
        assert data["status"] == "running"
        assert data["error"] is None

    def test_completed_status(self):
        """測試已完成的 pipeline 狀態"""
        completed_state = {
            "run_id": "pipeline-test-123",
            "status": "completed",
            "current_iteration": 3,
            "win_rate_history": [0.45, 0.48, 0.50],
            "error": None,
            "validation_report": {
                "symbols": ["2330"],
                "total_trades": 100,
                "avg_win_rate": 0.52,
            },
        }

        with patch("backend.app.routers.pipeline._current_run", completed_state):
            response = client.get("/api/v1/pipeline/status")

        assert response.status_code == 200
        data = response.json()
        assert data["running"] is False
        assert data["status"] == "completed"

    def test_failed_status(self):
        """測試失敗的 pipeline 狀態"""
        failed_state = {
            "run_id": "pipeline-test-123",
            "status": "failed",
            "current_iteration": 1,
            "win_rate_history": [0.45],
            "error": "Memory engine connection failed",
        }

        with patch("backend.app.routers.pipeline._current_run", failed_state):
            response = client.get("/api/v1/pipeline/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Memory engine connection failed"


class TestPipelineReportEndpoint:
    """GET /api/v1/pipeline/report 端點測試"""

    def test_no_report_available(self):
        """測試無報告時的回應"""
        with patch("backend.app.routers.pipeline._current_run", None):
            response = client.get("/api/v1/pipeline/report")

        assert response.status_code == 200
        data = response.json()
        assert data["symbols"] == []
        assert data["total_trades"] == 0
        assert data["avg_win_rate"] == 0

    def test_report_available(self):
        """測試有驗證報告時的回應"""
        report_data = {
            "symbols": ["2330", "2454"],
            "total_trades": 150,
            "total_wins": 90,
            "total_losses": 60,
            "avg_win_rate": 0.60,
            "avg_return": 0.085,
        }

        current_run = {
            "run_id": "pipeline-test-123",
            "status": "completed",
            "validation_report": report_data,
        }

        with patch("backend.app.routers.pipeline._current_run", current_run):
            response = client.get("/api/v1/pipeline/report")

        assert response.status_code == 200
        data = response.json()
        assert data == report_data


class TestPipelineRequestValidation:
    """Pipeline 請求驗證測試"""

    def test_missing_required_fields(self):
        """測試缺少必需欄位"""
        payload = {
            "train_start": "2024-01-01",
            "train_end": "2024-12-31",
            # 缺少 symbols, val_start, val_end
        }

        response = client.post("/api/v1/pipeline/run", json=payload)
        assert response.status_code == 422

    def test_default_values(self):
        """測試預設值"""
        payload = {
            "symbols": ["2330"],
            "train_start": "2024-01-01",
            "train_end": "2024-12-31",
            "val_start": "2025-01-01",
            "val_end": "2025-03-31",
            # 未指定 strategies, timeframe, max_iterations, convergence_threshold
        }

        with patch("backend.app.routers.pipeline._pipeline_lock") as mock_lock:
            mock_lock.acquire_nowait.return_value = True
            response = client.post("/api/v1/pipeline/run", json=payload)

        assert response.status_code == 200
        # 驗證背景任務被添加並使用預設值
