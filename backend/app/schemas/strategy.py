"""
Strategy Profile & Backtest v2 — Request / Response Schemas
"""

from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Default strategy params ──────────────────────────────────────────────────

DEFAULT_PARAMS: dict = {
    # 回測設定
    "backtest_mode": "smc_only",      # smc_only | smc_neutral | smc_full
    "fill_model": "limit",            # limit | conservative | close
    "cost_model": True,

    # 進場規則
    "min_rr": 2.0,
    "min_conditions": 2,
    "entry_tolerance_atr": 0.5,

    # 出場規則
    "stop_mode": "smc_structure",     # smc_structure | fixed_pct | atr_multiple
    "fixed_stop_pct": 0.07,
    "atr_buffer": 0.15,
    "target_mode": "smc_target",
    "exit_on_reversal": "mss_all",    # mss_all | choch_half_mss_all | off
    "breakeven_mode": "structure",    # structure | simple_1r | off

    # 倉位與風控
    "position_mode": "v2_dynamic",
    "fixed_position_pct": 0.10,
    "risk_per_trade": 0.02,
    "max_heat": 0.10,
    "max_positions": 8,
    "us_exposure_limit": 0.70,
    "tw_exposure_limit": 0.50,
    "use_sentiment": False,
    "use_mtf": True,

    # SMC 引擎
    "smc_config": {},
}


# ── Strategy Profile ─────────────────────────────────────────────────────────

class StrategyCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = None
    params: dict = Field(default_factory=lambda: DEFAULT_PARAMS.copy())
    overrides: dict = Field(default_factory=dict)
    stock_settings: dict = Field(default_factory=dict)


class StrategyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    params: dict | None = None
    overrides: dict | None = None
    stock_settings: dict | None = None


class StrategyOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    params: dict
    overrides: dict
    stock_settings: dict
    is_active: bool
    latest_backtest_id: int | None = None
    latest_metrics: dict | None = None    # joined from backtest
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StrategyListItem(BaseModel):
    id: int
    name: str
    description: str | None = None
    is_active: bool
    latest_backtest_id: int | None = None
    latest_metrics: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Backtest v2 ──────────────────────────────────────────────────────────────

class BacktestRunRequest(BaseModel):
    profile_id: int
    start_date: date
    end_date: date
    initial_capital: float = 1_000_000
    market_filter: str = "ALL"         # US | TW | ALL


class BacktestResultOut(BaseModel):
    id: int
    profile_id: int
    name: str | None = None
    start_date: date
    end_date: date
    initial_capital: float
    market_filter: str
    strategy_hash: str
    run_hash: str
    stock_universe: list
    metrics: dict
    diagnosis: dict | None = None
    duration_secs: float | None = None
    stock_count: int | None = None
    trading_days: int | None = None
    status: str
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BacktestTradeOut(BaseModel):
    id: int
    ticker: str
    market: str
    stock_group: str | None = None
    signal_date: date
    fill_date: date
    fill_price: float
    entry_source: str | None = None
    position_tier: str | None = None
    conditions_met: int | None = None
    position_size_pct: float | None = None
    exit_date: date | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    planned_rr: float | None = None
    actual_rr: float | None = None
    pnl_pct: float | None = None
    pnl_amount: float | None = None
    trade_cost: float | None = None
    net_pnl: float | None = None
    holding_days: int | None = None
    mae_pct: float | None = None
    mfe_pct: float | None = None
    smc_trend_at_entry: str | None = None
    smc_trend_at_exit: str | None = None

    model_config = {"from_attributes": True}


class BacktestEquityOut(BaseModel):
    trade_date: date
    equity: float
    drawdown_pct: float | None = None
    cash: float | None = None
    positions_value: float | None = None
    open_positions: int | None = None

    model_config = {"from_attributes": True}


class BacktestCompareOut(BaseModel):
    profile_a: dict
    profile_b: dict
    params_diff: list[dict]
    metrics_comparison: dict
    equity_a: list[dict]
    equity_b: list[dict]


# ── Strategy Signals ─────────────────────────────────────────────────────────

class SignalOut(BaseModel):
    id: int
    ticker: str | None = None        # joined from stock
    signal_date: date
    signal_action: str
    signal_entry: float | None = None
    signal_stop: float | None = None
    signal_target: float | None = None
    signal_rr: float | None = None
    signal_tier: str | None = None
    signal_conditions: int | None = None
    followed: bool | None = None
    actual_entry: float | None = None
    actual_exit: float | None = None
    actual_pnl_pct: float | None = None
    outcome_if_followed: float | None = None
    skip_reason: str | None = None
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SignalFollowRequest(BaseModel):
    actual_entry: float | None = None
    notes: str | None = None


class SignalSkipRequest(BaseModel):
    skip_reason: str | None = None
    notes: str | None = None
