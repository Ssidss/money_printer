"""
Memory Pipeline — 回測迭代管道

三個 Phase：
  1. 冷啟動 — 用現有策略跑回測，累積初始記憶
  2. 迭代 — 反思 → 生成決策表 → 回測 → 收斂檢查
  3. 驗證 — 獨立驗證集，不寫記憶
"""

import asyncio
import logging
import uuid
from datetime import date
from typing import Optional, Callable, Any

from .backtest_vbt import run_vbt_backtest
from .memory_client import MemoryEngineClient
from ..sse.manager import sse_manager

logger = logging.getLogger(__name__)


class PipelineRunInfo:
    """運行中 Pipeline 的狀態追蹤"""
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.status = "running"  # running | completed | failed
        self.current_iteration = 0
        self.win_rate_history: list[float] = []
        self.error_message: Optional[str] = None
        self.validation_report: Optional[dict] = None


async def run_pipeline(
    symbols: list[str],
    train_start: date,
    train_end: date,
    val_start: date,
    val_end: date,
    strategies: list[str],
    timeframe: str,
    max_iterations: int = 5,
    convergence_threshold: float = 0.02,
    cancel_event: asyncio.Event = None,
) -> dict:
    """
    執行完整的回測迭代 Pipeline。

    三 Phase 流程：
      1. 冷啟動：用 strategies 跑回測，save_to_memory=True，累積初始記憶
      2. 迭代：反思 → 生成決策表 → 用決策表跑回測 → 檢查勝率收斂
      3. 驗證：用獨立驗證集跑決策表（不寫記憶），產生最終報告

    Args:
        symbols: 股票代碼清單
        train_start: 訓練開始日期
        train_end: 訓練結束日期
        val_start: 驗證開始日期
        val_end: 驗證結束日期
        strategies: 初始策略清單（用於 Phase 1）
        timeframe: 時間框架（如 "1d", "4h"）
        max_iterations: 最大迭代次數
        convergence_threshold: 勝率變動閾值（如 0.02 = 2%）
        cancel_event: 取消信號（若被 set，pipeline 停止）

    Returns:
        {
            'status': 'completed' | 'failed' | 'cancelled',
            'iterations': int,
            'win_rate_history': list,
            'converged': bool,
            'validation_report': dict,
            'error': str (if failed)
        }
    """
    run_id = f"pipeline-{uuid.uuid4().hex[:8]}"
    info = PipelineRunInfo(run_id)

    try:
        # ── Phase 1: 冷啟動 ────────────────────────────────────────────────
        await _emit(f"[Phase 1] 冷啟動：用現有策略累積初始記憶", phase="phase1")

        total_phase1_tasks = len(strategies) * len(symbols)
        phase1_completed = 0

        for strategy in strategies:
            for symbol in symbols:
                # 檢查取消信號
                if cancel_event and cancel_event.is_set():
                    await _emit("[Phase 1] Pipeline 已被停止", phase="phase1_stopped")
                    info.status = "stopped"
                    await sse_manager.broadcast("pipeline_stopped", {
                        "status": "stopped",
                        "iterations": info.current_iteration,
                    })
                    return {
                        "status": "stopped",
                        "iterations": info.current_iteration,
                        "win_rate_history": info.win_rate_history,
                        "converged": False,
                        "validation_report": None,
                    }

                try:
                    result = await run_vbt_backtest(
                        ticker=symbol,
                        start_date=train_start,
                        end_date=train_end,
                        strategy_name=strategy,
                        save_to_memory=True,
                        timeframe=timeframe,
                    )
                    if "error" not in result:
                        phase1_completed += 1
                        await _emit(
                            f"[Phase 1] {symbol} × {strategy} 完成",
                            ticker=symbol,
                            current=phase1_completed,
                            total=total_phase1_tasks
                        )
                except Exception as e:
                    logger.warning(f"Phase 1 backtest failed: {symbol} × {strategy}: {e}")

        await _emit("[Phase 1] 完成", phase="phase1_done")

        # ── Phase 2: 迭代迴圈 ────────────────────────────────────────────────
        await _emit("[Phase 2] 開始迭代", phase="phase2")

        client = MemoryEngineClient()
        prev_win_rate = 0
        try:
            for iteration in range(max_iterations):
                # 檢查取消信號
                if cancel_event and cancel_event.is_set():
                    await _emit("[Phase 2] Pipeline 已被停止", phase="phase2_stopped")
                    info.status = "stopped"
                    converged = False
                    await sse_manager.broadcast("pipeline_stopped", {
                        "status": "stopped",
                        "iterations": info.current_iteration,
                    })
                    return {
                        "status": "stopped",
                        "iterations": info.current_iteration,
                        "win_rate_history": info.win_rate_history,
                        "converged": False,
                        "validation_report": None,
                    }

                info.current_iteration = iteration + 1

                # 反思
                await _emit(f"迭代 {iteration + 1}: 觸發反思...", iteration=iteration + 1)
                try:
                    reflect_result = await client.trigger_reflect()
                    logger.info(f"Reflect result: {reflect_result}")
                except Exception as e:
                    logger.warning(f"Reflect failed: {e}")
                    # 繼續，不中斷迭代

                # 生成決策表
                await _emit(f"迭代 {iteration + 1}: 生成決策表...", iteration=iteration + 1)
                try:
                    gen_result = await client.trigger_generate_table(timeframes=[timeframe])
                    logger.info(f"Generate table result: {gen_result}")
                except Exception as e:
                    logger.warning(f"Generate table failed: {e}")
                    # 繼續，不中斷迭代

                # 用決策表跑回測
                await _emit(f"迭代 {iteration + 1}: 用決策表回測...", iteration=iteration + 1)
                iteration_results = []

                for symbol in symbols:
                    try:
                        result = await run_vbt_backtest(
                            ticker=symbol,
                            start_date=train_start,
                            end_date=train_end,
                            strategy_name="decision_table",
                            save_to_memory=True,
                            timeframe=timeframe,
                        )
                        if "error" not in result:
                            iteration_results.append(result)
                            await _emit(
                                f"迭代 {iteration + 1}: {symbol} 完成",
                                ticker=symbol,
                                iteration=iteration + 1
                            )
                    except Exception as e:
                        logger.warning(f"Iteration {iteration + 1} backtest failed: {symbol}: {e}")

                # 獲取統計資訊（勝率）
                try:
                    stats = await client.get_stats(group_by="overall")
                    current_win_rate = stats.get("win_rate", 0)
                    info.win_rate_history.append(current_win_rate)

                    await _emit(
                        f"迭代 {iteration + 1} 完成：勝率 {current_win_rate:.2%}",
                        iteration=iteration + 1,
                        win_rate=current_win_rate
                    )

                    # 檢查收斂
                    if iteration > 0 and abs(current_win_rate - prev_win_rate) < convergence_threshold:
                        await _emit(
                            f"迭代 {iteration + 1}: 已收斂（勝率變動 {abs(current_win_rate - prev_win_rate):.2%} < {convergence_threshold:.2%}）",
                            converged=True
                        )
                        break

                    prev_win_rate = current_win_rate
                except Exception as e:
                    logger.warning(f"Failed to get stats in iteration {iteration + 1}: {e}")
                    # 跳過本次迭代的收斂檢查，避免誤判

            await _emit("[Phase 2] 迭代完成", phase="phase2_done")
        finally:
            await client.close()

        # ── Phase 3: 驗證 ──────────────────────────────────────────────────
        await _emit("[Phase 3] 驗證：用獨立驗證集測試（不寫記憶）", phase="phase3")

        # 檢查取消信號
        if cancel_event and cancel_event.is_set():
            await _emit("[Phase 3] Pipeline 已被停止", phase="phase3_stopped")
            info.status = "stopped"
            await sse_manager.broadcast("pipeline_stopped", {
                "status": "stopped",
                "iterations": info.current_iteration,
            })
            return {
                "status": "stopped",
                "iterations": info.current_iteration,
                "win_rate_history": info.win_rate_history,
                "converged": False,
                "validation_report": None,
            }

        validation_results = []
        for symbol in symbols:
            try:
                result = await run_vbt_backtest(
                    ticker=symbol,
                    start_date=val_start,
                    end_date=val_end,
                    strategy_name="decision_table",
                    save_to_memory=False,  # 重要：驗證段不寫記憶
                    timeframe=timeframe,
                )
                if "error" not in result:
                    validation_results.append(result)
                    await _emit(f"[Phase 3] {symbol} 驗證完成", ticker=symbol)
            except Exception as e:
                logger.warning(f"Validation failed: {symbol}: {e}")

        # 產生驗證報告
        validation_report = _generate_validation_report(validation_results)
        info.validation_report = validation_report

        await _emit("[Phase 3] 驗證完成", phase="phase3_done")

        # ── 完成 ────────────────────────────────────────────────────────────
        info.status = "completed"
        # converged = True 當迭代次數 < max_iterations（即提前停止了）
        converged = info.current_iteration < max_iterations

        await sse_manager.broadcast("pipeline_complete", {
            "status": "completed",
            "iterations": info.current_iteration,
            "win_rate_history": info.win_rate_history,
            "converged": converged,
            "validation_report": validation_report,
        })

        return {
            "status": "completed",
            "iterations": info.current_iteration,
            "win_rate_history": info.win_rate_history,
            "converged": converged,
            "validation_report": validation_report,
        }

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        info.status = "failed"
        info.error_message = str(e)

        await sse_manager.broadcast("pipeline_error", {
            "error": str(e),
            "iterations": info.current_iteration,
        })

        return {
            "status": "failed",
            "error": str(e),
            "iterations": info.current_iteration,
        }


def _generate_validation_report(results: list[dict]) -> dict:
    """從驗證結果生成報告"""
    if not results:
        return {"symbols": [], "total_trades": 0, "avg_win_rate": 0}

    report = {
        "symbols": [],
        "total_trades": 0,
        "total_wins": 0,
        "total_losses": 0,
        "avg_win_rate": 0,
        "avg_return": 0,
    }

    for result in results:
        if "error" in result:
            continue

        symbol = result.get("ticker", "?")
        stats = result.get("stats", {})

        report["symbols"].append(symbol)
        report["total_trades"] += stats.get("trades", 0)
        report["total_wins"] += stats.get("wins", 0)
        report["total_losses"] += stats.get("losses", 0)
        report["avg_return"] += stats.get("return_pct", 0)

    if report["total_trades"] > 0:
        report["avg_win_rate"] = report["total_wins"] / report["total_trades"]

    if report["symbols"]:
        report["avg_return"] /= len(report["symbols"])

    return report


async def _emit(message: str, **kwargs):
    """發送進度事件"""
    data = {"message": message, **kwargs}
    await sse_manager.broadcast("pipeline_progress", data)
    logger.info(f"[pipeline] {message}")
