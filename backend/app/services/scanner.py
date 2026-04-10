from __future__ import annotations
"""
量價異常掃描器 (Volume-Price Anomaly Scanner)

掃描 DB 中所有追蹤股票，找出量價異常的潛在爆擊股。
也可透過 yfinance 掃描外部股票池。

核心指標：
1. Volume Spike: 當日量 / 20MA量 → 量比
2. Price Surge: 單日漲幅 %
3. Consecutive Up Days: 連續上漲天數
4. Price Range Breakout: 突破近期高點
5. Volume Acceleration: 量能逐日遞增
6. Low Price Advantage: 低價股更容易爆發
"""

import asyncio
import logging
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.stock import Stock, PriceHistory

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    ticker: str
    market: str
    name: Optional[str]
    close_price: float
    change_pct: float           # 最近一日漲幅 %
    volume: int                 # 最近一日成交量
    avg_volume_20: float        # 20 日均量
    volume_ratio: float         # 量比（當日量/20MA）
    consecutive_up_days: int    # 連續上漲天數
    cumulative_gain_pct: float  # 連續上漲期間累計漲幅 %
    is_52w_high: bool           # 是否突破 52 週新高
    is_20d_high: bool           # 是否突破 20 日新高
    vol_acceleration: float     # 量能加速度（近3日量增率）
    explosion_score: float = 0  # 綜合爆擊分數 (0-100)
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _compute_explosion_score(r: ScanResult) -> float:
    """
    計算爆擊潛力分數 (0-100)

    權重：
      量比 30%  — 量比越高越異常
      漲幅 20%  — 單日漲幅越大越好
      連漲 15%  — 連續上漲天數
      突破 15%  — 突破新高加分
      量加速 10% — 量能逐日遞增
      低價 10%  — 低價股更容易爆
    """
    score = 0
    signals = []

    # 1. 量比 (0-30 分)
    if r.volume_ratio >= 10:
        score += 30
        signals.append(f"量比 {r.volume_ratio:.1f}x（極端放量）")
    elif r.volume_ratio >= 5:
        score += 25
        signals.append(f"量比 {r.volume_ratio:.1f}x（巨量）")
    elif r.volume_ratio >= 3:
        score += 18
        signals.append(f"量比 {r.volume_ratio:.1f}x（大幅放量）")
    elif r.volume_ratio >= 2:
        score += 10
        signals.append(f"量比 {r.volume_ratio:.1f}x（放量）")

    # 2. 單日漲幅 (0-20 分)
    if r.change_pct >= 20:
        score += 20
        signals.append(f"單日漲幅 +{r.change_pct:.1f}%（暴漲）")
    elif r.change_pct >= 10:
        score += 15
        signals.append(f"單日漲幅 +{r.change_pct:.1f}%（大漲）")
    elif r.change_pct >= 5:
        score += 10
        signals.append(f"單日漲幅 +{r.change_pct:.1f}%")
    elif r.change_pct >= 3:
        score += 5
        signals.append(f"單日漲幅 +{r.change_pct:.1f}%")

    # 3. 連續上漲 (0-15 分)
    if r.consecutive_up_days >= 5:
        score += 15
        signals.append(f"連漲 {r.consecutive_up_days} 天（累計 +{r.cumulative_gain_pct:.1f}%）")
    elif r.consecutive_up_days >= 3:
        score += 10
        signals.append(f"連漲 {r.consecutive_up_days} 天（累計 +{r.cumulative_gain_pct:.1f}%）")
    elif r.consecutive_up_days >= 2:
        score += 5
        signals.append(f"連漲 {r.consecutive_up_days} 天")

    # 4. 突破新高 (0-15 分)
    if r.is_52w_high:
        score += 15
        signals.append("突破 52 週新高")
    elif r.is_20d_high:
        score += 8
        signals.append("突破 20 日新高")

    # 5. 量能加速 (0-10 分)
    if r.vol_acceleration >= 2:
        score += 10
        signals.append(f"量能連日加速 {r.vol_acceleration:.1f}x")
    elif r.vol_acceleration >= 1.5:
        score += 5
        signals.append(f"量能加速 {r.vol_acceleration:.1f}x")

    # 6. 低價優勢 (0-10 分)
    if r.close_price <= 5:
        score += 10
        signals.append(f"低價股 ${r.close_price:.2f}（爆發空間大）")
    elif r.close_price <= 10:
        score += 7
        signals.append(f"低價區 ${r.close_price:.2f}")
    elif r.close_price <= 20:
        score += 3

    r.explosion_score = min(score, 100)
    r.signals = signals
    return r.explosion_score


async def scan_tracked_stocks(db: AsyncSession, min_score: float = 15) -> list[ScanResult]:
    """掃描 DB 中所有追蹤股票，找出量價異常"""
    result = await db.execute(select(Stock).where(Stock.is_active == True))
    stocks = result.scalars().all()

    scan_results: list[ScanResult] = []

    for stock in stocks:
        try:
            sr = await _analyze_stock_from_db(db, stock)
            if sr and sr.explosion_score >= min_score:
                scan_results.append(sr)
        except Exception as e:
            logger.warning(f"掃描 {stock.ticker} 失敗: {e}")

    scan_results.sort(key=lambda x: x.explosion_score, reverse=True)
    return scan_results


async def _analyze_stock_from_db(db: AsyncSession, stock: Stock) -> Optional[ScanResult]:
    """從 DB 價格資料分析單支股票的量價異常"""
    # 取最近 260 個交易日（約一年）
    rows = (await db.execute(
        select(PriceHistory)
        .where(PriceHistory.stock_id == stock.id)
        .order_by(PriceHistory.date.desc())
        .limit(260)
    )).scalars().all()

    if len(rows) < 25:
        return None

    # 轉成 DataFrame（由舊到新）
    data = []
    for r in reversed(rows):
        data.append({
            "date": r.date,
            "open": float(r.open) if r.open else None,
            "high": float(r.high) if r.high else None,
            "low": float(r.low) if r.low else None,
            "close": float(r.close) if r.close else None,
            "volume": int(r.volume) if r.volume else 0,
        })
    df = pd.DataFrame(data).dropna(subset=["close"])

    if len(df) < 25:
        return None

    return _compute_scan_result(df, stock.ticker, stock.market, stock.name)


def _compute_scan_result(
    df: pd.DataFrame, ticker: str, market: str, name: Optional[str]
) -> Optional[ScanResult]:
    """從 DataFrame 計算 ScanResult"""
    latest = df.iloc[-1]
    close_price = latest["close"]
    volume = int(latest["volume"])

    if close_price <= 0 or volume <= 0:
        return None

    # 20 日均量
    vol_20 = df["volume"].iloc[-20:].mean()
    volume_ratio = volume / vol_20 if vol_20 > 0 else 0

    # 單日漲幅
    if len(df) >= 2:
        prev_close = df.iloc[-2]["close"]
        change_pct = (close_price - prev_close) / prev_close * 100 if prev_close > 0 else 0
    else:
        change_pct = 0

    # 連續上漲天數 & 累計漲幅
    consecutive_up = 0
    cumulative_gain = 0
    for i in range(len(df) - 1, 0, -1):
        if df.iloc[i]["close"] > df.iloc[i - 1]["close"]:
            consecutive_up += 1
        else:
            break

    if consecutive_up > 0 and len(df) > consecutive_up:
        base_price = df.iloc[-(consecutive_up + 1)]["close"]
        cumulative_gain = (close_price - base_price) / base_price * 100 if base_price > 0 else 0

    # 52 週新高
    high_52w = df["high"].iloc[-min(252, len(df)):].max()
    is_52w_high = close_price >= high_52w * 0.98  # 接近 2% 以內算突破

    # 20 日新高
    high_20d = df["high"].iloc[-min(20, len(df)):].max()
    is_20d_high = close_price >= high_20d * 0.99

    # 量能加速度（近 3 日的量各比前一日）
    vol_accel = 1.0
    if len(df) >= 4:
        recent_vols = df["volume"].iloc[-3:].values
        if recent_vols[0] > 0 and recent_vols[1] > 0:
            # 平均每日增長率
            r1 = recent_vols[1] / recent_vols[0] if recent_vols[0] > 0 else 1
            r2 = recent_vols[2] / recent_vols[1] if recent_vols[1] > 0 else 1
            vol_accel = (r1 + r2) / 2

    sr = ScanResult(
        ticker=ticker,
        market=market,
        name=name,
        close_price=round(close_price, 2),
        change_pct=round(change_pct, 2),
        volume=volume,
        avg_volume_20=round(vol_20, 0),
        volume_ratio=round(volume_ratio, 2),
        consecutive_up_days=consecutive_up,
        cumulative_gain_pct=round(cumulative_gain, 2),
        is_52w_high=bool(is_52w_high),
        is_20d_high=bool(is_20d_high),
        vol_acceleration=round(vol_accel, 2),
    )

    _compute_explosion_score(sr)
    return sr


# ── 外部掃描：yfinance 擴展股票池 ─────────────────────────

# 美股低價股池（penny stocks & small caps 常出現爆擊）
US_SCAN_POOL = [
    # Meme / 話題股
    "GME", "AMC", "BBBY", "BB", "NOK", "SOFI", "PLTR", "LCID", "RIVN",
    "MARA", "RIOT", "COIN", "HOOD", "WISH", "CLOV", "WKHS", "GOEV",
    # 生技 / 低價股
    "SNDL", "TLRY", "ACB", "CRON", "CGC", "NIO", "XPEV", "LI",
    "PLUG", "FCEL", "BE", "CLNE", "GEVO",
    # AI 相關中小股
    "BBAI", "SOUN", "RKLB", "ASTS", "IONQ", "RGTI",
    # SPACs & recent hot
    "DJT", "ONDS", "PHUN", "DWAC",
]


def _fetch_scan_data(symbol: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    """同步：yfinance 抓取掃描用資料"""
    try:
        t = yf.Ticker(symbol)
        df = t.history(period=period)
        if df.empty or len(df) < 20:
            return None
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        return df
    except Exception as e:
        logger.debug(f"yfinance scan {symbol} 失敗: {e}")
        return None


async def scan_external_pool(
    tickers: Optional[list[str]] = None,
    min_score: float = 20,
    progress_cb=None,
) -> list[ScanResult]:
    """掃描外部股票池（非 DB 追蹤的股票）"""
    pool = tickers or US_SCAN_POOL
    loop = asyncio.get_event_loop()
    results: list[ScanResult] = []
    total = len(pool)

    for i, ticker in enumerate(pool, 1):
        if progress_cb:
            await progress_cb(
                f"掃描 {ticker} ({i}/{total})...",
                phase="scanning", current=i, total=total, ticker=ticker,
            )

        df = await loop.run_in_executor(None, _fetch_scan_data, ticker)
        if df is None:
            continue

        sr = _compute_scan_result(df, ticker, "US", None)
        if sr and sr.explosion_score >= min_score:
            results.append(sr)

    results.sort(key=lambda x: x.explosion_score, reverse=True)
    return results


async def scan_all(
    db: AsyncSession,
    include_external: bool = True,
    min_score: float = 15,
    progress_cb=None,
) -> dict:
    """完整掃描：DB 追蹤 + 外部股票池"""
    if progress_cb:
        await progress_cb("掃描追蹤股票...", phase="tracked", current=0, total=1)

    tracked = await scan_tracked_stocks(db, min_score=min_score)

    external = []
    if include_external:
        if progress_cb:
            await progress_cb("掃描外部股票池...", phase="external", current=0, total=1)
        # 排除已追蹤的 tickers
        tracked_tickers = {r.ticker for r in tracked}
        external_pool = [t for t in US_SCAN_POOL if t not in tracked_tickers]
        external = await scan_external_pool(external_pool, min_score=min_score, progress_cb=progress_cb)

    # 合併去重
    all_results = tracked + external
    seen = set()
    deduped = []
    for r in all_results:
        if r.ticker not in seen:
            seen.add(r.ticker)
            deduped.append(r)

    deduped.sort(key=lambda x: x.explosion_score, reverse=True)

    if progress_cb:
        await progress_cb(
            f"掃描完成！找到 {len(deduped)} 支異常股票",
            phase="done", current=1, total=1,
        )

    return {
        "scan_date": date.today().isoformat(),
        "tracked_count": len(tracked),
        "external_count": len(external),
        "total_count": len(deduped),
        "results": [r.to_dict() for r in deduped],
    }
