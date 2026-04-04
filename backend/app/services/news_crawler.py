from __future__ import annotations
"""
新聞爬取 Service
從 Google News RSS + Yahoo Finance RSS 抓取新聞並寫入 DB
"""

import logging
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.analysis import NewsArticle
from ..models.stock import Stock
from .sentiment import score_title

logger = logging.getLogger(__name__)

TW_COMPANY_NAMES = {
    "2330": "台積電", "2303": "聯電", "2308": "台達電", "2317": "鴻海",
    "2357": "華碩", "2882": "國泰金", "2881": "富邦金", "2886": "兆豐金",
    "2891": "中信金", "2412": "中華電", "2454": "聯發科", "3008": "大立光",
    "2379": "瑞昱", "1301": "台塑", "1303": "南亞", "2002": "中鋼",
}


def _parse_date(entry) -> Optional[datetime]:
    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return parsedate_to_datetime(val)
            except Exception:
                pass
    return None


def _google_news(query: str, lang: str = "en", max_items: int = 10, days: int = 3) -> list[dict]:
    encoded = urllib.parse.quote(query)
    if lang == "zh-TW":
        url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    else:
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        feed = feedparser.parse(url)
        results = []
        for entry in feed.entries[:max_items * 2]:
            pub = _parse_date(entry)
            if pub and pub < cutoff:
                continue
            results.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "source": entry.get("source", {}).get("title", "Google News") if hasattr(entry, "source") else "Google News",
                "published_at": pub,
            })
            if len(results) >= max_items:
                break
        return results
    except Exception as e:
        logger.error(f"Google News 失敗 ({query}): {e}")
        return []


def _yahoo_news(symbol: str, max_items: int = 8) -> list[dict]:
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
    try:
        feed = feedparser.parse(url)
        return [
            {
                "title": e.get("title", ""),
                "url": e.get("link", ""),
                "source": "Yahoo Finance",
                "published_at": _parse_date(e),
            }
            for e in feed.entries[:max_items]
        ]
    except Exception as e:
        logger.error(f"Yahoo Finance RSS 失敗 ({symbol}): {e}")
        return []


async def crawl_and_store_news(
    db: AsyncSession,
    stock: Stock,
    days: int = 3,
    max_per_source: int = 8,
) -> int:
    """爬取一支股票的新聞並寫入 DB，回傳新增筆數"""
    ticker = stock.ticker
    market = stock.market

    raw_articles = []
    if market == "US":
        raw_articles += _google_news(f"{ticker} stock", lang="en", max_items=max_per_source, days=days)
        raw_articles += _yahoo_news(ticker, max_items=max_per_source)
    else:
        company = TW_COMPANY_NAMES.get(ticker, ticker)
        raw_articles += _google_news(f"{company} 股票 {ticker}", lang="zh-TW", max_items=max_per_source, days=days)
        raw_articles += _google_news(f"{company} stock", lang="en", max_items=4, days=days)

    # 去重
    seen, unique = set(), []
    for a in raw_articles:
        if a["title"] and a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    if not unique:
        return 0

    # 清除 DB 中超過 7 天的舊新聞
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    await db.execute(
        delete(NewsArticle).where(
            NewsArticle.stock_id == stock.id,
            NewsArticle.created_at < cutoff,
        )
    )

    # 寫入新聞
    count = 0
    for a in unique:
        sentiment = score_title(a["title"])
        article = NewsArticle(
            stock_id=stock.id,
            title=a["title"][:500],
            url=a["url"][:1000] if a["url"] else None,
            source=a["source"],
            published_at=a["published_at"],
            sentiment_score=sentiment,
        )
        db.add(article)
        count += 1

    await db.commit()
    logger.info(f"[News] {ticker} 寫入 {count} 則新聞")
    return count
