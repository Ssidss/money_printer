"""
Live Signal API — Phase B

用 V3 策略邏輯對最新市場數據即時計算信號。
跟回測的差別：回測跑 2 年歷史，這裡跑「今天」。

Endpoints:
  GET /signals/{ticker}   — 單支股票即時信號
  GET /signals/batch      — 全部追蹤股票的信號（for Dashboard）
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ..database import AsyncSessionLocal
from ..models.stock import Stock, PriceHistory
from ..services.backtest_v3.live_provider import LiveProvider
from ..services.backtest_v3 import (
    SMCStrategy, MomentumBreakoutStrategy, ExplosionScannerStrategy,
)

import pandas as pd

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])

# ── Strategy builders ────────────────────────────────────
STRATEGY_BUILDERS = {
    "explosion_scanner": lambda: ExplosionScannerStrategy(score_threshold=50),
    "momentum_breakout": lambda: MomentumBreakoutStrategy(min_rr=1.5),
    "smc_v2": lambda: SMCStrategy(min_conditions=3, min_rr=2.0, market="US"),
}

VALID_STRATEGIES = list(STRATEGY_BUILDERS.keys())


# ── Data loading helpers ─────────────────────────────────

async def _load_ticker_prices(ticker: str) -> Optional[pd.DataFrame]:
    """載入單支股票的 price_history，回傳 OHLCV DataFrame"""
    async with AsyncSessionLocal() as db:
        stock = (await db.execute(
            select(Stock).where(Stock.ticker == ticker)
        )).scalar_one_or_none()
        if not stock:
            return None

        rows = (await db.execute(
            select(PriceHistory)
            .where(PriceHistory.stock_id == stock.id)
            .order_by(PriceHistory.date)
        )).scalars().all()

        if len(rows) < 22:
            return None

        data = [{
            "date": r.date,
            "Open": float(r.open or 0),
            "High": float(r.high or 0),
            "Low": float(r.low or 0),
            "Close": float(r.close or 0),
            "Volume": int(r.volume or 0),
        } for r in rows]

        return pd.DataFrame(data).set_index("date").sort_index()


async def _load_all_prices(market: str = "US") -> dict[str, pd.DataFrame]:
    """載入全部追蹤股票的 price_history"""
    async with AsyncSessionLocal() as db:
        q = select(Stock)
        if market != "ALL":
            q = q.where(Stock.market == market)
        stocks = (await db.execute(q)).scalars().all()
        stock_ids = {s.id: s.ticker for s in stocks}

        rows = (await db.execute(
            select(PriceHistory)
            .where(PriceHistory.stock_id.in_(stock_ids.keys()))
            .order_by(PriceHistory.stock_id, PriceHistory.date)
        )).scalars().all()

        ticker_rows: dict[str, list] = {}
        for r in rows:
            t = stock_ids.get(r.stock_id)
            if t:
                ticker_rows.setdefault(t, []).append({
                    "date": r.date,
                    "Open": float(r.open or 0),
                    "High": float(r.high or 0),
                    "Low": float(r.low or 0),
                    "Close": float(r.close or 0),
                    "Volume": int(r.volume or 0),
                })

        return {
            ticker: pd.DataFrame(data).set_index("date").sort_index()
            for ticker, data in ticker_rows.items()
            if len(data) >= 22
        }


# ── Signal serialization ─────────────────────────────────

def _signal_to_dict(signal) -> dict:
    """把 Signal dataclass 轉成 JSON-safe dict"""
    ph = signal.price_hint or {}
    return {
        "signal_id": signal.signal_id,
        "strategy_name": signal.strategy_name,
        "strategy_type": signal.strategy_type,
        "action": signal.action,
        "confidence": signal.confidence,
        "position_tier": signal.position_tier,
        "entry": ph.get("entry"),
        "stop": ph.get("stop"),
        "target": ph.get("target"),
        "rr_ratio": ph.get("rr_ratio"),
        "expiry": str(signal.expiry),
        "meta": signal.meta,
    }


# ── Endpoints ────────────────────────────────────────────

@router.get("/{ticker}")
async def get_signals(
    ticker: str,
    strategies: str = Query("explosion_scanner,momentum_breakout", description="逗號分隔策略名"),
):
    """
    對單支股票跑即時信號。

    - Explosion + Momentum: < 0.1s
    - SMC: ~2-3s（較慢）
    """
    ticker = ticker.upper()
    strategy_names = [s.strip() for s in strategies.split(",") if s.strip()]

    # Validate strategy names
    invalid = [s for s in strategy_names if s not in STRATEGY_BUILDERS]
    if invalid:
        raise HTTPException(400, f"Unknown strategies: {invalid}. Valid: {VALID_STRATEGIES}")

    # Load price data
    t0 = time.time()
    df = await _load_ticker_prices(ticker)
    if df is None:
        raise HTTPException(404, f"Stock {ticker} not found or insufficient data")
    load_time = time.time() - t0

    # Build provider
    provider = LiveProvider(price_data={ticker: df})
    data_date = provider.current_date()
    current_price = provider.get_latest_price(ticker)

    # Run strategies
    t0 = time.time()
    all_signals = []
    strategy_status = {}

    for name in strategy_names:
        try:
            strategy = STRATEGY_BUILDERS[name]()
            signals = strategy.generate_signals(ticker, provider)
            all_signals.extend(signals)
            strategy_status[name] = {
                "status": "ok",
                "signal_count": len(signals),
            }
        except Exception as e:
            logger.warning(f"Strategy {name} failed for {ticker}: {e}")
            strategy_status[name] = {
                "status": "error",
                "message": str(e),
                "signal_count": 0,
            }

    compute_time = time.time() - t0

    return {
        "ticker": ticker,
        "data_date": str(data_date),
        "current_price": current_price,
        "signal_count": len(all_signals),
        "signals": [_signal_to_dict(s) for s in all_signals],
        "strategy_status": strategy_status,
        "timing": {
            "data_load_ms": round(load_time * 1000, 1),
            "compute_ms": round(compute_time * 1000, 1),
        },
    }


@router.get("/batch/all")
async def get_batch_signals(
    strategy: str = Query("explosion_scanner", description="策略名稱（單一）"),
    market: str = Query("US", description="市場 US/TW/ALL"),
):
    """
    對全部追蹤股票跑即時信號（單一策略）。

    - Explosion/Momentum: ~2-4s for 34 stocks
    - SMC: ~60-100s（不建議 batch）
    """
    if strategy not in STRATEGY_BUILDERS:
        raise HTTPException(400, f"Unknown strategy: {strategy}. Valid: {VALID_STRATEGIES}")

    # Load all prices
    t0 = time.time()
    price_data = await _load_all_prices(market)
    load_time = time.time() - t0

    if not price_data:
        return {"strategy": strategy, "signal_count": 0, "results": [], "timing": {}}

    # Build provider with all stocks
    provider = LiveProvider(price_data=price_data)
    data_date = provider.current_date()

    # Run strategy on each stock
    t0 = time.time()
    strat = STRATEGY_BUILDERS[strategy]()
    results = []

    for ticker in sorted(price_data.keys()):
        if not provider.is_tradable(ticker):
            continue
        try:
            signals = strat.generate_signals(ticker, provider)
            if signals:
                price = provider.get_latest_price(ticker)
                for s in signals:
                    results.append({
                        "ticker": ticker,
                        "current_price": price,
                        **_signal_to_dict(s),
                    })
        except Exception as e:
            logger.warning(f"Strategy {strategy} failed for {ticker}: {e}")

    compute_time = time.time() - t0

    # Sort by confidence descending
    results.sort(key=lambda r: r.get("confidence", 0), reverse=True)

    return {
        "strategy": strategy,
        "data_date": str(data_date),
        "stock_count": len(price_data),
        "signal_count": len(results),
        "results": results,
        "timing": {
            "data_load_ms": round(load_time * 1000, 1),
            "compute_ms": round(compute_time * 1000, 1),
        },
    }
