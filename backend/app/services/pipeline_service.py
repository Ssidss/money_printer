"""
Pipeline Service — 處理 pipeline 狀態的持久化

提供方法來：
  - 建立新的 pipeline run 記錄
  - 更新 pipeline run 狀態
  - 查詢 pipeline run 記錄
"""

from datetime import date, datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal
from ..models import PipelineRun


class PipelineService:
    """Pipeline 狀態管理服務"""

    @staticmethod
    async def create_pipeline_run(
        run_id: str,
        symbols: list[str],
        train_start: date,
        train_end: date,
        val_start: date,
        val_end: date,
        status: str = "running",
        strategies: list[str] = None,
        timeframe: str = "1d",
        max_iterations: int = 5,
        convergence_threshold: float = 0.02,
    ) -> PipelineRun:
        """建立新的 pipeline run 記錄"""
        if strategies is None:
            strategies = ["smc_v2"]

        async with AsyncSessionLocal() as session:
            run = PipelineRun(
                run_id=run_id,
                status=status,
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
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run

    @staticmethod
    async def update_pipeline_run(
        run_id: str,
        **updates
    ) -> Optional[PipelineRun]:
        """更新 pipeline run 記錄"""
        async with AsyncSessionLocal() as session:
            stmt = select(PipelineRun).where(PipelineRun.run_id == run_id)
            result = await session.execute(stmt)
            run = result.scalars().first()

            if not run:
                return None

            # 更新指定的欄位
            for key, value in updates.items():
                if hasattr(run, key):
                    setattr(run, key, value)

            # 更新 updated_at
            run.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(run)
            return run

    @staticmethod
    async def get_pipeline_run(run_id: str) -> Optional[PipelineRun]:
        """查詢 pipeline run 記錄"""
        async with AsyncSessionLocal() as session:
            stmt = select(PipelineRun).where(PipelineRun.run_id == run_id)
            result = await session.execute(stmt)
            return result.scalars().first()

    @staticmethod
    async def get_latest_pipeline_run() -> Optional[PipelineRun]:
        """查詢最新的 pipeline run 記錄"""
        async with AsyncSessionLocal() as session:
            stmt = select(PipelineRun).order_by(PipelineRun.created_at.desc()).limit(1)
            result = await session.execute(stmt)
            return result.scalars().first()

    @staticmethod
    async def mark_as_cancelled(run_id: str) -> Optional[PipelineRun]:
        """標記 pipeline 為 cancelled"""
        return await PipelineService.update_pipeline_run(
            run_id,
            status="cancelled"
        )
