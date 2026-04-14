from __future__ import annotations
"""
開盤簡報 API
整合持倉健檢 + 推薦標的 + AI 筆記，產出一頁式的開盤前觀察清單

v2 升級：優先從 DB 的 smc_data/entry_plan JSONB 讀取，不再即時計算 SMC
"""
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc, and_
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


def _smc_from_db(ar: AnalysisResult | None) -> dict | None:
    """從 AnalysisResult 的 smc_data JSONB 提取 SMC v2 摘要。"""
    if not ar or not ar.smc_data:
        return None
    smc = ar.smc_data
    ep = ar.entry_plan or {}
    return {
        "trend": smc.get("structure", {}).get("trend", "unknown"),
        "regime": ar.regime,
        "recommendation": ep.get("recommendation"),
        "action": ep.get("action"),
        "entry_price": ep.get("entry_price"),
        "stop_price": ep.get("stop_price"),
        "target_price": ep.get("target_price"),
        "rr_ratio": ep.get("rr_ratio"),
        "position_tier": ep.get("position_tier"),
        "conditions_met": ep.get("conditions_met"),
        "warnings": ep.get("warnings", []),
        "mtf": ep.get("mtf"),
    }


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

    # 提取所有持倉的 stock_id
    holding_stock_ids = [h.stock_id for h, _, _, _ in holdings_raw]

    # ── 批量查詢所有持倉的最新 AnalysisResult（避免 N+1） ──
    # 子查詢：每個 stock_id 的最新 analysis_date
    latest_ar_subq = (
        select(AnalysisResult.stock_id, func.max(AnalysisResult.analysis_date).label("latest_date"))
        .where(AnalysisResult.stock_id.in_(holding_stock_ids))
        .group_by(AnalysisResult.stock_id)
        .subquery()
    )
    latest_ar_map = {}
    if holding_stock_ids:
        ar_r = await db.execute(
            select(AnalysisResult)
            .join(latest_ar_subq, and_(
                AnalysisResult.stock_id == latest_ar_subq.c.stock_id,
                AnalysisResult.analysis_date == latest_ar_subq.c.latest_date
            ))
        )
        for ar in ar_r.scalars():
            latest_ar_map[ar.stock_id] = ar

    # ── 批量查詢所有持倉的最新 AiAnalysisNote（避免 N+1） ──
    # 子查詢：每個 stock_id 的最新 created_at
    latest_ai_subq = (
        select(AiAnalysisNote.stock_id, func.max(AiAnalysisNote.created_at).label("latest_time"))
        .where(AiAnalysisNote.stock_id.in_(holding_stock_ids))
        .group_by(AiAnalysisNote.stock_id)
        .subquery()
    )
    latest_ai_map = {}
    if holding_stock_ids:
        ai_r = await db.execute(
            select(AiAnalysisNote)
            .join(latest_ai_subq, and_(
                AiAnalysisNote.stock_id == latest_ai_subq.c.stock_id,
                AiAnalysisNote.created_at == latest_ai_subq.c.latest_time
            ))
        )
        for ai in ai_r.scalars():
            latest_ai_map[ai.stock_id] = ai

    portfolio_items = []
    for h, ticker, market, name in holdings_raw:
        # 從查找表取得最新分析和 AI 筆記
        ar = latest_ar_map.get(h.stock_id)
        ai_note = latest_ai_map.get(h.stock_id)

        # 優先用 v2 SMC 數據，fallback 到 v1
        smc_v2 = _smc_from_db(ar)
        if smc_v2:
            smc_trend = smc_v2["trend"]
            mtf_info = smc_v2.get("mtf")
            current_price = float(ar.close_price) if ar and ar.close_price else None
        else:
            # Fallback: v1 即時計算
            df = await load_price_df(db, h.stock_id, limit=1260)
            smc_trend = "未知"
            mtf_info = None
            current_price = None
            if df is not None and len(df) >= 30:
                try:
                    smc_trend = find_structure(df).get("trend", "未知")
                    current_price = round(float(df["Close"].iloc[-1]), 2)
                    weekly_trend = "未知"
                    monthly_trend = "未知"
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
        # 用 v2 entry_plan 的 stop_price，否則 fallback 到 -7%
        stop_loss = smc_v2["stop_price"] if smc_v2 and smc_v2.get("stop_price") else round(avg_cost * 0.93, 2)
        take_profit = smc_v2["target_price"] if smc_v2 and smc_v2.get("target_price") else round(avg_cost * 1.15, 2)
        pnl_pct = round((current_price - avg_cost) / avg_cost * 100, 2) if current_price else None

        # 判斷警報等級
        alert = None
        trend_str = smc_trend if isinstance(smc_trend, str) else str(smc_trend)
        if trend_str in ("下降趨勢", "downtrend", "weak_downtrend"):
            alert = "trend_down"
        if stop_loss and current_price and current_price <= stop_loss:
            alert = "stop_hit"
        elif stop_loss and current_price and current_price <= stop_loss * 1.03:
            alert = "near_stop"

        portfolio_items.append({
            "ticker": ticker,
            "market": market,
            "name": name,
            "shares": float(h.total_shares),
            "avg_cost": avg_cost,
            "current_price": current_price,
            "pnl_pct": pnl_pct,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "smc_trend": smc_trend,
            "smc_v2": smc_v2,
            "mtf_alignment": mtf_info.get("alignment") if isinstance(mtf_info, dict) and "alignment" in mtf_info else None,
            "mtf_tradable": mtf_info.get("tradable") if isinstance(mtf_info, dict) and "tradable" in mtf_info else None,
            "alert": alert,
            "composite_score": float(ar.composite_score) if ar and ar.composite_score else None,
            "recommendation": smc_v2["recommendation"] if smc_v2 else (ar.recommendation if ar else None),
            "ai_action": ai_note.action if ai_note else None,
            "ai_summary_preview": (ai_note.summary[:120] + "...") if ai_note and len(ai_note.summary) > 120 else (ai_note.summary if ai_note else None),
            "ai_note_id": ai_note.id if ai_note else None,
            "ai_note_at": ai_note.created_at.isoformat() if ai_note else None,
        })

    # 排序：alert 優先（stop_hit > near_stop > trend_down > None）
    alert_order = {"stop_hit": 0, "near_stop": 1, "trend_down": 2, None: 3}
    portfolio_items.sort(key=lambda x: alert_order.get(x["alert"], 3))

    # ── 3. 推薦觀察清單（優先用 v2 推薦，fallback 到 v1） ──
    holding_tickers = {ticker for _, ticker, _, _ in holdings_raw}

    watchlist = []
    if latest_date:
        # 先查有 v2 entry_plan 的推薦
        watch_r = await db.execute(
            select(AnalysisResult, Stock.ticker, Stock.market, Stock.name)
            .join(Stock)
            .where(
                AnalysisResult.analysis_date == latest_date,
                Stock.is_active == True,
                AnalysisResult.smc_data.isnot(None),
            )
            .order_by(AnalysisResult.composite_score.desc())
            .limit(20)
        )
        watch_rows = watch_r.all()

        # ── 批量查詢 v2 推薦的 AI 筆記（避免 N+1） ──
        v2_stock_ids = [ar.stock_id for ar, _, _, _ in watch_rows]
        v2_ai_map = {}
        if v2_stock_ids:
            v2_ai_subq = (
                select(AiAnalysisNote.stock_id, func.max(AiAnalysisNote.created_at).label("latest_time"))
                .where(AiAnalysisNote.stock_id.in_(v2_stock_ids))
                .group_by(AiAnalysisNote.stock_id)
                .subquery()
            )
            ai_r = await db.execute(
                select(AiAnalysisNote)
                .join(v2_ai_subq, and_(
                    AiAnalysisNote.stock_id == v2_ai_subq.c.stock_id,
                    AiAnalysisNote.created_at == v2_ai_subq.c.latest_time
                ))
            )
            for ai in ai_r.scalars():
                v2_ai_map[ai.stock_id] = ai

        REC_RANK = {"強力推薦": 4, "推薦": 3, "觀察": 2}
        for ar, ticker, market, name in watch_rows:
            if ticker in holding_tickers:
                continue
            smc_v2 = _smc_from_db(ar)
            rec = smc_v2["recommendation"] if smc_v2 else ar.recommendation
            if REC_RANK.get(rec, 0) < 2:
                continue

            ai_note = v2_ai_map.get(ar.stock_id)

            close = float(ar.close_price) if ar.close_price else None
            entry_price = smc_v2.get("entry_price") if smc_v2 else None
            distance_pct = round((close - entry_price) / entry_price * 100, 1) if entry_price and close else None

            watchlist.append({
                "ticker": ticker,
                "market": market,
                "name": name,
                "composite_score": float(ar.composite_score) if ar.composite_score else None,
                "recommendation": rec,
                "current_price": close,
                "smc_v2": smc_v2,
                "distance_pct": distance_pct,
                "signals": ar.signals or [],
                "ai_action": ai_note.action if ai_note else None,
                "ai_summary_preview": (ai_note.summary[:120] + "...") if ai_note and len(ai_note.summary) > 120 else (ai_note.summary if ai_note else None),
                "ai_note_id": ai_note.id if ai_note else None,
                "ai_note_at": ai_note.created_at.isoformat() if ai_note else None,
            })

        # 如果 v2 推薦不夠，補 v1 推薦
        if len(watchlist) < 5:
            v1_watch_r = await db.execute(
                select(AnalysisResult, Stock.ticker, Stock.market, Stock.name)
                .join(Stock)
                .where(
                    AnalysisResult.analysis_date == latest_date,
                    Stock.is_active == True,
                    AnalysisResult.recommendation.in_(["強力推薦", "推薦", "觀察"]),
                )
                .order_by(AnalysisResult.composite_score.desc())
                .limit(10)
            )
            v1_watch_rows = v1_watch_r.all()

            # ── 批量查詢 v1 推薦的 AI 筆記（避免 N+1） ──
            v1_stock_ids = [ar.stock_id for ar, _, _, _ in v1_watch_rows]
            v1_ai_map = {}
            if v1_stock_ids:
                v1_ai_subq = (
                    select(AiAnalysisNote.stock_id, func.max(AiAnalysisNote.created_at).label("latest_time"))
                    .where(AiAnalysisNote.stock_id.in_(v1_stock_ids))
                    .group_by(AiAnalysisNote.stock_id)
                    .subquery()
                )
                ai_r = await db.execute(
                    select(AiAnalysisNote)
                    .join(v1_ai_subq, and_(
                        AiAnalysisNote.stock_id == v1_ai_subq.c.stock_id,
                        AiAnalysisNote.created_at == v1_ai_subq.c.latest_time
                    ))
                )
                for ai in ai_r.scalars():
                    v1_ai_map[ai.stock_id] = ai

            existing_tickers = {w["ticker"] for w in watchlist}
            for ar, ticker, market, name in v1_watch_rows:
                if ticker in holding_tickers or ticker in existing_tickers:
                    continue
                entry = _get_entry(ar)
                close = float(ar.close_price) if ar.close_price else None
                distance_pct = round((close - entry["entry"]) / entry["entry"] * 100, 1) if entry and close and entry.get("entry") else None

                # 從 v1_ai_map 取出 AI 筆記（若有）
                ai_note = v1_ai_map.get(ar.stock_id) if v1_stock_ids else None

                watchlist.append({
                    "ticker": ticker,
                    "market": market,
                    "name": name,
                    "composite_score": float(ar.composite_score) if ar.composite_score else None,
                    "recommendation": ar.recommendation,
                    "current_price": close,
                    "smc_v2": _smc_from_db(ar),
                    "distance_pct": distance_pct,
                    "signals": ar.signals or [],
                    "ai_action": ai_note.action if ai_note else None,
                    "ai_summary_preview": ai_note.summary if ai_note else None,
                    "ai_note_id": str(ai_note.id) if ai_note else None,
                    "ai_note_at": ai_note.created_at.isoformat() if ai_note else None,
                })
                if len(watchlist) >= 10:
                    break

    # ── 4. 大盤指標（優先讀 DB，fallback v1）───────────────
    # 一次查詢所有市場指標的 Stock 記錄
    market_tickers = ["SPY", "QQQ", "SOXX"]
    stock_r = await db.execute(
        select(Stock).where(Stock.ticker.in_(market_tickers))
    )
    market_stocks = {s.ticker: s for s in stock_r.scalars()}
    market_stock_ids = [s.id for s in market_stocks.values()]

    # ── 批量查詢所有市場指標的最新 AnalysisResult（v2） ──
    idx_ar_map = {}
    if market_stock_ids:
        idx_ar_subq = (
            select(AnalysisResult.stock_id, func.max(AnalysisResult.analysis_date).label("latest_date"))
            .where(AnalysisResult.stock_id.in_(market_stock_ids), AnalysisResult.smc_data.isnot(None))
            .group_by(AnalysisResult.stock_id)
            .subquery()
        )
        idx_ar_r = await db.execute(
            select(AnalysisResult)
            .join(idx_ar_subq, and_(
                AnalysisResult.stock_id == idx_ar_subq.c.stock_id,
                AnalysisResult.analysis_date == idx_ar_subq.c.latest_date
            ))
        )
        for ar in idx_ar_r.scalars():
            idx_ar_map[ar.stock_id] = ar

    # ── 批量查詢前一日價格（針對有最新分析的指標） ──
    # 構造 (stock_id, latest_date) 配對
    prev_price_map = {}
    if idx_ar_map:
        # 對每個股票，查詢最新的 2 筆記錄（latest + previous）
        prev_ar_r = await db.execute(
            select(AnalysisResult)
            .where(AnalysisResult.stock_id.in_(list(idx_ar_map.keys())))
            .order_by(AnalysisResult.stock_id, desc(AnalysisResult.analysis_date))
            .limit(2)  # 只取最新 2 筆，避免載入完整歷史
        )
        all_prev_ars = prev_ar_r.scalars().all()

        # 組織成 {stock_id: [latest_ar, prev_ar]}
        ar_by_stock = {}
        for ar in all_prev_ars:
            if ar.stock_id not in ar_by_stock:
                ar_by_stock[ar.stock_id] = []
            ar_by_stock[ar.stock_id].append(ar)

        # 取得前一日價格
        for stock_id, ars in ar_by_stock.items():
            if len(ars) > 1:
                prev_price_map[stock_id] = float(ars[1].close_price) if ars[1].close_price else None

    market_indices = {}
    for idx_ticker in market_tickers:
        idx_stock = market_stocks.get(idx_ticker)
        if not idx_stock:
            continue

        idx_ar = idx_ar_map.get(idx_stock.id)
        if idx_ar and idx_ar.smc_data:
            trend = idx_ar.smc_data.get("structure", {}).get("trend", "未知")
            close = float(idx_ar.close_price) if idx_ar.close_price else None
            prev = prev_price_map.get(idx_stock.id, close)
            chg = round((close - prev) / prev * 100, 2) if close and prev else 0
            market_indices[idx_ticker] = {"price": close, "change_pct": chg, "trend": trend, "regime": idx_ar.regime}
        else:
            # Fallback: v1 即時計算
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
