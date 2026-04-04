from __future__ import annotations
"""
推薦引擎 Service
整合技術分析 + 情緒分析 → 評分排名 → 寫入 analysis_results
"""

import logging
from datetime import date, datetime

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.stock import Stock
from ..models.analysis import AnalysisResult, NewsArticle
from .technical import analyze_stock, load_price_df
from .sentiment import aggregate_sentiment
from .smc import find_structure

# SMC 趨勢對綜合分的乘數
# 下降趨勢：逆勢做多勝率低，重扣並封頂"觀察"
# 盤整：方向未明，輕扣
# 上升趨勢：順勢，小幅加分
SMC_SCORE_MULTIPLIER: dict[str, float] = {
    "上升趨勢": 1.10,
    "盤整":     0.90,
    "下降趨勢": 0.70,
    "未知":     0.95,
}

# 下降趨勢時推薦等級上限（不管分數多高都不能推薦）
SMC_DOWNTREND_CAP = "觀察"

logger = logging.getLogger(__name__)


async def run_analysis_for_stock(
    db: AsyncSession,
    stock: Stock,
    analysis_date: date | None = None,
) -> dict | None:
    """
    對單一股票執行分析並寫入 DB

    Returns:
        分析結果 dict，失敗回傳 None
    """
    if analysis_date is None:
        analysis_date = date.today()

    # 技術分析
    tech = await analyze_stock(db, stock.id)
    if tech is None:
        logger.warning(f"{stock.ticker} 技術分析失敗（資料不足）")
        return None

    # 情緒分析（從 DB 取最近新聞）
    news_result = await db.execute(
        select(NewsArticle.sentiment_score)
        .where(NewsArticle.stock_id == stock.id)
        .order_by(NewsArticle.published_at.desc())
        .limit(10)
    )
    sentiment_scores = [float(s) for s in news_result.scalars().all() if s is not None]
    sentiment = aggregate_sentiment(sentiment_scores)

    # SMC 市場結構分析（輕量版：只算趨勢，不跑完整 SMC）
    smc_trend = "未知"
    try:
        df = await load_price_df(db, stock.id, limit=60)
        if df is not None:
            struct = find_structure(df)
            smc_trend = struct.get("trend", "未知")
    except Exception as e:
        logger.warning(f"{stock.ticker} SMC 趨勢計算失敗: {e}")

    # 綜合評分（技術 + 情緒，再套 SMC 趨勢乘數）
    w_tech = settings.WEIGHT_TECHNICAL
    w_sent = settings.WEIGHT_SENTIMENT
    base_composite = tech["score"] * w_tech + sentiment["score"] * w_sent
    smc_mult = SMC_SCORE_MULTIPLIER.get(smc_trend, 1.0)
    composite = min(base_composite * smc_mult, 100.0)  # 不超過100

    # 推薦等級
    if composite >= 75:   recommendation = "強力推薦"
    elif composite >= 65: recommendation = "推薦"
    elif composite >= 55: recommendation = "觀察"
    else:                 recommendation = "不推薦"

    # 下降趨勢：推薦等級封頂（無論分數多高都不能是「推薦」以上）
    if smc_trend == "下降趨勢" and recommendation in ("強力推薦", "推薦"):
        recommendation = SMC_DOWNTREND_CAP

    # 把 SMC 趨勢加入訊號說明
    smc_signal_text = {
        "上升趨勢": f"SMC 上升趨勢 ✅（順勢加分 ×{SMC_SCORE_MULTIPLIER['上升趨勢']}）",
        "下降趨勢": f"SMC 下降趨勢 ⚠️（逆勢重扣 ×{SMC_SCORE_MULTIPLIER['下降趨勢']}，推薦封頂「觀察」）",
        "盤整":     f"SMC 盤整中 〰️（方向不明扣分 ×{SMC_SCORE_MULTIPLIER['盤整']}）",
        "未知":     "SMC 趨勢未知（資料不足）",
    }.get(smc_trend, "")
    if smc_signal_text:
        tech["signals"].append(smc_signal_text)

    ind = tech["indicators"]

    # Upsert analysis_results
    stmt = insert(AnalysisResult).values(
        stock_id=stock.id,
        analysis_date=analysis_date,
        composite_score=round(composite, 2),
        technical_score=round(tech["score"], 2),
        sentiment_score=round(sentiment["score"], 2),
        recommendation=recommendation,
        rsi=ind.get("rsi"),
        macd=ind.get("macd"),
        macd_signal=ind.get("macd_signal"),
        ma5=ind.get("ma5"),
        ma20=ind.get("ma20"),
        ma60=ind.get("ma60"),
        bb_upper=ind.get("bb_upper"),
        bb_lower=ind.get("bb_lower"),
        volume_ratio=ind.get("volume_ratio"),
        close_price=ind.get("price"),
        signals=tech["signals"],
        news_summary=sentiment,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_id", "analysis_date"],
        set_={
            "composite_score": round(composite, 2),
            "technical_score": round(tech["score"], 2),
            "sentiment_score": round(sentiment["score"], 2),
            "recommendation": recommendation,
            "rsi": ind.get("rsi"),
            "macd": ind.get("macd"),
            "macd_signal": ind.get("macd_signal"),
            "close_price": ind.get("price"),
            "signals": tech["signals"],
            "news_summary": sentiment,
        }
    )
    await db.execute(stmt)
    await db.commit()

    return {
        "ticker": stock.ticker,
        "market": stock.market,
        "composite_score": round(composite, 2),
        "technical_score": round(tech["score"], 2),
        "sentiment_score": round(sentiment["score"], 2),
        "recommendation": recommendation,
        "smc_trend": smc_trend,
        "indicators": ind,
        "signals": tech["signals"],
        "news_sentiment": sentiment,
    }


async def run_full_analysis(
    db: AsyncSession,
    progress_cb=None,
) -> dict:
    """
    對所有 active 股票執行分析，回傳完整結果包含 top_picks
    """
    result = await db.execute(select(Stock).where(Stock.is_active == True))
    stocks = result.scalars().all()

    total = len(stocks)
    all_results = []

    for i, stock in enumerate(stocks, 1):
        if progress_cb:
            await progress_cb(
                f"分析 {stock.ticker}...",
                phase="analyzing",
                current=i,
                total=total,
                ticker=stock.ticker,
            )

        res = await run_analysis_for_stock(db, stock)
        if res:
            all_results.append(res)

    all_results.sort(key=lambda x: x["composite_score"], reverse=True)
    top_picks = all_results[:settings.DAILY_RECOMMEND_COUNT]

    summary = {
        "total_analyzed": len(all_results),
        "date": date.today().isoformat(),
        "avg_technical": round(sum(r["technical_score"] for r in all_results) / max(len(all_results), 1), 1),
        "avg_sentiment": round(sum(r["sentiment_score"] for r in all_results) / max(len(all_results), 1), 1),
    }

    logger.info(f"分析完成：{len(all_results)} 支股票，Top 1: {top_picks[0]['ticker'] if top_picks else 'N/A'}")
    return {"top_picks": top_picks, "all_results": all_results, "summary": summary}
