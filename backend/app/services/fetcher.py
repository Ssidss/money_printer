from __future__ import annotations
"""
股價抓取 Service
從 yfinance 抓取 OHLCV 並寫入 price_history 表
"""

import asyncio
import logging
import time
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.stock import Stock, PriceHistory

logger = logging.getLogger(__name__)

TW_COMPANY_NAMES = {
    # 半導體
    "2330": "台積電", "2303": "聯電", "2454": "聯發科", "3034": "聯詠",
    "2379": "瑞昱", "3711": "日月光投控", "6770": "力積電",
    # 電子代工 / 零組件 / 伺服器
    "2317": "鴻海", "2308": "台達電", "2357": "華碩",
    "2382": "廣達", "3231": "緯創", "2356": "英業達",
    # AI / 機器人 / 散熱
    "3443": "創意", "2059": "川湖", "3017": "奇鋐", "6547": "高端疫苗",
    # IC 設計
    "3661": "世芯-KY", "5274": "信驊",
    # 光學
    "3008": "大立光",
    # 電信
    "2412": "中華電",
    # 金融
    "2882": "國泰金", "2881": "富邦金", "2886": "兆豐金", "2891": "中信金",
    "2884": "玉山金",
    # 傳產 / 航運
    "1301": "台塑", "1303": "南亞", "2002": "中鋼",
    "2603": "長榮", "2609": "陽明",
    # ETF
    "0050": "元大台灣50", "00919": "群益台灣精選高息",
}

US_COMPANY_NAMES = {
    "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon",
    "NVDA": "NVIDIA", "META": "Meta", "TSLA": "Tesla", "AMD": "AMD",
    "INTC": "Intel", "QCOM": "Qualcomm", "TSM": "台積電 ADR", "AVGO": "Broadcom",
    "MU": "Micron", "MRVL": "Marvell", "ARM": "Arm Holdings", "ASML": "ASML",
    "ALAB": "Astera Labs", "PLTR": "Palantir", "SNOW": "Snowflake", "NET": "Cloudflare",
    "CRWD": "CrowdStrike", "PANW": "Palo Alto", "NOW": "ServiceNow", "CRM": "Salesforce",
    "UBER": "Uber", "SHOP": "Shopify", "SMCI": "Super Micro",
    "QQQ": "Nasdaq 100 ETF", "SPY": "S&P 500 ETF", "SOXX": "半導體 ETF",
    "UNH": "UnitedHealth", "JPM": "JPMorgan",
}


async def ensure_stock_exists(db: AsyncSession, ticker: str, market: str) -> Stock:
    """確保 stocks 表有這支股票，不存在則新增"""
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()
    if stock is None:
        name = TW_COMPANY_NAMES.get(ticker) if market == "TW" else US_COMPANY_NAMES.get(ticker)
        stock = Stock(ticker=ticker, market=market, name=name)
        db.add(stock)
        await db.flush()
        logger.info(f"新增股票記錄: {ticker} ({market})")
    return stock


async def get_latest_price_date(db: AsyncSession, stock_id: int) -> date | None:
    """取得 DB 中某股票最新的價格日期"""
    result = await db.execute(
        select(func.max(PriceHistory.date)).where(PriceHistory.stock_id == stock_id)
    )
    return result.scalar_one_or_none()


def _fetch_yfinance(symbol: str, start: str, end: str) -> pd.DataFrame | None:
    """同步呼叫 yfinance（跑在 executor 中）"""
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(start=start, end=end)
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df[["Open", "High", "Low", "Close", "Volume"]]
    except Exception as e:
        logger.error(f"yfinance 抓取 {symbol} 失敗: {e}")
        return None


def _resolve_tw_symbol(ticker: str) -> tuple[str, str] | None:
    """找出台股的 yfinance symbol（.TW 或 .TWO）"""
    for suffix in [".TW", ".TWO"]:
        try:
            symbol = ticker + suffix
            df = yf.Ticker(symbol).history(period="5d")
            if not df.empty:
                return symbol, suffix
        except Exception:
            pass
        time.sleep(0.3)
    return None


async def fetch_and_store_prices(
    db: AsyncSession,
    ticker: str,
    market: str,
    days: int = 365,
    progress_cb=None,
) -> int:
    """
    抓取股價並寫入 DB，只補齊缺失的日期

    Returns:
        寫入的新資料筆數
    """
    stock = await ensure_stock_exists(db, ticker, market)
    latest_date = await get_latest_price_date(db, stock.id)

    # 決定起始日期
    if latest_date:
        start_date = latest_date + timedelta(days=1)
        if start_date >= date.today():
            logger.debug(f"{ticker} 資料已是最新，跳過")
            return 0
        start_str = start_date.strftime("%Y-%m-%d")
    else:
        start_str = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    end_str = date.today().strftime("%Y-%m-%d")

    if progress_cb:
        await progress_cb(f"正在抓取 {ticker} 股價 ({start_str} ~ {end_str})...")

    # 在 executor 中跑同步的 yfinance 呼叫
    loop = asyncio.get_event_loop()

    if market == "US":
        df = await loop.run_in_executor(None, _fetch_yfinance, ticker, start_str, end_str)
    else:
        # 台股先找正確 symbol
        symbol_info = await loop.run_in_executor(None, _resolve_tw_symbol, ticker)
        if symbol_info is None:
            logger.warning(f"[TW] {ticker} 找不到對應的 yfinance symbol")
            return 0
        symbol, _ = symbol_info
        df = await loop.run_in_executor(None, _fetch_yfinance, symbol, start_str, end_str)

    if df is None or df.empty:
        return 0

    # 批次 upsert
    rows = []
    for dt, row in df.iterrows():
        rows.append({
            "stock_id": stock.id,
            "date": dt.date(),
            "open": float(row["Open"]) if pd.notna(row["Open"]) else None,
            "high": float(row["High"]) if pd.notna(row["High"]) else None,
            "low": float(row["Low"]) if pd.notna(row["Low"]) else None,
            "close": float(row["Close"]) if pd.notna(row["Close"]) else None,
            "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else None,
        })

    if not rows:
        return 0

    stmt = insert(PriceHistory).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["stock_id", "date"])
    await db.execute(stmt)
    await db.commit()

    logger.info(f"{ticker} 寫入 {len(rows)} 筆股價資料")
    return len(rows)


async def fetch_all_stocks(
    db: AsyncSession,
    us_tickers: list[str],
    tw_tickers: list[str],
    days: int = 365,
    progress_cb=None,
) -> dict:
    """批次補齊所有股票的股價資料，回傳各股票寫入筆數"""
    results = {}
    total = len(us_tickers) + len(tw_tickers)
    done = 0

    for ticker in us_tickers:
        count = await fetch_and_store_prices(db, ticker, "US", days=days, progress_cb=progress_cb)
        results[ticker] = count
        done += 1
        if progress_cb:
            await progress_cb(f"股價補齊進度 {done}/{total}", current=done, total=total)

    for ticker in tw_tickers:
        count = await fetch_and_store_prices(db, ticker, "TW", days=days, progress_cb=progress_cb)
        results[ticker] = count
        done += 1
        if progress_cb:
            await progress_cb(f"股價補齊進度 {done}/{total}", current=done, total=total)

    return results
