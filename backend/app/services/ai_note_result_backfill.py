"""
AI Analysis Notes 結果回填服務
負責定期檢查待評估的 AI 分析筆記，並根據當前市場價格更新交易結果。

邏輯：
1. 找出所有 outcome_status == 'pending' 的筆記
2. 對於每筆筆記：
   - 如果超過 30 天 → outcome_status = 'expired'
   - 否則，獲取當前股價：
     - 如果 >= target_price → outcome_status = 'hit_target'
     - 如果 <= stop_price → outcome_status = 'hit_stop'
     - 否則保持 'pending'
3. 計算 actual_return_pct = (closed_price - entry_price) / entry_price * 100
4. 設置 closed_at = 現在時間
"""

from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ai_note import AiAnalysisNote
from ..models.stock import Stock, PriceHistory
import logging

logger = logging.getLogger(__name__)


async def backfill_ai_note_results(db: AsyncSession) -> dict:
    """
    回填所有待評估的 AI 分析筆記結果。

    Returns:
        {"updated": int, "expired": int, "hit_target": int, "hit_stop": int}
    """
    # 獲取所有 pending 的筆記
    result = await db.execute(
        select(AiAnalysisNote, Stock).join(
            Stock, AiAnalysisNote.stock_id == Stock.id
        ).where(
            AiAnalysisNote.outcome_status == "pending"
        )
    )
    pending_notes = result.all()

    stats = {
        "total_checked": len(pending_notes),
        "updated": 0,
        "expired": 0,
        "hit_target": 0,
        "hit_stop": 0,
    }

    now = datetime.utcnow()

    for note, stock in pending_notes:
        # 檢查是否過期（30 天）
        if (now - note.created_at) > timedelta(days=30):
            note.outcome_status = "expired"
            note.closed_at = now
            # 使用最後已知的價格（如果有）
            if not note.closed_price:
                # 嘗試獲取最新價格
                latest_price = await _get_latest_stock_price(db, stock.id)
                if latest_price:
                    note.closed_price = latest_price
                    note.actual_return_pct = _calculate_return_pct(
                        float(note.entry_price) if note.entry_price else None,
                        latest_price
                    )
            stats["expired"] += 1
            stats["updated"] += 1
            continue

        # 獲取當前股價
        current_price = await _get_latest_stock_price(db, stock.id)
        if not current_price:
            logger.warning(f"Stock {stock.ticker} 無法取得最新價格，跳過 note #{note.id}")
            continue

        # 判斷是否達到目標或停損
        if note.target_price and current_price >= float(note.target_price):
            note.outcome_status = "hit_target"
            note.closed_price = current_price
            note.closed_at = now
            note.actual_return_pct = _calculate_return_pct(
                float(note.entry_price) if note.entry_price else None,
                current_price
            )
            stats["hit_target"] += 1
            stats["updated"] += 1
        elif note.stop_price and current_price <= float(note.stop_price):
            note.outcome_status = "hit_stop"
            note.closed_price = current_price
            note.closed_at = now
            note.actual_return_pct = _calculate_return_pct(
                float(note.entry_price) if note.entry_price else None,
                current_price
            )
            stats["hit_stop"] += 1
            stats["updated"] += 1

    await db.commit()
    logger.info(f"AI notes backfill 完成: {stats}")
    return stats


async def _get_latest_stock_price(db: AsyncSession, stock_id: int) -> float | None:
    """獲取股票最新收盤價"""
    result = await db.execute(
        select(PriceHistory.close)
        .where(PriceHistory.stock_id == stock_id)
        .order_by(PriceHistory.date.desc())
        .limit(1)
    )
    price_row = result.scalar_one_or_none()
    return float(price_row) if price_row else None


def _calculate_return_pct(entry_price: float | None, closed_price: float | None) -> float | None:
    """計算回報百分比"""
    if not entry_price or not closed_price or entry_price == 0:
        return None
    return ((closed_price - entry_price) / entry_price) * 100
