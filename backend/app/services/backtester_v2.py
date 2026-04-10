"""
回測引擎 v2 — SMC 分層決策回測

核心規則：
  - T 日計算 SMC + EntryPlan，T+1 才能成交（防止前瞻偏差）
  - 三種成交模型：limit / conservative / close
  - 成本模型：US (0.05% slippage + SEC fee) / TW (佣金 + 交易稅)
  - 倉位由 decision engine 動態決定（核心/標準/探索）
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Callable, Awaitable

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.stock import Stock, PriceHistory
from ..schemas.decision import EntryPlan
from ..schemas.smc import SmcResult
from ..services.smc import run_smc_analysis_v2
from ..services.smc.config import SmcConfig, DEFAULT_CONFIG
from ..services.decision.entry import generate_entry_plan
from ..services.stock_grouper import assign_groups_batch
from ..services.diagnosis import generate_diagnosis

logger = logging.getLogger(__name__)

ProgressCb = Callable[[str, str, int, int], Awaitable[None]] | None


# ── Cost Models ──────────────────────────────────────────────────────────────

def us_cost(fill_price: float, shares: int, is_sell: bool) -> float:
    """美股成本：0.05% slippage + SEC fee (sell only)"""
    value = fill_price * shares
    cost = value * 0.0005  # slippage
    if is_sell:
        cost += value * 0.0000278  # SEC fee ~$27.8 per million
    return cost


def tw_cost(fill_price: float, shares: int, is_sell: bool) -> float:
    """台股成本：佣金 0.1425% × 0.6 折 (買賣都收) + 交易稅 0.3% (賣)"""
    value = fill_price * shares
    cost = value * 0.001425 * 0.6  # commission
    if is_sell:
        cost += value * 0.003  # transaction tax
    return cost


def calc_trade_cost(market: str, fill_price: float, shares: int, is_sell: bool, use_cost: bool) -> float:
    if not use_cost:
        return 0.0
    if market == "TW":
        return tw_cost(fill_price, shares, is_sell)
    return us_cost(fill_price, shares, is_sell)


# ── Fill Models ──────────────────────────────────────────────────────────────

def try_fill_limit(entry_price: float, ohlc: dict) -> float | None:
    """Limit order: T+1 日 Low <= entry_price → 以 entry_price 成交"""
    if ohlc["Low"] <= entry_price:
        return entry_price
    return None


def try_fill_conservative(entry_price: float, ohlc: dict) -> float | None:
    """Conservative: 考慮跳空，如果 Open > entry_price 則以 Open 成交 (slippage)"""
    if ohlc["Low"] <= entry_price:
        return max(entry_price, ohlc["Open"])  # gap up → worse fill
    return None


def try_fill_close(entry_price: float, ohlc: dict) -> float | None:
    """Close price: 無條件以 T+1 收盤價成交"""
    return ohlc["Close"]


FILL_MODELS = {
    "limit": try_fill_limit,
    "conservative": try_fill_conservative,
    "close": try_fill_close,
}


# ── Hash Utils ───────────────────────────────────────────────────────────────

def compute_strategy_hash(params: dict) -> str:
    raw = str(sorted(params.items()))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def compute_data_hash(universe: list[str], price_data: dict[str, pd.DataFrame]) -> str:
    parts = []
    for t in sorted(universe):
        df = price_data.get(t)
        if df is not None and len(df) > 0:
            last_date = str(df.index[-1])
            parts.append(f"{t}:{last_date}:{len(df)}")
    return hashlib.sha256(",".join(parts).encode()).hexdigest()[:16]


def compute_run_hash(
    strategy_hash: str, universe: list[str],
    start_date: date, end_date: date,
    data_hash: str, fill_model: str, cost_model: bool,
) -> str:
    raw = (
        strategy_hash
        + "|" + ",".join(sorted(universe))
        + f"|{start_date}|{end_date}"
        + f"|{data_hash}|{fill_model}|{cost_model}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Data Loading ─────────────────────────────────────────────────────────────

async def load_all_price_data(
    db: AsyncSession, market_filter: str = "ALL"
) -> tuple[list[dict], dict[str, pd.DataFrame]]:
    """
    載入所有股票 + price_history。
    Returns: (stocks_info, price_data)
      stocks_info: [{"ticker": "AAPL", "market": "US", "id": 1}, ...]
      price_data: {"AAPL": DataFrame(index=date, cols=OHLCV)}
    """
    q = select(Stock)
    if market_filter != "ALL":
        q = q.where(Stock.market == market_filter)
    stocks = (await db.execute(q)).scalars().all()
    stock_ids = {s.ticker: s.id for s in stocks}
    stocks_info = [{"ticker": s.ticker, "market": s.market, "id": s.id} for s in stocks]

    # batch load prices
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.stock_id.in_(stock_ids.values()))
        .order_by(PriceHistory.stock_id, PriceHistory.date)
    )
    rows = result.scalars().all()

    id_to_ticker = {v: k for k, v in stock_ids.items()}
    ticker_rows: dict[str, list] = {}
    for r in rows:
        t = id_to_ticker.get(r.stock_id)
        if t:
            ticker_rows.setdefault(t, []).append({
                "date": r.date,
                "Open": float(r.open or 0), "High": float(r.high or 0),
                "Low": float(r.low or 0), "Close": float(r.close or 0),
                "Volume": int(r.volume or 0),
            })

    price_data = {
        ticker: pd.DataFrame(rows_).set_index("date").sort_index()
        for ticker, rows_ in ticker_rows.items()
        if len(rows_) >= 60  # 至少 60 天才能跑 SMC
    }

    return stocks_info, price_data


# ── Resample Utils ───────────────────────────────────────────────────────────

def resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """從日線做週線"""
    if len(df) < 10:
        return pd.DataFrame()
    df_ts = df.copy()
    df_ts.index = pd.to_datetime(df_ts.index)
    weekly = df_ts.resample("W-FRI").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna()
    return weekly


def resample_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """從日線做月線"""
    if len(df) < 30:
        return pd.DataFrame()
    df_ts = df.copy()
    df_ts.index = pd.to_datetime(df_ts.index)
    monthly = df_ts.resample("ME").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna()
    return monthly


# ── SMC Pre-computation ──────────────────────────────────────────────────────

def precompute_smc_for_date(
    ticker: str,
    daily_df: pd.DataFrame,
    target_date: date,
    smc_cfg: SmcConfig,
    market: str = "US",
) -> dict | None:
    """
    計算 T 日的 SMC + EntryPlan。
    只使用 target_date 當天及之前的資料（防止前瞻偏差）。
    """
    sub = daily_df[daily_df.index <= target_date]
    if len(sub) < 60:
        return None

    try:
        smc_daily = run_smc_analysis_v2(ticker, sub, timeframe="daily", market=market, cfg=smc_cfg)
    except Exception as e:
        logger.warning(f"SMC failed for {ticker} on {target_date}: {e}")
        return None

    # Weekly / Monthly (simplified: use all data up to target_date)
    weekly_df = resample_weekly(sub)
    monthly_df = resample_monthly(sub)

    weekly_trend = "unknown"
    monthly_trend = "unknown"

    if len(weekly_df) >= 20:
        try:
            smc_w = run_smc_analysis_v2(ticker, weekly_df, timeframe="weekly", market=market, cfg=smc_cfg)
            weekly_trend = smc_w.structure.trend.value if hasattr(smc_w.structure.trend, 'value') else str(smc_w.structure.trend)
        except Exception:
            pass

    if len(monthly_df) >= 12:
        try:
            smc_m = run_smc_analysis_v2(ticker, monthly_df, timeframe="monthly", market=market, cfg=smc_cfg)
            monthly_trend = smc_m.structure.trend.value if hasattr(smc_m.structure.trend, 'value') else str(smc_m.structure.trend)
        except Exception:
            pass

    # Generate entry plan
    current_price = float(sub["Close"].iloc[-1])
    closes = sub["Close"].tolist()
    highs = sub["High"].tolist()
    lows = sub["Low"].tolist()

    try:
        from ..schemas.smc import TrendDirection
        wt = TrendDirection(weekly_trend) if weekly_trend != "unknown" else TrendDirection.INSUFFICIENT
        mt = TrendDirection(monthly_trend) if monthly_trend != "unknown" else TrendDirection.INSUFFICIENT
    except (ValueError, KeyError):
        from ..schemas.smc import TrendDirection
        wt = TrendDirection.INSUFFICIENT
        mt = TrendDirection.INSUFFICIENT

    try:
        plan = generate_entry_plan(
            smc=smc_daily,
            current_price=current_price,
            closes=closes, highs=highs, lows=lows,
            weekly_trend=wt,
            monthly_trend=mt,
        )
    except Exception as e:
        logger.warning(f"EntryPlan failed for {ticker} on {target_date}: {e}")
        return None

    return {
        "smc": smc_daily,
        "plan": plan,
        "daily_trend": smc_daily.structure.trend.value if hasattr(smc_daily.structure.trend, 'value') else str(smc_daily.structure.trend),
        "weekly_trend": weekly_trend,
        "monthly_trend": monthly_trend,
    }


# ── Position Tracking ────────────────────────────────────────────────────────

class Position:
    """回測中的持倉追蹤"""

    def __init__(
        self, ticker: str, market: str, group: str,
        signal_date: date, fill_date: date, fill_price: float,
        shares: int, entry_cost: float,
        entry_source: str, stop_price: float, target_price: float,
        stop_source: str, target_source: str,
        position_tier: str, conditions_met: int, position_size_pct: float,
        planned_rr: float, smc_trend: str,
    ):
        self.ticker = ticker
        self.market = market
        self.group = group
        self.signal_date = signal_date
        self.fill_date = fill_date
        self.fill_price = fill_price
        self.shares = shares
        self.entry_cost = entry_cost
        self.entry_source = entry_source
        self.stop_price = stop_price
        self.target_price = target_price
        self.stop_source = stop_source
        self.target_source = target_source
        self.position_tier = position_tier
        self.conditions_met = conditions_met
        self.position_size_pct = position_size_pct
        self.planned_rr = planned_rr
        self.smc_trend = smc_trend

        # tracking
        self.mae_price = fill_price  # worst price seen
        self.mfe_price = fill_price  # best price seen

    def update_mae_mfe(self, low: float, high: float):
        self.mae_price = min(self.mae_price, low)
        self.mfe_price = max(self.mfe_price, high)

    @property
    def mae_pct(self) -> float:
        return (self.mae_price - self.fill_price) / self.fill_price

    @property
    def mfe_pct(self) -> float:
        return (self.mfe_price - self.fill_price) / self.fill_price

    def value_at(self, price: float) -> float:
        return self.shares * price


# ── Main Backtest Engine ─────────────────────────────────────────────────────

async def run_backtest_v2(
    db: AsyncSession,
    params: dict,
    overrides: dict,
    stock_settings: dict,
    start_date: date,
    end_date: date,
    initial_capital: float = 1_000_000,
    market_filter: str = "ALL",
    progress_cb: ProgressCb = None,
) -> dict[str, Any]:
    """
    v2 回測引擎核心。

    Returns:
        {
            "strategy_hash": str,
            "run_hash": str,
            "data_hash": str,
            "stock_universe": [{"ticker": ..., "group": ...}],
            "metrics": {...},
            "trades": [TradeRecord, ...],
            "equity_curve": [EquityPoint, ...],
            "diagnosis": {...} | None,
            "duration_secs": float,
        }
    """
    t0 = time.time()

    # ── 1. Load data ──
    if progress_cb:
        await progress_cb("載入價格資料...", "loading", 0, 100)

    stocks_info, price_data = await load_all_price_data(db, market_filter)

    # Filter by stock_settings
    disabled = {t for t, v in stock_settings.items() if not v.get("enabled", True)}
    stocks_info = [s for s in stocks_info if s["ticker"] not in disabled and s["ticker"] in price_data]

    if not stocks_info:
        return {"error": "沒有可用的股票資料"}

    # ── 2. Assign groups (fixed at start_date) ──
    groups = assign_groups_batch(stocks_info, price_data, anchor_date=start_date)
    universe = [s["ticker"] for s in stocks_info]
    stock_market = {s["ticker"]: s["market"] for s in stocks_info}

    # Build merged params (global + group overrides)
    def get_params(ticker: str) -> dict:
        group = groups.get(ticker, "")
        merged = {**params}
        if group in overrides:
            merged.update(overrides[group])
        return merged

    # ── 3. Hashes ──
    strategy_hash = compute_strategy_hash(params)
    data_hash = compute_data_hash(universe, price_data)
    fill_model = params.get("fill_model", "limit")
    cost_model = params.get("cost_model", True)
    run_hash = compute_run_hash(
        strategy_hash, universe, start_date, end_date, data_hash, fill_model, cost_model,
    )

    # ── 4. SMC config ──
    smc_cfg_dict = params.get("smc_config", {})
    smc_cfg = SmcConfig(**smc_cfg_dict) if smc_cfg_dict else DEFAULT_CONFIG

    # ── 5. Get trading dates ──
    all_dates: set[date] = set()
    for df in price_data.values():
        all_dates.update(d for d in df.index if start_date <= d <= end_date)
    trading_days = sorted(all_dates)

    if len(trading_days) < 2:
        return {"error": "交易日不足"}

    # ── 6. Params ──
    fill_fn = FILL_MODELS.get(fill_model, try_fill_limit)
    min_rr = params.get("min_rr", 2.0)
    min_conditions = params.get("min_conditions", 2)
    max_positions = params.get("max_positions", 8)
    risk_per_trade = params.get("risk_per_trade", 0.02)
    max_heat = params.get("max_heat", 0.10)

    # ── 7. Main loop ──
    positions: list[Position] = []
    closed_trades: list[dict] = []
    equity_curve: list[dict] = []
    cash = float(initial_capital)
    smc_cache: dict[tuple[str, date], dict] = {}

    total_steps = len(trading_days)

    for day_idx, today in enumerate(trading_days):
        if progress_cb and day_idx % 20 == 0:
            pct = int((day_idx / total_steps) * 100)
            await progress_cb(f"回測中 {today}...", "backtesting", pct, 100)

        # === Phase A: 持倉管理（檢查出場）===
        still_open = []
        for pos in positions:
            df = price_data.get(pos.ticker)
            if df is None or today not in df.index:
                still_open.append(pos)
                continue

            ohlc = df.loc[today]
            pos.update_mae_mfe(float(ohlc["Low"]), float(ohlc["High"]))

            exit_price = None
            exit_reason = None

            # 停損: Low <= stop_price
            if float(ohlc["Low"]) <= pos.stop_price:
                exit_price = pos.stop_price
                # 如果跳空低開，以 Open 成交（更差）
                if float(ohlc["Open"]) < pos.stop_price:
                    exit_price = float(ohlc["Open"])
                exit_reason = "停損"

            # 停利: High >= target_price (如果同日也觸停損，停損優先 — conservative)
            if exit_reason is None and float(ohlc["High"]) >= pos.target_price:
                exit_price = pos.target_price
                if float(ohlc["Open"]) > pos.target_price:
                    exit_price = float(ohlc["Open"])
                exit_reason = "停利"

            if exit_price is not None:
                sell_cost = calc_trade_cost(pos.market, exit_price, pos.shares, True, cost_model)
                pnl_amount = (exit_price - pos.fill_price) * pos.shares
                net_pnl = pnl_amount - pos.entry_cost - sell_cost
                pnl_pct = (exit_price - pos.fill_price) / pos.fill_price

                actual_rr = None
                risk = pos.fill_price - pos.stop_price
                if risk > 0:
                    actual_rr = (exit_price - pos.fill_price) / risk

                closed_trades.append({
                    "ticker": pos.ticker, "market": pos.market, "stock_group": pos.group,
                    "signal_date": pos.signal_date, "fill_date": pos.fill_date,
                    "fill_price": pos.fill_price, "entry_source": pos.entry_source,
                    "position_tier": pos.position_tier, "conditions_met": pos.conditions_met,
                    "position_size_pct": pos.position_size_pct,
                    "exit_date": today, "exit_price": exit_price, "exit_reason": exit_reason,
                    "stop_source": pos.stop_source, "target_source": pos.target_source,
                    "planned_rr": pos.planned_rr, "actual_rr": actual_rr,
                    "pnl_pct": pnl_pct, "pnl_amount": pnl_amount,
                    "trade_cost": pos.entry_cost + sell_cost, "net_pnl": net_pnl,
                    "holding_days": (today - pos.fill_date).days,
                    "mae_pct": pos.mae_pct, "mfe_pct": pos.mfe_pct,
                    "smc_trend_at_entry": pos.smc_trend, "smc_trend_at_exit": None,
                })
                cash += exit_price * pos.shares - sell_cost
            else:
                still_open.append(pos)

        positions = still_open

        # === Phase B: 新倉進場 ===
        # T 日信號 = 前一個交易日的 SMC 計算
        if day_idx == 0:
            # 第一天無法用前一天信號
            pass
        else:
            prev_day = trading_days[day_idx - 1]

            # 計算前一天的 SMC (如果還沒算過)
            signals = []
            for s in stocks_info:
                ticker = s["ticker"]
                cache_key = (ticker, prev_day)

                if cache_key not in smc_cache:
                    df = price_data.get(ticker)
                    if df is not None:
                        result = precompute_smc_for_date(ticker, df, prev_day, smc_cfg, s["market"])
                        smc_cache[cache_key] = result
                    else:
                        smc_cache[cache_key] = None

                smc_result = smc_cache[cache_key]
                if smc_result is None:
                    continue

                plan: EntryPlan = smc_result["plan"]
                p = get_params(ticker)

                # 過濾條件
                if plan.conditions_met < p.get("min_conditions", min_conditions):
                    continue
                if plan.rr_ratio is not None and plan.rr_ratio < p.get("min_rr", min_rr):
                    continue
                if plan.entry_price is None or plan.stop_price is None or plan.target_price is None:
                    continue
                if plan.action == "不操作":
                    continue

                signals.append((ticker, s["market"], plan, smc_result["daily_trend"]))

            # 按 R:R 排序（高優先）
            signals.sort(key=lambda x: x[2].rr_ratio or 0, reverse=True)

            # 嘗試進場
            held_tickers = {p.ticker for p in positions}
            for ticker, market, plan, trend in signals:
                if len(positions) >= max_positions:
                    break
                if ticker in held_tickers:
                    continue

                # 今日 OHLC
                df = price_data.get(ticker)
                if df is None or today not in df.index:
                    continue
                ohlc = df.loc[today]

                # 成交嘗試
                fill_price = fill_fn(plan.entry_price, {
                    "Open": float(ohlc["Open"]),
                    "High": float(ohlc["High"]),
                    "Low": float(ohlc["Low"]),
                    "Close": float(ohlc["Close"]),
                })
                if fill_price is None:
                    continue

                # 倉位計算
                total_equity = cash + sum(
                    p.value_at(float(price_data[p.ticker].loc[today]["Close"]))
                    for p in positions
                    if p.ticker in price_data and today in price_data[p.ticker].index
                )
                position_pct = plan.max_position_pct / 100 if plan.max_position_pct > 1 else plan.max_position_pct
                if position_pct <= 0:
                    continue

                # risk-based sizing: risk_per_trade * equity / (entry - stop)
                risk_amount = total_equity * risk_per_trade
                price_risk = fill_price - plan.stop_price
                if price_risk <= 0:
                    continue
                risk_based_shares = int(risk_amount / price_risk)

                # tier-based sizing
                tier_amount = total_equity * position_pct
                tier_based_shares = int(tier_amount / fill_price)

                # take the smaller of the two
                shares = min(risk_based_shares, tier_based_shares)
                if shares <= 0:
                    continue

                # check cash
                buy_value = fill_price * shares
                entry_cost = calc_trade_cost(market, fill_price, shares, False, cost_model)
                if buy_value + entry_cost > cash:
                    shares = int((cash * 0.98) / fill_price)  # leave 2% buffer
                    if shares <= 0:
                        continue
                    buy_value = fill_price * shares
                    entry_cost = calc_trade_cost(market, fill_price, shares, False, cost_model)

                # portfolio heat check
                current_heat = sum(
                    (p.fill_price - p.stop_price) * p.shares / total_equity
                    for p in positions
                ) if total_equity > 0 else 0
                new_heat = price_risk * shares / total_equity if total_equity > 0 else 0
                if current_heat + new_heat > max_heat:
                    continue

                cash -= buy_value + entry_cost

                positions.append(Position(
                    ticker=ticker, market=market, group=groups.get(ticker, ""),
                    signal_date=prev_day, fill_date=today, fill_price=fill_price,
                    shares=shares, entry_cost=entry_cost,
                    entry_source=plan.entry_source,
                    stop_price=plan.stop_price, target_price=plan.target_price,
                    stop_source=plan.stop_source, target_source=plan.target_source,
                    position_tier=plan.position_tier,
                    conditions_met=plan.conditions_met,
                    position_size_pct=position_pct * 100,
                    planned_rr=plan.rr_ratio or 0,
                    smc_trend=trend,
                ))
                held_tickers.add(ticker)

        # === Phase C: Record equity ===
        positions_value = 0
        for p in positions:
            df = price_data.get(p.ticker)
            if df is not None and today in df.index:
                positions_value += p.value_at(float(df.loc[today]["Close"]))

        total_equity = cash + positions_value
        peak = max(
            (eq["equity"] for eq in equity_curve),
            default=initial_capital,
        )
        peak = max(peak, total_equity)
        dd_pct = (total_equity - peak) / peak if peak > 0 else 0

        equity_curve.append({
            "trade_date": today,
            "equity": round(total_equity, 2),
            "drawdown_pct": round(dd_pct, 4),
            "cash": round(cash, 2),
            "positions_value": round(positions_value, 2),
            "open_positions": len(positions),
        })

    # ── Force close remaining positions ──
    last_day = trading_days[-1] if trading_days else end_date
    for pos in positions:
        df = price_data.get(pos.ticker)
        if df is not None and last_day in df.index:
            close_price = float(df.loc[last_day]["Close"])
        else:
            close_price = pos.fill_price  # fallback

        sell_cost = calc_trade_cost(pos.market, close_price, pos.shares, True, cost_model)
        pnl_amount = (close_price - pos.fill_price) * pos.shares
        net_pnl = pnl_amount - pos.entry_cost - sell_cost
        pnl_pct = (close_price - pos.fill_price) / pos.fill_price

        risk = pos.fill_price - pos.stop_price
        actual_rr = (close_price - pos.fill_price) / risk if risk > 0 else None

        closed_trades.append({
            "ticker": pos.ticker, "market": pos.market, "stock_group": pos.group,
            "signal_date": pos.signal_date, "fill_date": pos.fill_date,
            "fill_price": pos.fill_price, "entry_source": pos.entry_source,
            "position_tier": pos.position_tier, "conditions_met": pos.conditions_met,
            "position_size_pct": pos.position_size_pct,
            "exit_date": last_day, "exit_price": close_price, "exit_reason": "強制平倉",
            "stop_source": pos.stop_source, "target_source": pos.target_source,
            "planned_rr": pos.planned_rr, "actual_rr": actual_rr,
            "pnl_pct": pnl_pct, "pnl_amount": pnl_amount,
            "trade_cost": pos.entry_cost + sell_cost, "net_pnl": net_pnl,
            "holding_days": (last_day - pos.fill_date).days,
            "mae_pct": pos.mae_pct, "mfe_pct": pos.mfe_pct,
            "smc_trend_at_entry": pos.smc_trend, "smc_trend_at_exit": None,
        })

    # ── 8. Calculate metrics + diagnosis ──
    metrics = calc_metrics(closed_trades, equity_curve, initial_capital, trading_days)
    diagnosis = generate_diagnosis(closed_trades, metrics)

    duration = time.time() - t0

    if progress_cb:
        await progress_cb("回測完成", "done", 100, 100)

    return {
        "strategy_hash": strategy_hash,
        "run_hash": run_hash,
        "data_hash": data_hash,
        "stock_universe": [{"ticker": t, "group": groups.get(t, "")} for t in universe],
        "metrics": metrics,
        "diagnosis": diagnosis,
        "trades": closed_trades,
        "equity_curve": equity_curve,
        "duration_secs": round(duration, 1),
        "stock_count": len(universe),
        "trading_days": len(trading_days),
    }


# ── Metrics Calculation ──────────────────────────────────────────────────────

def calc_metrics(
    trades: list[dict],
    equity_curve: list[dict],
    initial_capital: float,
    trading_days: list[date],
) -> dict:
    if not trades:
        return {
            "total_return_pct": 0, "annual_return_pct": 0,
            "max_drawdown_pct": 0, "sharpe_ratio": 0,
            "win_rate": 0, "total_trades": 0,
            "profitable_trades": 0, "losing_trades": 0,
            "avg_profit_pct": 0, "avg_loss_pct": 0,
            "profit_factor": 0, "total_cost": 0,
            "by_exit_reason": {}, "by_tier": {}, "by_group": {},
        }

    winners = [t for t in trades if (t.get("pnl_pct") or 0) > 0]
    losers = [t for t in trades if (t.get("pnl_pct") or 0) <= 0]

    final_equity = equity_curve[-1]["equity"] if equity_curve else initial_capital
    total_return_pct = (final_equity - initial_capital) / initial_capital * 100

    # Annualized
    n_days = len(trading_days)
    years = n_days / 252 if n_days > 0 else 1
    annual_return_pct = ((final_equity / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

    # Max drawdown
    max_dd = min((e["drawdown_pct"] for e in equity_curve), default=0) * 100

    # Sharpe (daily returns)
    if len(equity_curve) > 1:
        equities = [e["equity"] for e in equity_curve]
        daily_returns = [(equities[i] - equities[i-1]) / equities[i-1] for i in range(1, len(equities))]
        mean_r = np.mean(daily_returns)
        std_r = np.std(daily_returns)
        sharpe = (mean_r / std_r * np.sqrt(252)) if std_r > 0 else 0
    else:
        sharpe = 0

    # Win rate
    win_rate = len(winners) / len(trades) * 100 if trades else 0

    # Avg profit/loss
    avg_profit = np.mean([t["pnl_pct"] for t in winners]) * 100 if winners else 0
    avg_loss = np.mean([t["pnl_pct"] for t in losers]) * 100 if losers else 0

    # Profit factor
    gross_profit = sum(t.get("net_pnl", 0) for t in winners)
    gross_loss = abs(sum(t.get("net_pnl", 0) for t in losers))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

    # Total cost
    total_cost = sum(t.get("trade_cost", 0) for t in trades)

    # By exit reason
    by_exit = defaultdict(lambda: {"count": 0, "total_pnl_pct": 0})
    for t in trades:
        r = t.get("exit_reason", "unknown")
        by_exit[r]["count"] += 1
        by_exit[r]["total_pnl_pct"] += (t.get("pnl_pct") or 0) * 100
    for v in by_exit.values():
        v["avg_pnl_pct"] = round(v["total_pnl_pct"] / v["count"], 2) if v["count"] else 0
        v["total_pnl_pct"] = round(v["total_pnl_pct"], 2)

    # By tier
    by_tier = defaultdict(lambda: {"count": 0, "total_pnl_pct": 0})
    for t in trades:
        tier = t.get("position_tier", "unknown")
        by_tier[tier]["count"] += 1
        by_tier[tier]["total_pnl_pct"] += (t.get("pnl_pct") or 0) * 100
    for v in by_tier.values():
        v["avg_pnl_pct"] = round(v["total_pnl_pct"] / v["count"], 2) if v["count"] else 0
        v["total_pnl_pct"] = round(v["total_pnl_pct"], 2)

    # By group
    by_group = defaultdict(lambda: {"count": 0, "total_pnl_pct": 0})
    for t in trades:
        g = t.get("stock_group", "unknown")
        by_group[g]["count"] += 1
        by_group[g]["total_pnl_pct"] += (t.get("pnl_pct") or 0) * 100
    for v in by_group.values():
        v["avg_pnl_pct"] = round(v["total_pnl_pct"] / v["count"], 2) if v["count"] else 0
        v["total_pnl_pct"] = round(v["total_pnl_pct"], 2)

    return {
        "total_return_pct": round(total_return_pct, 2),
        "annual_return_pct": round(annual_return_pct, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 2),
        "win_rate": round(win_rate, 1),
        "total_trades": len(trades),
        "profitable_trades": len(winners),
        "losing_trades": len(losers),
        "avg_profit_pct": round(avg_profit, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 999,
        "total_cost": round(total_cost, 2),
        "by_exit_reason": dict(by_exit),
        "by_tier": dict(by_tier),
        "by_group": dict(by_group),
    }
