"""
回測診斷報告生成

分析回測結果，產出可執行的改進建議：
  - 各趨勢下的勝率
  - 各倉位等級的表現
  - 各群組的成本佔比
  - MAE/MFE 分析
  - 停損/停利效率
"""

from __future__ import annotations
from collections import defaultdict


def generate_diagnosis(trades: list[dict], metrics: dict) -> dict:
    """
    從回測交易明細生成診斷報告。

    Returns:
        {
            "highlights": [str, ...],       # 重點發現
            "warnings": [str, ...],         # 風險警告
            "suggestions": [str, ...],      # 改進建議
            "by_trend": {...},              # 按趨勢分析
            "by_tier": {...},               # 按倉位等級
            "by_group": {...},              # 按股票群組
            "stop_efficiency": {...},       # 停損效率
            "target_efficiency": {...},     # 停利效率
            "mae_mfe_analysis": {...},      # MAE/MFE 分析
        }
    """
    if not trades:
        return {"highlights": ["無交易記錄"], "warnings": [], "suggestions": []}

    highlights = []
    warnings = []
    suggestions = []

    # ── 按趨勢分析 ──
    by_trend = defaultdict(lambda: {"count": 0, "wins": 0, "total_pnl": 0})
    for t in trades:
        trend = t.get("smc_trend_at_entry", "unknown") or "unknown"
        by_trend[trend]["count"] += 1
        pnl = t.get("pnl_pct", 0) or 0
        by_trend[trend]["total_pnl"] += pnl
        if pnl > 0:
            by_trend[trend]["wins"] += 1

    for trend, data in by_trend.items():
        data["win_rate"] = round(data["wins"] / data["count"] * 100, 1) if data["count"] else 0
        data["avg_pnl"] = round(data["total_pnl"] / data["count"] * 100, 2) if data["count"] else 0

    # 上升趨勢勝率
    up = by_trend.get("uptrend", by_trend.get("up", {}))
    if up and up.get("win_rate", 0) >= 60:
        highlights.append(f"上升趨勢勝率 {up['win_rate']}%，策略方向正確")
    weak_up = by_trend.get("weak_uptrend", by_trend.get("weak_up", {}))
    if weak_up and weak_up.get("count", 0) > 3 and weak_up.get("win_rate", 0) < 45:
        warnings.append(f"弱上升趨勢勝率僅 {weak_up['win_rate']}%，考慮提高進場條件")

    # ── 按倉位等級 ──
    by_tier = defaultdict(lambda: {"count": 0, "wins": 0, "total_pnl": 0})
    for t in trades:
        tier = t.get("position_tier", "unknown") or "unknown"
        by_tier[tier]["count"] += 1
        pnl = t.get("pnl_pct", 0) or 0
        by_tier[tier]["total_pnl"] += pnl
        if pnl > 0:
            by_tier[tier]["wins"] += 1

    for tier, data in by_tier.items():
        data["win_rate"] = round(data["wins"] / data["count"] * 100, 1) if data["count"] else 0
        data["avg_pnl"] = round(data["total_pnl"] / data["count"] * 100, 2) if data["count"] else 0

    core = by_tier.get("核心持倉", by_tier.get("核心", {}))
    if core and core.get("avg_pnl", 0) > 0:
        highlights.append(f"核心持倉平均獲利 {core['avg_pnl']}%")

    explore = by_tier.get("探索倉位", by_tier.get("探索", {}))
    if explore and explore.get("avg_pnl", 0) < 0:
        suggestions.append("探索倉位虧損，建議提高 min_conditions 或 min_rr")

    # ── 按群組分析 ──
    by_group = defaultdict(lambda: {"count": 0, "total_cost": 0, "total_pnl": 0})
    for t in trades:
        g = t.get("stock_group", "unknown") or "unknown"
        by_group[g]["count"] += 1
        by_group[g]["total_cost"] += t.get("trade_cost", 0) or 0
        by_group[g]["total_pnl"] += t.get("net_pnl", 0) or 0

    for g, data in by_group.items():
        gross_profit = data["total_pnl"] + data["total_cost"]
        if gross_profit > 0:
            data["cost_ratio"] = round(data["total_cost"] / gross_profit * 100, 1)
        else:
            data["cost_ratio"] = 0
        if data["cost_ratio"] > 15:
            warnings.append(f"{g} 成本佔獲利 {data['cost_ratio']}%，考慮提高 R:R 門檻")

    # ── 停損效率 ──
    stop_trades = [t for t in trades if t.get("exit_reason") == "停損"]
    target_trades = [t for t in trades if t.get("exit_reason") == "停利"]

    stop_efficiency = {}
    if stop_trades:
        avg_stop_loss = sum(abs(t.get("pnl_pct", 0)) for t in stop_trades) / len(stop_trades) * 100
        stop_efficiency = {
            "count": len(stop_trades),
            "avg_loss_pct": round(avg_stop_loss, 2),
            "pct_of_total": round(len(stop_trades) / len(trades) * 100, 1),
        }
        if stop_efficiency["pct_of_total"] > 50:
            warnings.append(f"停損觸發率 {stop_efficiency['pct_of_total']}%，進場品質可能需要改善")

    target_efficiency = {}
    if target_trades:
        avg_target_gain = sum(t.get("pnl_pct", 0) for t in target_trades) / len(target_trades) * 100
        target_efficiency = {
            "count": len(target_trades),
            "avg_gain_pct": round(avg_target_gain, 2),
            "pct_of_total": round(len(target_trades) / len(trades) * 100, 1),
        }

    # ── MAE/MFE 分析 ──
    mae_mfe = {}
    maes = [t.get("mae_pct", 0) or 0 for t in trades]
    mfes = [t.get("mfe_pct", 0) or 0 for t in trades]
    if maes:
        mae_mfe["avg_mae_pct"] = round(sum(maes) / len(maes) * 100, 2)
        mae_mfe["avg_mfe_pct"] = round(sum(mfes) / len(mfes) * 100, 2)
        mae_mfe["max_mae_pct"] = round(min(maes) * 100, 2)
        mae_mfe["max_mfe_pct"] = round(max(mfes) * 100, 2)

        # 勝的交易裡 MAE 很大 → 停損可以更緊
        winning_maes = [t.get("mae_pct", 0) or 0 for t in trades if (t.get("pnl_pct") or 0) > 0]
        if winning_maes:
            avg_winning_mae = abs(sum(winning_maes) / len(winning_maes)) * 100
            mae_mfe["avg_winning_mae_pct"] = round(avg_winning_mae, 2)
            if avg_winning_mae > 3:
                suggestions.append(f"獲利交易平均 MAE {avg_winning_mae:.1f}%，可考慮更緊的停損")

    # ── 整體診斷 ──
    total_return = metrics.get("total_return_pct", 0)
    sharpe = metrics.get("sharpe_ratio", 0)
    max_dd = metrics.get("max_drawdown_pct", 0)

    if total_return > 0 and sharpe > 1.0:
        highlights.append(f"總報酬 {total_return}%，Sharpe {sharpe} — 策略有效")
    if abs(max_dd) > 20:
        warnings.append(f"最大回撤 {max_dd}%，風險偏高")
    if metrics.get("win_rate", 0) < 40:
        suggestions.append("勝率偏低，建議檢視進場條件是否太寬鬆")

    return {
        "highlights": highlights,
        "warnings": warnings,
        "suggestions": suggestions,
        "by_trend": dict(by_trend),
        "by_tier": dict(by_tier),
        "by_group": dict(by_group),
        "stop_efficiency": stop_efficiency,
        "target_efficiency": target_efficiency,
        "mae_mfe_analysis": mae_mfe,
    }
