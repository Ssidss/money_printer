from __future__ import annotations
"""
開盤簡報 API
整合持倉健檢 + 推薦標的 + AI 筆記，產出一頁式的開盤前觀察清單
"""
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.stock import Stock, PriceHistory
from ..models.analysis import AnalysisResult
from ..models.portfolio import PortfolioHolding
from ..models.ai_note import AiAnalysisNote
from ..services.technical import load_price_df
from ..services.smc_v1 import find_structure, resample_to_weekly, resample_to_monthly, mtf_alignment
from .analysis import _get_entry

router = APIRouter(prefix="/briefing", tags=["briefing"])


@router.get("/next-open")
async def next_open_briefing(db: AsyncSession = Depends(get_db)):
    """
    下次開盤前簡報：
    1. 持倉健檢（每支持倉的損益、SMC 趨勢、是否觸發停損）
    2. 推薦觀察（綜合分 Top N 且上升/盤整的股票）
    3. 每支股票最新 AI 筆記摘要
    """
    # ── 1. 取得最新分析日期 ──────────────────────────────
    latest_date_r = await db.execute(select(func.max(AnalysisResult.analysis_date)))
    latest_date = latest_date_r.scalar_one_or_none()

    # ── 2. 取得所有持倉 ──────────────────────────────────
    holdings_r = await db.execute(
        select(PortfolioHolding, Stock.ticker, Stock.market, Stock.name)
        .join(Stock)
    )
    holdings_raw = holdings_r.all()

    portfolio_items = []
    for h, ticker, market, name in holdings_raw:
        # 取最新分析
        ar = (await db.execute(
            select(AnalysisResult)
            .where(AnalysisResult.stock_id == h.stock_id)
            .order_by(AnalysisResult.analysis_date.desc())
            .limit(1)
        )).scalar_one_or_none()

        # 取 SMC 趨勢（含 MTF）
        df = await load_price_df(db, h.stock_id, limit=1260)
        smc_trend = "未知"
        weekly_trend = "未知"
        monthly_trend = "未知"
        mtf_info = None
        current_price = None
        if df is not None and len(df) >= 30:
            try:
                smc_trend = find_structure(df).get("trend", "未知")
                current_price = round(float(df["Close"].iloc[-1]), 2)
                df_w = resample_to_weekly(df)
                if len(df_w) >= 20:
                    weekly_trend = find_structure(df_w).get("trend", "未知")
                df_m = resample_to_monthly(df)
                if len(df_m) >= 12:
                    monthly_trend = find_structure(df_m).get("trend", "未知")
                mtf_info = mtf_alignment(smc_trend, weekly_trend, monthly_trend)
            except Exception:
                pass

        avg_cost = float(h.avg_cost)
        stop_loss = round(avg_cost * 0.93, 2)   # 7% stop loss
        take_profit = round(avg_cost * 1.15, 2)  # 15% take profit
        pnl_pct = round((current_price - avg_cost) / avg_cost * 100, 2) if current_price else None

        # 判斷警報等級
        alert = None
        if smc_trend == "下降趨勢":
            alert = "trend_down"
        if stop_loss and current_price and current_price <= stop_loss:
            alert = "stop_hit"
        elif stop_loss and current_price and current_price <= stop_loss * 1.03:
            alert = "near_stop"

        # 最新 AI 筆記
        ai_r = await db.execute(
            select(AiAnalysisNote)
            .where(AiAnalysisNote.stock_id == h.stock_id)
            .order_by(AiAnalysisNote.created_at.desc())
            .limit(1)
        )
        ai_note = ai_r.scalar_one_or_none()

        portfolio_items.append({
            "ticker": ticker,
            "market": market,
            "name": name,
            "shares": float(h.total_shares),
            "avg_cost": avg_cost,
            "current_price": current_price,
            "pnl_pct": pnl_pct,
            "stop_loss": stop_loss,
            "smc_trend": smc_trend,
            "weekly_trend": weekly_trend,
            "monthly_trend": monthly_trend,
            "mtf_alignment": mtf_info.get("alignment") if mtf_info else None,
            "mtf_tradable": mtf_info.get("tradable") if mtf_info else None,
            "alert": alert,
            "composite_score": float(ar.composite_score) if ar and ar.composite_score else None,
            "recommendation": ar.recommendation if ar else None,
            "ai_action": ai_note.action if ai_note else None,
            "ai_summary_preview": (ai_note.summary[:120] + "...") if ai_note and len(ai_note.summary) > 120 else (ai_note.summary if ai_note else None),
            "ai_note_id": ai_note.id if ai_note else None,
            "ai_note_at": ai_note.created_at.isoformat() if ai_note else None,
        })

    # 排序：alert 優先（stop_hit > near_stop > trend_down > None）
    alert_order = {"stop_hit": 0, "near_stop": 1, "trend_down": 2, None: 3}
    portfolio_items.sort(key=lambda x: alert_order.get(x["alert"], 3))

    # ── 3. 推薦觀察清單（非持倉、且推薦 ≥ 觀察） ───────
    holding_tickers = {ticker for _, ticker, _, _ in holdings_raw}

    if latest_date:
        watch_r = await db.execute(
            select(AnalysisResult, Stock.ticker, Stock.market, Stock.name)
            .join(Stock)
            .where(
                AnalysisResult.analysis_date == latest_date,
                Stock.is_active == True,
                Stock.market == "US",
                AnalysisResult.recommendation.in_(["強力推薦", "推薦", "觀察"]),
            )
            .order_by(AnalysisResult.composite_score.desc())
            .limit(10)
        )
        watch_rows = watch_r.all()
    else:
        watch_rows = []

    watchlist = []
    for ar, ticker, market, name in watch_rows:
        if ticker in holding_tickers:
            continue
        # AI 筆記
        ai_r = await db.execute(
            select(AiAnalysisNote)
            .where(AiAnalysisNote.stock_id == ar.stock_id)
            .order_by(AiAnalysisNote.created_at.desc())
            .limit(1)
        )
        ai_note = ai_r.scalar_one_or_none()

        entry = _get_entry(ar)
        close = float(ar.close_price) if ar.close_price else None
        distance_pct = round((close - entry["entry"]) / entry["entry"] * 100, 1) if entry and close and entry.get("entry") else None

        watchlist.append({
            "ticker": ticker,
            "market": market,
            "name": name,
            "composite_score": float(ar.composite_score) if ar.composite_score else None,
            "recommendation": ar.recommendation,
            "rsi": float(ar.rsi) if ar.rsi else None,
            "current_price": close,
            "entry_suggestion": entry,
            "distance_pct": distance_pct,
            "signals": ar.signals or [],
            "ai_action": ai_note.action if ai_note else None,
            "ai_summary_preview": (ai_note.summary[:120] + "...") if ai_note and len(ai_note.summary) > 120 else (ai_note.summary if ai_note else None),
            "ai_note_id": ai_note.id if ai_note else None,
            "ai_note_at": ai_note.created_at.isoformat() if ai_note else None,
        })

    # ── 4. 大盤指標 ──────────────────────────────────────
    market_indices = {}
    for idx_ticker in ["SPY", "QQQ", "SOXX"]:
        idx_r = await db.execute(select(Stock).where(Stock.ticker == idx_ticker))
        idx_stock = idx_r.scalar_one_or_none()
        if idx_stock:
            df = await load_price_df(db, idx_stock.id, limit=60)
            if df is not None and len(df) >= 30:
                try:
                    trend = find_structure(df).get("trend", "未知")
                    close = round(float(df["Close"].iloc[-1]), 2)
                    prev = round(float(df["Close"].iloc[-2]), 2) if len(df) >= 2 else close
                    chg = round((close - prev) / prev * 100, 2)
                    market_indices[idx_ticker] = {"price": close, "change_pct": chg, "trend": trend}
                except Exception:
                    pass

    return {
        "analysis_date": latest_date.isoformat() if latest_date else None,
        "market_indices": market_indices,
        "portfolio": portfolio_items,
        "watchlist": watchlist,
        "portfolio_alerts": sum(1 for p in portfolio_items if p["alert"]),
    }
