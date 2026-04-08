from __future__ import annotations
"""
推薦引擎 Service（分層決策版 v2）

架構：
  Layer 1: SMC 結構（方向門檻）→ 通過 / 排除 / 觀望
  Layer 2: 動量確認（technical.py）→ 動量分 0-100
  Layer 3: 催化劑確認（新聞情緒）→ 加速 / 中性 / 警告
  → 條件計數決定推薦等級 + 倉位大小
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
from .smc_v1 import find_structure, run_smc_analysis, run_mtf_smc_analysis, compute_smc_entry

logger = logging.getLogger(__name__)

# ── 倉位等級定義 ─────────────────────────────────────────────
POSITION_TIERS = {
    "核心持倉": {"pct": "15-20%", "desc": "高信心，結構+動量+催化劑全到位"},
    "標準倉位": {"pct": "8-12%",  "desc": "中等信心，主要條件滿足"},
    "探索倉位": {"pct": "3-5%",   "desc": "低信心或觀望，先小量試探"},
}


def _compute_composite(
    signals_met: int,
    rr: float | None,
    current_price: float | None,
    stop_price: float | None,
    target_price: float | None,
) -> float:
    """
    新版綜合分（v3）— 直接反映交易品質

    綜合分 = 條件分(0~50) + 風報比分(0~30) + 位置分(0~20) = 0~100

    條件分: 每滿足一個條件 +10 分（SMC/動量/催化劑/R:R/MTF）
    風報比分: R:R 越高分越高，< 1.0 = 0 分
    位置分: 現價離目標越近（已沒肉）或離停損越近（很危險）= 低分
    """
    # 1. 條件分 (0-50)
    condition_score = max(0, min(5, signals_met)) * 10

    # 2. 風報比分 (0-30)
    if rr is None or rr <= 0:
        rr_score = 0
    elif rr >= 4.0:
        rr_score = 30
    elif rr >= 3.0:
        rr_score = 25
    elif rr >= 2.0:
        rr_score = 20
    elif rr >= 1.5:
        rr_score = 12
    elif rr >= 1.0:
        rr_score = 5
    else:
        rr_score = 0

    # 3. 位置分 (0-20): 現價在停損~目標之間的位置
    #    越接近停損 = 越危險 = 低分
    #    越多上升空間 = 高分
    position_score = 10  # 預設（缺少資料時給中間值）
    if current_price and stop_price and target_price and target_price > stop_price:
        upside = target_price - current_price   # 剩餘上升空間
        downside = current_price - stop_price   # 離停損距離
        total_range = target_price - stop_price

        if downside <= 0:
            position_score = 0   # 已跌破停損！
        elif upside <= 0:
            position_score = 3   # 已超過目標，沒什麼肉了
        else:
            # 上升空間佔總範圍的比例 × 20
            position_score = round((upside / total_range) * 20)
            position_score = max(0, min(20, position_score))

    composite = condition_score + rr_score + position_score
    return float(max(0, min(100, composite)))


def _layered_decision(
    smc_trend: str,
    momentum_score: float,
    catalyst: str,       # "加速" / "中性" / "警告"
    rr: float | None,    # 風報比
    mtf: dict | None = None,  # MTF 對齊結果
    current_price: float | None = None,
    stop_price: float | None = None,
    target_price: float | None = None,
) -> dict:
    """
    分層決策引擎（v3）+ 多時間框架確認

    綜合分 = 條件分(0~50) + 風報比分(0~30) + 位置分(0~20)
    推薦等級 = 由條件計數決定

    Returns:
        {
            "recommendation": str,
            "position_tier": str | None,
            "composite_score": float,
            "signals_met": int,
            "reason": str,
        }
    """
    mtf = mtf or {}
    mtf_tradable = mtf.get("tradable", True)
    mtf_score_adj = mtf.get("score_adj", 0)
    mtf_alignment = mtf.get("alignment", "")
    mtf_confidence = mtf.get("confidence", "低")

    # ── Layer 0: MTF 門檻（高時間框架否決權）──────────────
    if not mtf_tradable and mtf_alignment in ("三重下降", "逆勢反彈"):
        composite = _compute_composite(0, rr, current_price, stop_price, target_price)
        return {
            "recommendation": "不推薦",
            "position_tier": None,
            "composite_score": composite,
            "signals_met": 0,
            "reason": f"MTF {mtf_alignment}，高時間框架不支持做多",
        }

    # ── Layer 1: SMC 日線門檻 ─────────────────────────────
    if smc_trend == "下降趨勢":
        if mtf_tradable and mtf_score_adj > 0:
            composite = _compute_composite(1, rr, current_price, stop_price, target_price)
            return {
                "recommendation": "觀察",
                "position_tier": "探索倉位",
                "composite_score": composite,
                "signals_met": 1,
                "reason": f"日線下降但{mtf_alignment}，等日線止穩",
            }
        composite = _compute_composite(0, rr, current_price, stop_price, target_price)
        return {
            "recommendation": "不推薦",
            "position_tier": None,
            "composite_score": composite,
            "signals_met": 0,
            "reason": "SMC 下降結構，不做多",
        }

    # ── 條件計數 ──────────────────────────────────────────
    signals_met = 0
    reasons = []

    # 條件 1: SMC 結構方向
    if smc_trend == "上升趨勢":
        signals_met += 1
        reasons.append("SMC 上升結構")
    # 盤整不加分也不排除

    # 條件 2: 動量分
    if momentum_score >= 70:
        signals_met += 1
        reasons.append(f"動量強勁 ({momentum_score:.0f})")
    elif momentum_score >= 60:
        signals_met += 1
        reasons.append(f"動量健康 ({momentum_score:.0f})")

    # 條件 3: 催化劑
    if catalyst == "加速":
        signals_met += 1
        reasons.append("有正面催化劑")
    elif catalyst == "警告":
        signals_met -= 1  # 扣分
        reasons.append("有負面催化劑")

    # 條件 4: 風報比
    if rr is not None and rr >= 2.0:
        signals_met += 1
        reasons.append(f"風報比優秀 ({rr}x)")
    elif rr is not None and rr >= 1.5:
        # 可接受但不加分
        pass

    # 條件 5: MTF 對齊
    if mtf_confidence == "高" and mtf_score_adj > 0:
        signals_met += 1
        reasons.append(f"MTF {mtf_alignment}")
    elif not mtf_tradable:
        signals_met -= 1
        reasons.append(f"MTF 警告：{mtf_alignment}")

    # ── 綜合分（新公式 v3）────────────────────────────────
    composite = _compute_composite(signals_met, rr, current_price, stop_price, target_price)

    # ── 推薦等級 + 倉位（由條件計數決定）─────────────────
    if signals_met >= 5:
        rec = "強力推薦"
        tier = "核心持倉"
    elif signals_met >= 4:
        rec = "強力推薦"
        tier = "核心持倉"
    elif signals_met >= 3:
        rec = "推薦"
        tier = "標準倉位"
    elif signals_met >= 2:
        rec = "觀察"
        tier = "探索倉位"
    else:
        rec = "不推薦"
        tier = None

    # 盤整中即使條件夠多，最高只到「標準倉位」
    if smc_trend == "盤整" and tier == "核心持倉":
        tier = "標準倉位"

    # MTF 不可交易時，最高只到「探索倉位」
    if not mtf_tradable and tier in ("核心持倉", "標準倉位"):
        tier = "探索倉位"
        rec = "觀察"

    return {
        "recommendation": rec,
        "position_tier": tier,
        "composite_score": composite,
        "signals_met": signals_met,
        "reason": " + ".join(reasons) if reasons else "條件不足",
    }


def _catalyst_level(sentiment: dict) -> str:
    """將情緒分析結果轉換為催化劑等級"""
    score = sentiment.get("score", 50)
    count = sentiment.get("article_count", 0)

    if count == 0:
        return "中性"    # 沒有新聞 = 不加不減
    if score >= 65:
        return "加速"    # 正面催化劑
    if score <= 35:
        return "警告"    # 負面催化劑
    return "中性"


async def run_analysis_for_stock(
    db: AsyncSession,
    stock: Stock,
    analysis_date: date | None = None,
) -> dict | None:
    """
    對單一股票執行分層分析並寫入 DB
    """
    if analysis_date is None:
        analysis_date = date.today()

    # ── Layer 2: 動量分析（technical.py） ─────────────────
    tech = await analyze_stock(db, stock.id)
    if tech is None:
        logger.warning(f"{stock.ticker} 技術分析失敗（資料不足）")
        return None

    # ── Layer 3: 催化劑（新聞情緒） ──────────────────────
    news_result = await db.execute(
        select(NewsArticle.sentiment_score)
        .where(NewsArticle.stock_id == stock.id)
        .order_by(NewsArticle.published_at.desc())
        .limit(10)
    )
    sentiment_scores = [float(s) for s in news_result.scalars().all() if s is not None]
    sentiment = aggregate_sentiment(sentiment_scores)
    catalyst = _catalyst_level(sentiment)

    # ── Layer 1: SMC 結構分析（門檻）+ MTF 多時間框架 ────
    smc_trend = "未知"
    smc_entry: dict | None = None
    mtf_info: dict | None = None
    weekly_trend = "未知"
    monthly_trend = "未知"
    try:
        # 載入更多資料供週線/月線分析（最多 5 年）
        df = await load_price_df(db, stock.id, limit=1260)  # ~5 年交易日
        if df is not None and len(df) >= 30:
            mtf_result = run_mtf_smc_analysis(df)
            smc_trend = mtf_result["daily"].get("structure", {}).get("trend", "未知")
            smc_entry = mtf_result["daily"].get("entry_suggestion")
            weekly_trend = mtf_result["weekly"].get("trend", "未知")
            monthly_trend = mtf_result["monthly"].get("trend", "未知")
            mtf_info = mtf_result.get("mtf")
    except Exception as e:
        logger.warning(f"{stock.ticker} SMC/MTF 分析失敗: {e}")

    # ── 分層決策 ──────────────────────────────────────────
    rr = smc_entry.get("rr") if smc_entry else None
    entry_price = smc_entry.get("entry") if smc_entry else None
    stop_price = smc_entry.get("stop") if smc_entry else None
    target_price = smc_entry.get("target") if smc_entry else None
    current_price = tech["indicators"].get("price")
    decision = _layered_decision(
        smc_trend, tech["score"], catalyst, rr, mtf=mtf_info,
        current_price=current_price, stop_price=stop_price, target_price=target_price,
    )

    recommendation = decision["recommendation"]
    composite = decision["composite_score"]
    position_tier = decision["position_tier"]

    # 把分層結果加入訊號說明
    tech["signals"].append(f"SMC: {smc_trend}")
    if weekly_trend != "未知" or monthly_trend != "未知":
        tech["signals"].append(f"MTF: 日{smc_trend} / 週{weekly_trend} / 月{monthly_trend}")
    if mtf_info:
        tech["signals"].append(f"MTF 對齊: {mtf_info['alignment']}（{mtf_info['confidence']}信心）")
    tech["signals"].append(f"催化劑: {catalyst}")
    if position_tier:
        tech["signals"].append(f"倉位建議: {position_tier}")
    tech["signals"].append(f"分層決策: {decision['reason']}")

    ind = tech["indicators"]

    # 把 position_tier 加入 entry_suggestion
    if smc_entry and position_tier:
        smc_entry["position_tier"] = position_tier
    elif smc_entry:
        smc_entry["position_tier"] = None

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
        entry_suggestion=smc_entry,
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
            "entry_suggestion": smc_entry,
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
        "position_tier": position_tier,
        "smc_trend": smc_trend,
        "weekly_trend": weekly_trend,
        "monthly_trend": monthly_trend,
        "mtf_alignment": mtf_info.get("alignment") if mtf_info else None,
        "mtf_confidence": mtf_info.get("confidence") if mtf_info else None,
        "catalyst": catalyst,
        "signals_met": decision["signals_met"],
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
