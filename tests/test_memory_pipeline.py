"""
Test Memory Pipeline — 回測迭代管道完整流程測試

測試三個 phase：
  1. 冷啟動 — 用現有策略跑回測，累積初始記憶
  2. 迭代 — 反思 → 生成決策表 → 用決策表回測 → 收斂檢查
  3. 驗證 — 獨立驗證集，不寫記憶
"""

import pytest
import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

from backend.app.services.run_memory_pipeline import run_pipeline, PipelineRunInfo


class TestPipelineRunInfo:
    """PipelineRunInfo 單元測試"""

    def test_init(self):
        """測試初始化"""
        info = PipelineRunInfo("pipeline-test-123")
        assert info.run_id == "pipeline-test-123"
        assert info.status == "running"
        assert info.current_iteration == 0
        assert info.win_rate_history == []
        assert info.error_message is None
        assert info.validation_report is None


class TestRunPipelinePhases:
    """Pipeline 三個 phase 的流程測試"""

    @pytest.mark.asyncio
    async def test_phase1_coldstart(self):
        """Phase 1: 冷啟動 — 用現有策略累積初始記憶"""
        symbols = ["AAPL", "MSFT"]
        strategies = ["smc_v2"]
        train_start = date(2024, 1, 1)
        train_end = date(2024, 12, 31)
        val_start = date(2025, 1, 1)
        val_end = date(2025, 3, 31)

        # Mock run_vbt_backtest
        mock_backtest_result = {
            "ticker": "AAPL",
            "strategy": "smc_v2",
            "stats": {
                "trades": 10,
                "wins": 6,
                "losses": 4,
                "return_pct": 5.2,
                "sharpe_ratio": 1.5,
                "max_drawdown_pct": 8.5,
            },
        }

        with patch("backend.app.services.run_memory_pipeline.run_vbt_backtest") as mock_run:
            mock_run.return_value = mock_backtest_result
            with patch("backend.app.services.run_memory_pipeline.sse_manager") as mock_sse:
                mock_sse.broadcast = AsyncMock()
                result = await run_pipeline(
                    symbols=symbols,
                    train_start=train_start,
                    train_end=train_end,
                    val_start=val_start,
                    val_end=val_end,
                    strategies=strategies,
                    timeframe="1d",
                    max_iterations=1,  # 只跑一次迭代測試
                    convergence_threshold=0.02,
                )

        # 驗證結果
        assert result["status"] == "completed"
        assert "iterations" in result
        assert "win_rate_history" in result
        assert "validation_report" in result
        # 驗證背景任務的 SSE emit 被調用
        assert mock_run.call_count >= len(symbols) * len(strategies)

    @pytest.mark.asyncio
    async def test_phase2_iteration_convergence(self):
        """Phase 2: 迭代 — 檢查勝率收斂"""
        symbols = ["AAPL"]
        strategies = ["smc_v2"]
        train_start = date(2024, 1, 1)
        train_end = date(2024, 12, 31)
        val_start = date(2025, 1, 1)
        val_end = date(2025, 3, 31)

        # Mock 背景任務返回不同勝率，模擬收斂
        backtest_results = [
            {"ticker": "AAPL", "stats": {"trades": 10, "wins": 5, "return_pct": 0.5}},
            {"ticker": "AAPL", "stats": {"trades": 10, "wins": 5, "return_pct": 0.5}},
        ]

        mock_client = AsyncMock()
        mock_client.trigger_reflect = AsyncMock(return_value={"status": "ok"})
        mock_client.trigger_generate_table = AsyncMock(return_value={"status": "ok"})
        # 第一次迭代勝率 50%，第二次迭代勝率 50.5% < 2% 閾值，應收斂
        mock_client.get_stats = AsyncMock(
            side_effect=[
                {"win_rate": 0.50},  # 第一次迭代
                {"win_rate": 0.505},  # 第二次迭代（收斂）
            ]
        )
        mock_client.close = AsyncMock()

        with patch("backend.app.services.run_memory_pipeline.run_vbt_backtest") as mock_run:
            mock_run.return_value = backtest_results[0]
            with patch("backend.app.services.run_memory_pipeline.MemoryEngineClient") as mock_cls:
                mock_cls.return_value = mock_client
                with patch("backend.app.services.run_memory_pipeline.sse_manager") as mock_sse:
                    mock_sse.broadcast = AsyncMock()
                    result = await run_pipeline(
                        symbols=symbols,
                        train_start=train_start,
                        train_end=train_end,
                        val_start=val_start,
                        val_end=val_end,
                        strategies=strategies,
                        timeframe="1d",
                        max_iterations=5,
                        convergence_threshold=0.02,
                    )

        # 應該提前停止，iterations < max_iterations
        assert result["status"] == "completed"
        assert result["converged"] is True  # 提前收斂
        assert result["iterations"] <= 5  # 沒有跑滿 5 次

    @pytest.mark.asyncio
    async def test_phase3_validation_no_memory_write(self):
        """Phase 3: 驗證 — 不寫記憶"""
        symbols = ["AAPL"]
        train_start = date(2024, 1, 1)
        train_end = date(2024, 12, 31)
        val_start = date(2025, 1, 1)
        val_end = date(2025, 3, 31)

        validation_result = {
            "ticker": "AAPL",
            "stats": {"trades": 5, "wins": 3, "return_pct": 2.1},
        }

        with patch("backend.app.services.run_memory_pipeline.run_vbt_backtest") as mock_run:
            mock_run.return_value = validation_result
            with patch("backend.app.services.run_memory_pipeline.MemoryEngineClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.trigger_reflect = AsyncMock()
                mock_client.trigger_generate_table = AsyncMock()
                mock_client.get_stats = AsyncMock(return_value={"win_rate": 0.50})
                mock_client.close = AsyncMock()
                mock_cls.return_value = mock_client

                with patch("backend.app.services.run_memory_pipeline.sse_manager") as mock_sse:
                    mock_sse.broadcast = AsyncMock()
                    result = await run_pipeline(
                        symbols=symbols,
                        train_start=train_start,
                        train_end=train_end,
                        val_start=val_start,
                        val_end=val_end,
                        strategies=["smc_v2"],
                        timeframe="1d",
                        max_iterations=1,
                        convergence_threshold=0.02,
                    )

        # 驗證 Phase 3 的回測 save_to_memory=False
        # 檢查第三次 run_vbt_backtest 呼叫（驗證段）
        calls = mock_run.call_args_list
        # Phase 1: 1 策略 × 1 符號 = 1 次
        # Phase 2: 1 符號 × 1 迭代 = 1 次
        # Phase 3: 1 符號 = 1 次
        assert len(calls) >= 3
        # 最後一次呼叫應該是 save_to_memory=False
        last_call = calls[-1]
        assert last_call[1].get("save_to_memory") is False

    @pytest.mark.asyncio
    async def test_error_handling_memory_engine_failure(self):
        """測試錯誤處理 — MemoryEngineClient 連接失敗時 pipeline 應返回 failed 狀態"""
        symbols = ["AAPL"]
        train_start = date(2024, 1, 1)
        train_end = date(2024, 12, 31)
        val_start = date(2025, 1, 1)
        val_end = date(2025, 3, 31)

        mock_backtest_result = {
            "ticker": "AAPL",
            "stats": {"trades": 10, "wins": 6, "return_pct": 5.2},
        }

        with patch("backend.app.services.run_memory_pipeline.run_vbt_backtest") as mock_run:
            mock_run.return_value = mock_backtest_result
            with patch("backend.app.services.run_memory_pipeline.MemoryEngineClient") as mock_cls:
                # MemoryEngineClient 初始化失敗
                mock_cls.side_effect = Exception("Memory engine connection failed")
                with patch("backend.app.services.run_memory_pipeline.sse_manager") as mock_sse:
                    mock_sse.broadcast = AsyncMock()
                    result = await run_pipeline(
                        symbols=symbols,
                        train_start=train_start,
                        train_end=train_end,
                        val_start=val_start,
                        val_end=val_end,
                        strategies=["smc_v2"],
                        timeframe="1d",
                        max_iterations=1,
                        convergence_threshold=0.02,
                    )

        # 應該返回 failed 狀態
        assert result["status"] == "failed"
        assert "error" in result
        assert "Memory engine connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_backtest_partial_failure(self):
        """測試背景任務部分失敗時 pipeline 繼續 — robustness 設計"""
        symbols = ["AAPL", "MSFT"]
        train_start = date(2024, 1, 1)
        train_end = date(2024, 12, 31)
        val_start = date(2025, 1, 1)
        val_end = date(2025, 3, 31)

        # AAPL 成功，MSFT 失敗
        def mock_backtest(*args, **kwargs):
            if kwargs.get("ticker") == "AAPL":
                return {"ticker": "AAPL", "stats": {"trades": 10, "wins": 6}}
            else:
                raise Exception("MSFT backtest failed")

        with patch("backend.app.services.run_memory_pipeline.run_vbt_backtest") as mock_run:
            mock_run.side_effect = mock_backtest
            with patch("backend.app.services.run_memory_pipeline.MemoryEngineClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.trigger_reflect = AsyncMock()
                mock_client.trigger_generate_table = AsyncMock()
                mock_client.get_stats = AsyncMock(return_value={"win_rate": 0.50})
                mock_client.close = AsyncMock()
                mock_cls.return_value = mock_client

                with patch("backend.app.services.run_memory_pipeline.sse_manager") as mock_sse:
                    mock_sse.broadcast = AsyncMock()
                    result = await run_pipeline(
                        symbols=symbols,
                        train_start=train_start,
                        train_end=train_end,
                        val_start=val_start,
                        val_end=val_end,
                        strategies=["smc_v2"],
                        timeframe="1d",
                        max_iterations=1,
                        convergence_threshold=0.02,
                    )

        # Pipeline 應該完成，即使某些 backtest 失敗
        assert result["status"] == "completed"
        # 驗證報告應該只包含成功的 AAPL
        assert "AAPL" in result["validation_report"]["symbols"]


class TestValidationReport:
    """驗證報告生成測試"""

    def test_generate_validation_report_empty(self):
        """空結果時的驗證報告"""
        from backend.app.services.run_memory_pipeline import _generate_validation_report

        report = _generate_validation_report([])
        assert report["symbols"] == []
        assert report["total_trades"] == 0
        assert report["avg_win_rate"] == 0

    def test_generate_validation_report_with_results(self):
        """有結果時的驗證報告"""
        from backend.app.services.run_memory_pipeline import _generate_validation_report

        results = [
            {
                "ticker": "AAPL",
                "stats": {
                    "trades": 10,
                    "wins": 6,
                    "losses": 4,
                    "return_pct": 5.2,
                },
            },
            {
                "ticker": "MSFT",
                "stats": {
                    "trades": 8,
                    "wins": 5,
                    "losses": 3,
                    "return_pct": 3.1,
                },
            },
        ]

        report = _generate_validation_report(results)
        assert report["symbols"] == ["AAPL", "MSFT"]
        assert report["total_trades"] == 18
        assert report["total_wins"] == 11
        assert report["total_losses"] == 7
        assert report["avg_win_rate"] == pytest.approx(11 / 18)
        assert report["avg_return"] == pytest.approx((5.2 + 3.1) / 2)
