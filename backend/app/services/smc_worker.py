"""
SMC v2 Worker — 分析 pipeline

職責：
  1. 從 DB 讀 PriceHistory → DataFrame
  2. 跑 run_smc_analysis_v2()（日/週/月）
  3. 跑 generate_entry_plan()
  4. 寫回 AnalysisResult（smc_data, entry_plan JSONB）

原則（ENGINEERING.md §廿一）：API 不跑分析，API 只讀結果。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.stock import Stock, PriceHistory
from ..models.analysis import AnalysisResult, NewsArticle
from ..schemas.smc import SmcResult, TrendDirection
from ..services.smc import run_smc_analysis_v2
from ..services.decision.entry import generate_entry_plan

logger = logging.getLogger(__name__)


async def _load_price_df(
    db: AsyncSession,
    stock_id: int,
    days: int = 730,
) -> pd.DataFrame:
    """從 DB 載入 PriceHistory 並轉成 OHLCV DataFrame。"""
    cutoff = date.today() - timedelta(days=days)
    rows = (await db.execute(
        select(PriceHistory)
        .where(PriceHistory.stock_id == stock_id, PriceHistory.date >= cutoff)
        .order_by(PriceHistory.date)
    )).scalars().all()

    if not rows:
        return pd.DataFrame()

    data = {
        "Open": [float(r.open) if r.open else None for r in rows],
        "High": [float(r.high) if r.high else None for r in rows],
        "Low": [float(r.low) if r.low else None for r in rows],
        "Close": [float(r.close) if r.close else None for r in rows],
        "Volume": [int(r.volume) if r.volume else 0 for r in rows],
    }
    df = pd.DataFrame(data, index=pd.to_datetime([r.date for r in rows]))
    df = df.dropna(subset=["Close"])
    return df


async def _load_sentiment(db: AsyncSession, stock_id: int) -> float | None:
    """從最近 10 篇新聞的 sentiment_score 取平均（0-100），無新聞回傳 None。"""
    rows = (await db.execute(
        select(NewsArticle.sentiment_score)
        .where(NewsArticle.stock_id == stock_id)
        .order_by(NewsArticle.published_at.desc())
        .limit(10)
    )).scalars().all()
    scores = [float(s) for s in rows if s is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


async def run_smc_for_ticker(
    db: AsyncSession,
    ticker: str,
    market: str,
    *,
    sentiment_score: float | None = None,
    progress_cb=None,
) -> dict | None:
    """
    對單一股票跑完整 SMC v2 分析 + 決策，寫入 DB。

    回傳 {"smc": SmcResult, "entry_plan": EntryPlan} 或 None（失敗時）。
    """
    # 1. 找到 stock
    result = await db.execute(
        select(Stock).where(Stock.ticker == ticker, Stock.is_active == True)
    )
    stock = result.scalar_one_or_none()
    if not stock:
        logger.warning(f"[SMC] {ticker} 不在追蹤清單中")
        return None

    if progress_cb:
        await progress_cb(f"分析 {ticker} SMC...", phase="smc_analysis", ticker=ticker)

    # 2. 載入價格 + 情緒
    df = await _load_price_df(db, stock.id)
    if df.empty or len(df) < 20:
        logger.warning(f"[SMC] {ticker} 價格數據不足 ({len(df)} bars)")
        return None

    if sentiment_score is None:
        sentiment_score = await _load_sentiment(db, stock.id)

    # 3. 跑日線 SMC
    smc_daily = run_smc_analysis_v2(ticker, df, "daily", market)

    # 4. 跑週線/月線（MTF 用）
    weekly_trend = TrendDirection.INSUFFICIENT
    monthly_trend = TrendDirection.INSUFFICIENT

    if len(df) >= 60:
        smc_weekly = run_smc_analysis_v2(ticker, df, "weekly", market)
        weekly_trend = smc_weekly.structure.trend

    if len(df) >= 200:
        smc_monthly = run_smc_analysis_v2(ticker, df, "monthly", market)
        monthly_trend = smc_monthly.structure.trend

    # 5. 生成進場計畫
    current_price = float(df["Close"].iloc[-1])
    closes = df["Close"].values.tolist()
    highs = df["High"].values.tolist()
    lows = df["Low"].values.tolist()

    entry_plan = generate_entry_plan(
        smc_daily,
        current_price,
        closes=closes,
        highs=highs,
        lows=lows,
        sentiment_score=sentiment_score,
        monthly_trend=monthly_trend,
        weekly_trend=weekly_trend,
    )

    # 6. 寫入 DB
    today = date.today()
    existing = (await db.execute(
        select(AnalysisResult).where(
            AnalysisResult.stock_id == stock.id,
            AnalysisResult.analysis_date == today,
        )
    )).scalar_one_or_none()

    smc_dict = smc_daily.model_dump(mode="json")
    entry_dict = entry_plan.model_dump(mode="json")

    if existing:
        existing.smc_data = smc_dict
        existing.smc_version = 2
        existing.entry_plan = entry_dict
        existing.regime = smc_daily.regime.regime.value if smc_daily.regime.regime else None
        existing.smc_computed_at = datetime.now(timezone.utc)
        existing.close_price = current_price
        existing.recommendation = entry_plan.recommendation
    else:
        new_row = AnalysisResult(
            stock_id=stock.id,
            analysis_date=today,
            smc_data=smc_dict,
            smc_version=2,
            entry_plan=entry_dict,
            regime=smc_daily.regime.regime.value if smc_daily.regime.regime else None,
            smc_computed_at=datetime.now(timezone.utc),
            close_price=current_price,
            recommendation=entry_plan.recommendation,
        )
        db.add(new_row)

    await db.commit()

    logger.info(
        f"[SMC] {ticker}: {smc_daily.structure.trend.value} | "
        f"{entry_plan.recommendation} | R:R={entry_plan.rr_ratio}"
    )

    return {"smc": smc_daily, "entry_plan": entry_plan}


async def run_smc_batch(
    db: AsyncSession,
    *,
    progress_cb=None,
) -> dict:
    """
    批次跑所有 active 股票的 SMC 分析。

    回傳 {"completed": int, "failed": int, "results": {ticker: {...}}}
    """
    stocks = (await db.execute(
        select(Stock).where(Stock.is_active == True)
    )).scalars().all()

    completed = 0
    failed = 0
    results = {}
    total = len(stocks)

    for i, stock in enumerate(stocks, 1):
        if progress_cb:
            await progress_cb(
                f"SMC 分析 {stock.ticker} ({i}/{total})",
                phase="smc_batch",
                current=i, total=total, ticker=stock.ticker,
            )
        try:
            result = await run_smc_for_ticker(db, stock.ticker, stock.market)
            if result:
                results[stock.ticker] = {
                    "trend": result["smc"].structure.trend.value,
                    "recommendation": result["entry_plan"].recommendation,
                    "action": result["entry_plan"].action,
                    "rr_ratio": result["entry_plan"].rr_ratio,
                    "entry_price": result["entry_plan"].entry_price,
                }
                completed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"[SMC] {stock.ticker} 分析失敗: {e}")
            await db.rollback()
            failed += 1

    return {"completed": completed, "failed": failed, "total": total, "results": results}
