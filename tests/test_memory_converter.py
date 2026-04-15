"""
Test VBT Result to Memory Converter — 驗收標準:
1. 從 VBT 結果提取 trades
2. 用 OHLCV 資料還原技術指標快照
3. 調用 memory_client.remember_batch() 寫入
4. 返回寫入的筆數
5. 處理空結果
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, date
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def sample_ohlcv():
    """提供示例 OHLCV 資料"""
    dates = pd.date_range('2024-01-01', periods=30, freq='D')
    return pd.DataFrame({
        'Open': np.linspace(150, 155, 30),
        'High': np.linspace(151, 156, 30),
        'Low': np.linspace(149, 154, 30),
        'Close': np.linspace(150.5, 155.5, 30),
        'Volume': np.random.randint(1000000, 5000000, 30),
    }, index=dates)


@pytest.fixture
def sample_vbt_result():
    """提供示例 VBT 回測結果"""
    return {
        'symbol': 'AAPL',
        'strategy': 'smc_v2',
        'trades': [
            {
                'entry_date': pd.Timestamp('2024-01-05'),
                'entry_price': 151.0,
                'exit_date': pd.Timestamp('2024-01-15'),
                'exit_price': 154.5,
                'pnl': 3.5,
                'pnl_pct': 2.32,
                'size': 100,
            },
            {
                'entry_date': pd.Timestamp('2024-01-20'),
                'entry_price': 154.0,
                'exit_date': pd.Timestamp('2024-01-28'),
                'exit_price': 156.0,
                'pnl': 2.0,
                'pnl_pct': 1.30,
                'size': 100,
            },
        ]
    }


# ============================================================================
# RED: 測試基本轉換功能
# ============================================================================

@pytest.mark.asyncio
async def test_convert_vbt_result_basic(sample_ohlcv, sample_vbt_result):
    """convert_vbt_result_to_memories() 應提取 trades 並寫入記憶"""
    from app.services.memory_converter import convert_vbt_result_to_memories
    from app.services.memory_client import MemoryEngineClient

    # Mock memory client
    mock_client = AsyncMock(spec=MemoryEngineClient)
    mock_client.remember_batch = AsyncMock(return_value={'count': 2, 'ids': ['mem_1', 'mem_2']})

    # 轉換並寫入
    count = await convert_vbt_result_to_memories(
        vbt_result=sample_vbt_result,
        symbol='AAPL',
        strategy_name='smc_v2',
        timeframe='1d',
        ohlcv_df=sample_ohlcv,
        memory_client=mock_client,
        market='us'
    )

    assert count == 2
    mock_client.remember_batch.assert_called_once()


# ============================================================================
# RED: 測試空結果處理
# ============================================================================

@pytest.mark.asyncio
async def test_convert_empty_trades(sample_ohlcv):
    """convert_vbt_result_to_memories() 應處理空 trades"""
    from app.services.memory_converter import convert_vbt_result_to_memories
    from app.services.memory_client import MemoryEngineClient

    empty_result = {
        'symbol': 'AAPL',
        'strategy': 'smc_v2',
        'trades': []
    }

    mock_client = AsyncMock(spec=MemoryEngineClient)

    count = await convert_vbt_result_to_memories(
        vbt_result=empty_result,
        symbol='AAPL',
        strategy_name='smc_v2',
        timeframe='1d',
        ohlcv_df=sample_ohlcv,
        memory_client=mock_client,
        market='us'
    )

    assert count == 0
    mock_client.remember_batch.assert_not_called()


# ============================================================================
# RED: 測試技術指標快照還原
# ============================================================================

@pytest.mark.asyncio
async def test_convert_includes_technical_indicators(sample_ohlcv, sample_vbt_result):
    """轉換後的記憶應包含技術指標快照"""
    from app.services.memory_converter import convert_vbt_result_to_memories
    from app.services.memory_client import MemoryEngineClient

    mock_client = AsyncMock(spec=MemoryEngineClient)

    # 捕獲 remember_batch 被呼叫時的參數
    captured_trades = None
    async def capture_remember_batch(trades):
        nonlocal captured_trades
        captured_trades = trades
        return {'count': len(trades), 'ids': [f'mem_{i}' for i in range(len(trades))]}

    mock_client.remember_batch = AsyncMock(side_effect=capture_remember_batch)

    count = await convert_vbt_result_to_memories(
        vbt_result=sample_vbt_result,
        symbol='AAPL',
        strategy_name='smc_v2',
        timeframe='1d',
        ohlcv_df=sample_ohlcv,
        memory_client=mock_client,
        market='us'
    )

    assert count == 2
    assert captured_trades is not None
    # 檢查第一筆記憶是否包含技術指標
    first_trade = captured_trades[0]
    assert 'entry_date' in first_trade
    assert 'entry_price' in first_trade
    assert 'exit_price' in first_trade
    # 應該有技術指標快照
    assert 'entry_indicators' in first_trade or 'technical_snapshot' in first_trade


# ============================================================================
# RED: 測試市場相關欄位 (market='tw' vs 'us')
# ============================================================================

@pytest.mark.asyncio
async def test_convert_market_field(sample_ohlcv, sample_vbt_result):
    """轉換應包含市場標籤 (tw/us/futures)"""
    from app.services.memory_converter import convert_vbt_result_to_memories
    from app.services.memory_client import MemoryEngineClient

    mock_client = AsyncMock(spec=MemoryEngineClient)
    captured_trades = None

    async def capture(trades):
        nonlocal captured_trades
        captured_trades = trades
        return {'count': len(trades), 'ids': [f'mem_{i}' for i in range(len(trades))]}

    mock_client.remember_batch = AsyncMock(side_effect=capture)

    await convert_vbt_result_to_memories(
        vbt_result=sample_vbt_result,
        symbol='AAPL',
        strategy_name='smc_v2',
        timeframe='1d',
        ohlcv_df=sample_ohlcv,
        memory_client=mock_client,
        market='us'
    )

    assert captured_trades is not None
    assert all('market' in trade for trade in captured_trades)
    assert all(trade['market'] == 'us' for trade in captured_trades)


# ============================================================================
# RED: 測試策略和時間框架標籤
# ============================================================================

@pytest.mark.asyncio
async def test_convert_strategy_and_timeframe(sample_ohlcv, sample_vbt_result):
    """轉換應包含策略名稱和時間框架"""
    from app.services.memory_converter import convert_vbt_result_to_memories
    from app.services.memory_client import MemoryEngineClient

    mock_client = AsyncMock(spec=MemoryEngineClient)
    captured_trades = None

    async def capture(trades):
        nonlocal captured_trades
        captured_trades = trades
        return {'count': len(trades), 'ids': [f'mem_{i}' for i in range(len(trades))]}

    mock_client.remember_batch = AsyncMock(side_effect=capture)

    await convert_vbt_result_to_memories(
        vbt_result=sample_vbt_result,
        symbol='AAPL',
        strategy_name='smc_v2',
        timeframe='4h',
        ohlcv_df=sample_ohlcv,
        memory_client=mock_client,
        market='tw'
    )

    assert captured_trades is not None
    assert all(trade['strategy_name'] == 'smc_v2' for trade in captured_trades)
    assert all(trade['timeframe'] == '4h' for trade in captured_trades)


# ============================================================================
# RED: 測試損益計算
# ============================================================================

@pytest.mark.asyncio
async def test_convert_pnl_fields(sample_ohlcv, sample_vbt_result):
    """轉換應正確包含損益相關欄位"""
    from app.services.memory_converter import convert_vbt_result_to_memories
    from app.services.memory_client import MemoryEngineClient

    mock_client = AsyncMock(spec=MemoryEngineClient)
    captured_trades = None

    async def capture(trades):
        nonlocal captured_trades
        captured_trades = trades
        return {'count': len(trades), 'ids': [f'mem_{i}' for i in range(len(trades))]}

    mock_client.remember_batch = AsyncMock(side_effect=capture)

    await convert_vbt_result_to_memories(
        vbt_result=sample_vbt_result,
        symbol='AAPL',
        strategy_name='smc_v2',
        timeframe='1d',
        ohlcv_df=sample_ohlcv,
        memory_client=mock_client
    )

    assert captured_trades is not None
    # 第一筆交易應有 entry_price, exit_price, pnl_pct
    first = captured_trades[0]
    assert first['entry_price'] == 151.0
    assert first['exit_price'] == 154.5
    assert abs(first['pnl_pct'] - 2.32) < 0.01


# ============================================================================
# RED: 測試異常處理
# ============================================================================

@pytest.mark.asyncio
async def test_convert_memory_client_failure(sample_ohlcv, sample_vbt_result):
    """記憶引擎寫入失敗時應拋出異常"""
    from app.services.memory_converter import convert_vbt_result_to_memories
    from app.services.memory_client import MemoryEngineClient

    mock_client = AsyncMock(spec=MemoryEngineClient)
    mock_client.remember_batch = AsyncMock(side_effect=Exception('Memory engine error'))

    with pytest.raises(Exception, match='Memory engine error'):
        await convert_vbt_result_to_memories(
            vbt_result=sample_vbt_result,
            symbol='AAPL',
            strategy_name='smc_v2',
            timeframe='1d',
            ohlcv_df=sample_ohlcv,
            memory_client=mock_client
        )


# ============================================================================
# RED: 測試 None 或缺失欄位的 VBT 結果
# ============================================================================

@pytest.mark.asyncio
async def test_convert_missing_fields(sample_ohlcv):
    """轉換應處理缺失欄位的 VBT 結果"""
    from app.services.memory_converter import convert_vbt_result_to_memories
    from app.services.memory_client import MemoryEngineClient

    incomplete_result = {
        'symbol': 'AAPL',
        'strategy': 'smc_v2',
        'trades': [
            {
                'entry_date': pd.Timestamp('2024-01-05'),
                'entry_price': 151.0,
                # 缺少 exit_date, exit_price 等
            },
        ]
    }

    mock_client = AsyncMock(spec=MemoryEngineClient)
    mock_client.remember_batch = AsyncMock(return_value={'count': 0, 'ids': []})

    # 應該優雅地處理或拋出有意義的異常
    with pytest.raises((ValueError, KeyError, TypeError)):
        await convert_vbt_result_to_memories(
            vbt_result=incomplete_result,
            symbol='AAPL',
            strategy_name='smc_v2',
            timeframe='1d',
            ohlcv_df=sample_ohlcv,
            memory_client=mock_client
        )
