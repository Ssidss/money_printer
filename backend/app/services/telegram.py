from __future__ import annotations
"""
Telegram 通知 Service
每日分析完成、持倉警示時自動推播
"""

import logging
from datetime import date
from typing import Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


async def _send(text: str, parse_mode: str = "HTML") -> bool:
    """發送訊息到設定的 chat_id"""
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        logger.debug("Telegram 未設定，跳過通知")
        return False

    url = TELEGRAM_API.format(token=token, method="sendMessage")
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=payload)
            if r.status_code == 200:
                return True
            logger.error(f"Telegram 回傳 {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Telegram 發送失敗: {e}")
        return False


def _score_emoji(score: float) -> str:
    if score >= 75: return "🟢"
    if score >= 65: return "🟡"
    if score >= 55: return "🟠"
    return "🔴"


async def notify_daily_report(top_picks: list[dict], summary: dict) -> bool:
    """每日分析完成 → 推播 Top Picks"""
    today = summary.get("date", date.today().isoformat())
    total = summary.get("total_analyzed", 0)

    lines = [
        f"📊 <b>Money Printer 每日報告</b>",
        f"<code>{today}</code>  分析 {total} 支股票",
        "",
    ]

    rank_emojis = ["🥇", "🥈", "🥉"]
    for i, pick in enumerate(top_picks):
        emoji = rank_emojis[i] if i < 3 else f"#{i+1}"
        score = pick.get("composite_score", 0)
        rsi   = pick.get("rsi", 0)
        price = pick.get("close_price", 0)
        rec   = pick.get("recommendation", "")
        news  = pick.get("news_summary", {})
        macd_val = pick.get("macd", 0) or 0
        macd_sig = pick.get("macd_signal", 0) or 0
        macd_dir = "金叉 ▲" if macd_val > macd_sig else "死叉 ▼"

        lines += [
            f"{emoji} <b>{pick['ticker']}</b> ({pick['market']})  {_score_emoji(score)} {rec}",
            f"   綜合分: <b>{score}</b>  |  現價: {price}",
            f"   RSI: {rsi:.1f}  MACD: {macd_dir}",
            f"   新聞情緒: {news.get('label', 'N/A')} ({news.get('article_count', 0)} 則)",
        ]
        signals = pick.get("signals", [])
        if signals:
            lines.append(f"   💡 {signals[0]}")
        lines.append("")

    lines.append("⚠️ 僅供參考，不構成投資建議")

    return await _send("\n".join(lines))


async def notify_portfolio_alert(holdings: list[dict]) -> bool:
    """持倉有停損/停利警示時推播"""
    alerts = [
        h for h in holdings
        if h.get("advice") in ("停損", "停利", "追蹤停損")
    ]
    if not alerts:
        return True

    lines = [f"🚨 <b>持倉警示</b>  {len(alerts)} 個部位需要注意\n"]
    for h in alerts:
        pnl   = h.get("pnl_pct", 0)
        sign  = "+" if pnl >= 0 else ""
        emoji = "🔴" if "停損" in h["advice"] else "🟢"
        lines += [
            f"{emoji} <b>{h['ticker']}</b> ({h['market']})  →  {h['advice']}",
            f"   買入: {h['buy_price']}  現價: {h.get('current_price', '?')}",
            f"   損益: <b>{sign}{pnl:.1f}%</b>",
            f"   {h.get('advice_detail', '')}",
            "",
        ]

    return await _send("\n".join(lines))


async def notify_backtest_done(metrics: dict, name: str = "回測") -> bool:
    """回測完成後推播摘要"""
    lines = [
        f"⏪ <b>{name} 完成</b>\n",
        f"📈 總報酬: <b>{metrics.get('total_return_pct', 0):+.2f}%</b>  "
        f"年化: {metrics.get('annual_return_pct', 0):+.2f}%",
        f"📉 最大回撤: {metrics.get('max_drawdown_pct', 0):.2f}%  "
        f"Sharpe: {metrics.get('sharpe_ratio', 0):.3f}",
        f"🎯 勝率: {metrics.get('win_rate', 0):.1f}%  "
        f"總交易: {metrics.get('total_trades', 0)} 筆",
        f"✅ 獲利均值: +{metrics.get('avg_profit_pct', 0):.2f}%  "
        f"❌ 虧損均值: {metrics.get('avg_loss_pct', 0):.2f}%",
    ]
    return await _send("\n".join(lines))


async def send_test() -> bool:
    """測試用：發送一則確認訊息"""
    return await _send("✅ <b>Money Printer</b> Telegram 通知設定成功！")
