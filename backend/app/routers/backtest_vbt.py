"""
VectorBT 回測 API — SMC 策略向量化回測

Endpoints:
  POST /backtest/vbt/run   — 執行 VectorBT SMC 回測（同步，< 10 秒）
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest/vbt", tags=["backtest_vbt"])


# ── Request / Response schemas ────────────────────────────────────────────────

class VbtRunRequest(BaseModel):
    ticker: str
    start: str                          # YYYY-MM-DD
    end: str                            # YYYY-MM-DD
    market: str = "US"                  # "US" | "TW"
    initial_capital: float = 100_000
    min_conditions: int = 2             # SMC 最少滿足條件數
    min_rr: float = 1.5                 # 最低風報比

    @field_validator("market")
    @classmethod
    def validate_market(cls, v: str) -> str:
        if v not in ("US", "TW"):
            raise ValueError("market must be 'US' or 'TW'")
        return v

    @field_validator("start", "end")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError(f"Invalid date format: '{v}', expected YYYY-MM-DD")
        return v


@router.post("/run")
async def run_vbt_backtest(req: VbtRunRequest):
    """
    執行 VectorBT SMC 回測。

    - 使用現有 SMCStrategy（無前視偏誤，T+1 執行）
    - VectorBT 向量化計算績效指標和 equity curve
    - Response time 目標：< 10 秒（單支股票 1 年）

    Request body:
    ```json
    {"ticker": "2330", "start": "2024-01-01", "end": "2024-12-31", "market": "TW"}
    ```
    """
    from ..services.backtest_vbt import run_smc_backtest

    start_dt = date.fromisoformat(req.start)
    end_dt = date.fromisoformat(req.end)

    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="end must be after start")

    if (end_dt - start_dt).days > 365 * 5:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 5 years")

    logger.info(
        f"[backtest_vbt] request: ticker={req.ticker} "
        f"{req.start}~{req.end} market={req.market} "
        f"capital={req.initial_capital}"
    )

    result = await run_smc_backtest(
        ticker=req.ticker,
        start_date=start_dt,
        end_date=end_dt,
        market=req.market,
        initial_capital=req.initial_capital,
        min_conditions=req.min_conditions,
        min_rr=req.min_rr,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result
