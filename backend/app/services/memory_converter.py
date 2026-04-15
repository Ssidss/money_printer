"""
VBT 回測結果轉換器 — 將 VBT 結果寫入記憶引擎

功能：
- 提取 VBT 回測的 trades
- 用 OHLCV 資料還原當天技術指標快照
- 批次寫入記憶引擎
"""

import logging
import pandas as pd
import numpy as np
from typing import Optional

from app.services.memory_client import MemoryEngineClient

logger = logging.getLogger(__name__)


async def convert_vbt_result_to_memories(
    vbt_result: dict,
    symbol: str,
    strategy_name: str,
    timeframe: str,
    ohlcv_df: pd.DataFrame,
    memory_client: MemoryEngineClient,
    market: Optional[str] = None
) -> int:
    """
    將 VBT 回測結果轉換並寫入記憶引擎。

    Args:
        vbt_result: VBT 回測結果 dict，包含 'trades' 清單
        symbol: 股票代碼
        strategy_name: 策略名稱
        timeframe: 時間框架 (1d, 4h, 等等)
        ohlcv_df: OHLCV 歷史資料 (用於還原技術指標快照)
        memory_client: MemoryEngineClient 實例
        market: 市場標籤 (tw/us/futures)，預設為環境變數 DEFAULT_MARKET

    Returns:
        寫入的交易記憶筆數
    """
    import os

    if market is None:
        market = os.getenv('DEFAULT_MARKET', 'us')

    trades = vbt_result.get('trades', [])
    if not trades:
        logger.info(f"No trades found in VBT result for {symbol}")
        return 0

    # 轉換 VBT trades 為記憶格式
    memories = []
    for trade in trades:
        # 提取交易資料
        entry_date = trade.get('entry_date')
        exit_date = trade.get('exit_date')
        entry_price = float(trade.get('entry_price', 0))
        exit_price = float(trade.get('exit_price', 0))
        pnl_pct = float(trade.get('pnl_pct', 0))

        # 還原當時的技術指標快照
        entry_indicators = _extract_indicators(ohlcv_df, entry_date)
        exit_indicators = _extract_indicators(ohlcv_df, exit_date)

        # 構建記憶資料
        memory = {
            'symbol': symbol,
            'strategy_name': strategy_name,
            'timeframe': timeframe,
            'market': market,
            'entry_date': str(entry_date.date()) if hasattr(entry_date, 'date') else str(entry_date),
            'exit_date': str(exit_date.date()) if hasattr(exit_date, 'date') else str(exit_date),
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl_pct': pnl_pct,
            'entry_indicators': entry_indicators,
            'exit_indicators': exit_indicators,
            'size': trade.get('size', 100),
        }
        memories.append(memory)

    if not memories:
        return 0

    # 批次寫入記憶引擎
    try:
        result = await memory_client.remember_batch(memories)
        count = result.get('count', len(memories))
        logger.info(f"Saved {count} trade memories for {symbol} ({strategy_name})")
        return count
    except Exception as e:
        logger.error(f"Failed to save memories for {symbol}: {e}")
        raise


def _extract_indicators(ohlcv_df: pd.DataFrame, date_val) -> dict:
    """
    從 OHLCV 資料提取指定日期的技術指標快照。

    Args:
        ohlcv_df: OHLCV DataFrame
        date_val: 日期

    Returns:
        技術指標 dict (rsi, macd, bb, atr, 等等)
    """
    import ta

    # 轉換日期格式，確保能查詢
    date_str = str(date_val.date()) if hasattr(date_val, 'date') else str(date_val)

    # 找到 <=  該日期的最新資料
    try:
        mask = pd.to_datetime(ohlcv_df.index) <= pd.Timestamp(date_str)
        df_up_to_date = ohlcv_df[mask]
        if df_up_to_date.empty:
            return {}

        close = df_up_to_date['Close'].values
        if len(close) < 14:
            return {}

        # 計算常見技術指標
        indicators = {}

        # RSI (14)
        if len(close) >= 14:
            indicators['rsi_14'] = float(ta.momentum.rsi(pd.Series(close), window=14).iloc[-1])

        # MACD
        try:
            macd = ta.trend.macd(pd.Series(close), window_fast=12, window_slow=26, window_sign=9)
            if macd is not None and len(macd) > 0:
                indicators['macd'] = float(macd.iloc[-1])
        except Exception:
            pass

        # ATR (14)
        try:
            high = df_up_to_date['High'].values
            low = df_up_to_date['Low'].values
            if len(high) >= 14 and len(low) >= 14:
                tr = np.maximum.reduce([
                    high[-14:] - low[-14:],
                    np.abs(high[-14:] - close[-15:-1]),
                    np.abs(low[-14:] - close[-15:-1])
                ])
                indicators['atr_14'] = float(np.mean(tr))
        except Exception:
            pass

        # 布林帶
        try:
            bb = ta.volatility.bollinger_bands(pd.Series(close), window=20, window_dev=2)
            if bb is not None:
                indicators['bb_high'] = float(bb.iloc[-1, 0]) if len(bb) > 0 else None
                indicators['bb_mid'] = float(bb.iloc[-1, 1]) if len(bb) > 0 else None
                indicators['bb_low'] = float(bb.iloc[-1, 2]) if len(bb) > 0 else None
        except Exception:
            pass

        return indicators
    except Exception as e:
        logger.warning(f"Failed to extract indicators for date {date_val}: {e}")
        return {}
