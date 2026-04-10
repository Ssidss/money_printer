"""
Backtest V3 — Metrics Calculator

三層報表：
  Level 1: Portfolio Summary（14 個指標）
  Level 2: Strategy Breakdown（按策略/regime/tier 拆分）
  Level 3: Trade Log（每筆交易明細）

Spec: docs/MULTI_STRATEGY_DESIGN.md 第九節
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np


def calculate_metrics(result: dict) -> dict:
    """
    從 engine 的 raw result 計算完整 metrics。
    回傳三層報表結構。
    """
    trades = result["trades"]
    equity_curve = result["equity_curve"]
    initial_capital = result["initial_capital"]
    final_equity = result["final_equity"]

    # ── Level 1: Portfolio Summary ──
    level1 = _portfolio_summary(trades, equity_curve, initial_capital, final_equity)

    # ── Level 2: Strategy Breakdown ──
    level2 = _strategy_breakdown(trades)

    # ── Level 3: Trade Log ──
    level3 = trades  # 已經有完整欄位

    return {
        "portfolio_summary": level1,
        "strategy_breakdown": level2,
        "trade_log": level3,
        "equity_curve": equity_curve,
        "order_stats": result.get("order_stats", {}),
        "kill_switch": result.get("kill_switch", {}),
        "open_positions": result.get("open_positions", []),
    }


def _portfolio_summary(
    trades: list[dict],
    equity_curve: list[dict],
    initial_capital: float,
    final_equity: float,
) -> dict:
    """Level 1: 14 個核心指標"""

    total_return_pct = (final_equity - initial_capital) / initial_capital * 100 if initial_capital > 0 else 0

    # CAGR
    if equity_curve:
        trading_days = len(equity_curve)
        years = trading_days / 252
        if years > 0 and final_equity > 0 and initial_capital > 0:
            cagr = (final_equity / initial_capital) ** (1 / years) - 1
            cagr_pct = cagr * 100
        else:
            cagr_pct = 0.0
    else:
        cagr_pct = 0.0
        trading_days = 0

    # Max Drawdown
    max_dd = 0.0
    if equity_curve:
        max_dd = max(e["drawdown_pct"] for e in equity_curve)

    # Sharpe Ratio (daily returns annualized)
    daily_returns = _daily_returns(equity_curve)
    sharpe = _sharpe_ratio(daily_returns)

    # Sortino Ratio
    sortino = _sortino_ratio(daily_returns)

    # Calmar Ratio
    calmar = abs(cagr_pct / max_dd) if max_dd > 0 else 0.0

    # Trade stats
    total_trades = len(trades)
    winning = [t for t in trades if (t.get("net_pnl") or 0) > 0]
    losing = [t for t in trades if (t.get("net_pnl") or 0) <= 0]
    win_rate = len(winning) / total_trades * 100 if total_trades > 0 else 0

    # Profit Factor
    total_wins = sum(t.get("net_pnl", 0) for t in winning)
    total_losses = abs(sum(t.get("net_pnl", 0) for t in losing))
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf') if total_wins > 0 else 0

    # Avg holding days
    holding_days_list = [t.get("holding_days", 0) for t in trades]
    avg_holding = sum(holding_days_list) / len(holding_days_list) if holding_days_list else 0

    # Expectancy
    avg_win = np.mean([t.get("pnl_pct", 0) for t in winning]) if winning else 0
    avg_loss = abs(np.mean([t.get("pnl_pct", 0) for t in losing])) if losing else 0
    win_pct = len(winning) / total_trades if total_trades > 0 else 0
    loss_pct = 1 - win_pct
    expectancy = win_pct * avg_win - loss_pct * avg_loss

    # Avg exposure
    avg_exposure = np.mean([
        e.get("positions_value", 0) / e["equity"] * 100
        for e in equity_curve
        if e.get("equity", 0) > 0
    ]) if equity_curve else 0

    # Max consecutive losses
    max_consec = _max_consecutive_losses(trades)

    # CVaR 5% (Expected Shortfall)
    pnl_pcts = sorted([t.get("pnl_pct", 0) for t in trades])
    n5 = max(1, int(len(pnl_pcts) * 0.05))
    cvar_5 = np.mean(pnl_pcts[:n5]) if pnl_pcts else 0

    return {
        "total_return_pct": round(total_return_pct, 2),
        "cagr_pct": round(cagr_pct, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3),
        "calmar_ratio": round(calmar, 3),
        "profit_factor": round(profit_factor, 2),
        "win_rate_pct": round(win_rate, 1),
        "total_trades": total_trades,
        "avg_holding_days": round(avg_holding, 1),
        "expectancy": round(expectancy, 3),
        "avg_exposure_pct": round(avg_exposure, 1),
        "max_consecutive_losses": max_consec,
        "tail_risk_cvar_5pct": round(cvar_5, 2),
        # Extra useful
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(-avg_loss, 2),
        "trading_days": trading_days,
        "final_equity": round(final_equity, 2),
        "initial_capital": round(initial_capital, 2),
    }


def _strategy_breakdown(trades: list[dict]) -> dict:
    """Level 2: 按策略拆分"""
    by_strategy = {}
    for t in trades:
        sn = t.get("strategy_name", "unknown")
        by_strategy.setdefault(sn, []).append(t)

    result = {}
    for sn, strategy_trades in by_strategy.items():
        pnls = [t.get("pnl_pct", 0) for t in strategy_trades]
        winning = [t for t in strategy_trades if (t.get("net_pnl") or 0) > 0]
        losing = [t for t in strategy_trades if (t.get("net_pnl") or 0) <= 0]
        total_wins = sum(t.get("net_pnl", 0) for t in winning)
        total_losses = abs(sum(t.get("net_pnl", 0) for t in losing))

        result[sn] = {
            "total_trades": len(strategy_trades),
            "win_rate_pct": round(len(winning) / len(strategy_trades) * 100, 1) if strategy_trades else 0,
            "profit_factor": round(total_wins / total_losses, 2) if total_losses > 0 else 0,
            "avg_pnl_pct": round(np.mean(pnls), 2) if pnls else 0,
            "max_consecutive_losses": _max_consecutive_losses(strategy_trades),
        }

    # 按 exit_reason 拆分
    by_exit = {}
    for t in trades:
        er = t.get("exit_reason", "unknown")
        by_exit.setdefault(er, []).append(t)

    exit_breakdown = {}
    for er, er_trades in by_exit.items():
        exit_breakdown[er] = {
            "count": len(er_trades),
            "avg_pnl_pct": round(np.mean([t.get("pnl_pct", 0) for t in er_trades]), 2),
            "total_pnl": round(sum(t.get("net_pnl", 0) for t in er_trades), 2),
        }

    return {
        "by_strategy": result,
        "by_exit_reason": exit_breakdown,
    }


# ── Helpers ──────────────────────────────────────────────────────────

def _daily_returns(equity_curve: list[dict]) -> list[float]:
    """從 equity curve 算 daily returns"""
    if len(equity_curve) < 2:
        return []
    returns = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]["equity"]
        curr = equity_curve[i]["equity"]
        if prev > 0:
            returns.append((curr - prev) / prev)
    return returns


def _sharpe_ratio(daily_returns: list[float], risk_free: float = 0.0) -> float:
    """Sharpe = mean(excess_return) / std(return) × √252"""
    if len(daily_returns) < 30:
        return 0.0
    arr = np.array(daily_returns)
    excess = arr - risk_free / 252
    std = np.std(excess, ddof=1)
    if std == 0:
        return 0.0
    return float(np.mean(excess) / std * math.sqrt(252))


def _sortino_ratio(daily_returns: list[float], risk_free: float = 0.0) -> float:
    """Sortino = mean(excess_return) / downside_std × √252"""
    if len(daily_returns) < 30:
        return 0.0
    arr = np.array(daily_returns)
    excess = arr - risk_free / 252
    downside = excess[excess < 0]
    if len(downside) == 0:
        return 0.0
    downside_std = np.std(downside, ddof=1)
    if downside_std == 0:
        return 0.0
    return float(np.mean(excess) / downside_std * math.sqrt(252))


def _max_consecutive_losses(trades: list[dict]) -> int:
    """最大連續虧損次數"""
    max_streak = 0
    current = 0
    for t in trades:
        if (t.get("net_pnl") or 0) <= 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak
