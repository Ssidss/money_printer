from __future__ import annotations
"""
回測引擎 Service
用歷史資料模擬推薦策略的買賣表現，計算績效指標
"""

import logging
import math
from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.stock import Stock, PriceHistory
from .technical import analyze_df
from .smc import find_structure

logger = logging.getLogger(__name__)

# 與 recommender v2 保持一致的 SMC 調整係數
# 注意：下降趨勢在 SMC 過濾階段已被排除（不進入排序）
_SMC_MULT = {
    "上升趨勢": 1.10,
    "盤整":     0.92,
    "下降趨勢": 0.50,   # 理論上不會用到（已被過濾），保留作為 fallback
    "未知":     1.00,
}


def _get_trading_dates(df_map: dict[str, pd.DataFrame]) -> list[date]:
    """從所有股票的 price_history 取得交易日列表"""
    all_dates = set()
    for df in df_map.values():
        all_dates.update(df.index.tolist())
    return sorted(all_dates)


async def _load_all_price_dfs(db: AsyncSession, stock_ids: dict[str, int]) -> dict[str, pd.DataFrame]:
    """批次從 DB 載入所有股票的完整 price_history"""
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
                "date": r.date, "Open": float(r.open or 0), "High": float(r.high or 0),
                "Low": float(r.low or 0), "Close": float(r.close or 0),
                "Volume": int(r.volume or 0),
            })

    return {
        ticker: pd.DataFrame(rows_).set_index("date")
        for ticker, rows_ in ticker_rows.items()
        if len(rows_) >= 30
    }


def _calc_technical_score(df: pd.DataFrame, end_date: date) -> float | None:
    """取到 end_date 當天的技術分析分數"""
    sub = df[df.index <= end_date]
    if len(sub) < 30:
        return None
    try:
        return analyze_df(sub)["score"]
    except Exception:
        return None


def _calc_smc_trend(df: pd.DataFrame, end_date: date, lookback: int = 60) -> str:
    """取到 end_date 的 SMC 市場結構趨勢（上升/下降/盤整/未知）"""
    sub = df[df.index <= end_date].tail(lookback)
    if len(sub) < 30:
        return "未知"
    try:
        return find_structure(sub).get("trend", "未知")
    except Exception:
        return "未知"


def _adjusted_score(tech_score: float, smc_trend: str) -> float:
    """套用 SMC 乘數後的綜合分（用於買入優先順序排序）"""
    return tech_score * _SMC_MULT.get(smc_trend, 1.0)


def _calc_metrics(trades: list[dict], equity_curve: list[dict], initial_capital: float) -> dict:
    """從交易紀錄計算績效指標"""
    if not trades:
        return {
            "total_return_pct": 0, "annual_return_pct": 0,
            "max_drawdown_pct": 0, "sharpe_ratio": 0,
            "win_rate": 0, "total_trades": 0, "profitable_trades": 0,
            "avg_profit_pct": 0, "avg_loss_pct": 0,
        }

    pnls = [t["pnl_pct"] for t in trades]
    profitable = [p for p in pnls if p > 0]
    losing = [p for p in pnls if p <= 0]

    # 最終資本
    final_equity = equity_curve[-1]["equity"] if equity_curve else initial_capital
    total_return = (final_equity - initial_capital) / initial_capital * 100

    # 年化報酬（假設 252 交易日/年）
    if equity_curve:
        days = (pd.to_datetime(equity_curve[-1]["date"]) - pd.to_datetime(equity_curve[0]["date"])).days
        years = max(days / 365, 0.01)
    else:
        years = 1
    annual_return = ((1 + total_return / 100) ** (1 / years) - 1) * 100

    # 最大回撤
    equities = [e["equity"] for e in equity_curve]
    max_dd = 0.0
    peak = equities[0] if equities else initial_capital
    for eq in equities:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Sharpe（用每日報酬率估算）
    if len(equities) > 1:
        daily_returns = [(equities[i] - equities[i-1]) / equities[i-1] for i in range(1, len(equities))]
        avg_dr = sum(daily_returns) / len(daily_returns)
        std_dr = (sum((r - avg_dr) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
        sharpe = (avg_dr / std_dr * math.sqrt(252)) if std_dr > 0 else 0
    else:
        sharpe = 0

    return {
        "total_return_pct": round(total_return, 2),
        "annual_return_pct": round(annual_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 3),
        "win_rate": round(len(profitable) / len(pnls) * 100, 1),
        "total_trades": len(trades),
        "profitable_trades": len(profitable),
        "avg_profit_pct": round(sum(profitable) / len(profitable), 2) if profitable else 0,
        "avg_loss_pct": round(sum(losing) / len(losing), 2) if losing else 0,
    }


async def run_backtest(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    buy_threshold: float = 60.0,      # 技術分 >= 此值才考慮買入
    stop_loss_pct: float = 0.07,
    trailing_stop_pct: float = 0.05,
    initial_capital: float = 1_000_000,
    position_size_pct: float = 0.1,    # 每次買入占總資金 10%
    max_positions: int = 5,            # 最多同時持有幾支
    use_smc_filter: bool = True,       # 是否啟用 SMC 趨勢過濾
    smc_exit_on_downtrend: bool = True, # 持倉中途若 SMC 轉下降趨勢則出場
    progress_cb=None,
) -> dict:
    """
    執行回測

    Args:
        start_date / end_date: 回測期間
        buy_threshold: 技術分超過此值才買入
        stop_loss_pct: 停損比例
        trailing_stop_pct: 追蹤停損比例（利潤達 5% 後啟動）
        initial_capital: 初始資金
        position_size_pct: 每筆交易占總資產比例
        max_positions: 最多同時持倉數
    """
    if progress_cb:
        await progress_cb("載入股價資料中...", phase="loading", current=0, total=100)

    # 載入所有股票 ID
    result = await db.execute(select(Stock).where(Stock.is_active == True))
    stocks = result.scalars().all()
    stock_ids = {s.ticker: s.id for s in stocks}

    price_dfs = await _load_all_price_dfs(db, stock_ids)
    trading_dates = [d for d in _get_trading_dates(price_dfs) if start_date <= d <= end_date]

    if not trading_dates:
        return {"error": "回測期間內無交易日資料"}

    if progress_cb:
        await progress_cb(
            f"開始回測 {start_date} ~ {end_date}，共 {len(trading_dates)} 個交易日",
            phase="backtesting", current=0, total=len(trading_dates)
        )

    capital = initial_capital
    positions: dict[str, dict] = {}    # ticker → {buy_price, shares, highest, buy_date}
    trades: list[dict] = []
    equity_curve: list[dict] = []

    for idx, today in enumerate(trading_dates):
        # ── 賣出檢查 ──────────────────────────────────────────────────
        to_sell = []
        for ticker, pos in positions.items():
            df = price_dfs.get(ticker)
            if df is None or today not in df.index:
                continue
            current_price = float(df.loc[today, "Close"])
            if current_price <= 0:
                continue

            pos["highest"] = max(pos["highest"], current_price)
            pnl = (current_price - pos["buy_price"]) / pos["buy_price"]
            drawdown = (pos["highest"] - current_price) / pos["highest"]

            exit_reason = None
            if pnl <= -stop_loss_pct:
                exit_reason = "停損"
            elif pnl > 0.05 and drawdown >= trailing_stop_pct:
                # 追蹤停損：只在已有 5%+ 利潤時才啟動，保護獲利但不截斷上升趨勢
                exit_reason = "追蹤停損"
            elif use_smc_filter and smc_exit_on_downtrend:
                smc_now = _calc_smc_trend(df, today)
                if smc_now == "下降趨勢" and pnl > -stop_loss_pct * 0.5:
                    exit_reason = "SMC趨勢反轉"

            if exit_reason:
                proceeds = current_price * pos["shares"]
                capital += proceeds
                trades.append({
                    "ticker": ticker,
                    "buy_date": pos["buy_date"].isoformat(),
                    "buy_price": pos["buy_price"],
                    "sell_date": today.isoformat(),
                    "sell_price": current_price,
                    "pnl_pct": round(pnl * 100, 2),
                    "exit_reason": exit_reason,
                })
                to_sell.append(ticker)

        for t in to_sell:
            del positions[t]

        # ── 買入檢查 ──────────────────────────────────────────────────
        if len(positions) < max_positions:
            candidates = []
            for ticker, df in price_dfs.items():
                if ticker in positions:
                    continue
                if today not in df.index:
                    continue
                score = _calc_technical_score(df, today)
                if score is None or score < buy_threshold:
                    continue

                # SMC 過濾：下降趨勢不買入
                if use_smc_filter:
                    smc_trend = _calc_smc_trend(df, today)
                    if smc_trend == "下降趨勢":
                        continue
                    adj_score = _adjusted_score(score, smc_trend)
                else:
                    adj_score = score

                candidates.append((ticker, adj_score, float(df.loc[today, "Close"])))

            # 依調整後評分降序，買入前幾名
            candidates.sort(key=lambda x: -x[1])
            slots = max_positions - len(positions)
            for ticker, adj_score, price in candidates[:slots]:
                if price <= 0:
                    continue
                # 用總資產（現金+持倉市值）計算倉位，避免現金拖累
                total_equity = capital + sum(
                    float(price_dfs[t_].loc[today, "Close"]) * pos_["shares"]
                    for t_, pos_ in positions.items()
                    if t_ in price_dfs and today in price_dfs[t_].index
                )
                invest = min(total_equity * position_size_pct, capital)
                if invest <= 0:
                    continue
                shares = invest / price
                capital -= invest
                positions[ticker] = {
                    "buy_price": price,
                    "shares": shares,
                    "highest": price,
                    "buy_date": today,
                }

        # ── 計算今日總資產 ─────────────────────────────────────────────
        holdings_value = sum(
            float(price_dfs[t].loc[today, "Close"]) * pos["shares"]
            for t, pos in positions.items()
            if t in price_dfs and today in price_dfs[t].index
        )
        equity_curve.append({"date": today.isoformat(), "equity": round(capital + holdings_value, 2)})

        if progress_cb and idx % 20 == 0:
            await progress_cb(
                f"回測進度 {idx+1}/{len(trading_dates)} 日",
                phase="backtesting", current=idx + 1, total=len(trading_dates)
            )

    # 強制在最後交易日平倉
    last_day = trading_dates[-1]
    for ticker, pos in positions.items():
        df = price_dfs.get(ticker)
        if df is None:
            continue
        last_available = df[df.index <= last_day].index[-1] if any(df.index <= last_day) else None
        if last_available is None:
            continue
        current_price = float(df.loc[last_available, "Close"])
        pnl = (current_price - pos["buy_price"]) / pos["buy_price"]
        trades.append({
            "ticker": ticker,
            "buy_date": pos["buy_date"].isoformat(),
            "buy_price": pos["buy_price"],
            "sell_date": last_day.isoformat(),
            "sell_price": current_price,
            "pnl_pct": round(pnl * 100, 2),
            "exit_reason": "回測結束",
        })
        capital += current_price * pos["shares"]

    if equity_curve:
        equity_curve[-1]["equity"] = round(capital, 2)

    metrics = _calc_metrics(trades, equity_curve, initial_capital)
    config = {
        "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        "buy_threshold": buy_threshold, "stop_loss_pct": stop_loss_pct,
        "trailing_stop_pct": trailing_stop_pct,
        "initial_capital": initial_capital, "position_size_pct": position_size_pct,
        "max_positions": max_positions,
        "use_smc_filter": use_smc_filter,
        "smc_exit_on_downtrend": smc_exit_on_downtrend,
    }

    if progress_cb:
        await progress_cb("回測完成！", phase="done", current=100, total=100)

    logger.info(f"回測完成: {metrics}")
    return {"config": config, "metrics": metrics, "trades": trades, "equity_curve": equity_curve}


async def optimize_weights(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    progress_cb=None,
) -> list[dict]:
    """
    網格搜索最佳化策略參數
    測試不同 buy_threshold 組合，找出最高 Sharpe ratio 的設定
    """
    thresholds = [50.0, 55.0, 60.0, 65.0, 70.0]
    stop_losses = [0.05, 0.07, 0.10]
    results = []
    total = len(thresholds) * len(stop_losses)
    done = 0

    for threshold in thresholds:
        for sl in stop_losses:
            if progress_cb:
                await progress_cb(
                    f"最佳化測試 threshold={threshold} stop_loss={sl*100:.0f}%",
                    phase="optimizing", current=done, total=total
                )
            bt = await run_backtest(
                db, start_date, end_date,
                buy_threshold=threshold,
                stop_loss_pct=sl,
                use_smc_filter=True,
                smc_exit_on_downtrend=True,
            )
            if "error" not in bt:
                results.append({
                    "threshold": threshold, "stop_loss_pct": sl,
                    **bt["metrics"]
                })
            done += 1

    results.sort(key=lambda x: x.get("sharpe_ratio", -99), reverse=True)
    return results
