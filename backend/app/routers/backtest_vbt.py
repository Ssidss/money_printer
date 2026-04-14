"""
VectorBT 回測 API

Endpoints:
  GET  /backtest/vbt/strategies  — 列出所有可用策略（動態從 STRATEGY_REGISTRY）
  POST /backtest/vbt/run         — 執行 VectorBT 回測（通用，指定 strategy）
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
    start: str                              # YYYY-MM-DD
    end: str                                # YYYY-MM-DD
    market: str = "US"                      # "US" | "TW"
    initial_capital: float = 100_000
    strategy: str = "smc_v2"               # 策略名稱（查 STRATEGY_REGISTRY）
    strategy_params: dict = {}             # 可選覆蓋策略預設參數

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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/strategies")
def get_strategies():
    """
    列出所有可用策略（動態從 STRATEGY_REGISTRY）。

    Response:
    ```json
    [
      {
        "name": "smc_v2",
        "label": "SMC v2（智慧資金結構）",
        "description": "...",
        "default_params": {"min_conditions": 2, "min_rr": 1.5, ...}
      },
      ...
    ]
    ```
    """
    from ..services.backtest_vbt import list_strategies
    return list_strategies()


@router.post("/run")
async def run_vbt_backtest_endpoint(req: VbtRunRequest):
    """
    執行 VectorBT 回測。

    - 策略由 `strategy` 欄位指定，必須在 STRATEGY_REGISTRY 中
    - `strategy_params` 可覆蓋策略預設參數
    - 使用現有策略（無前視偏誤，T+1 執行）
    - VectorBT 向量化計算績效指標和 equity curve

    Request body:
    ```json
    {
      "ticker": "2330",
      "start": "2024-01-01",
      "end": "2024-12-31",
      "market": "TW",
      "strategy": "smc_v2",
      "strategy_params": {"min_conditions": 3, "min_rr": 2.0}
    }
    ```
    """
    from ..services.backtest_vbt import run_vbt_backtest

    start_dt = date.fromisoformat(req.start)
    end_dt = date.fromisoformat(req.end)

    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="end must be after start")

    if (end_dt - start_dt).days > 365 * 5:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 5 years")

    logger.info(
        f"[backtest_vbt] request: ticker={req.ticker} "
        f"{req.start}~{req.end} market={req.market} "
        f"strategy={req.strategy} capital={req.initial_capital}"
    )

    result = await run_vbt_backtest(
        ticker=req.ticker,
        start_date=start_dt,
        end_date=end_dt,
        market=req.market,
        initial_capital=req.initial_capital,
        strategy_name=req.strategy,
        strategy_params=req.strategy_params,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result
