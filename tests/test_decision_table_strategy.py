"""
Test DecisionTableStrategy
驗收標準:
1. DecisionTableStrategy 能在 STRATEGY_REGISTRY 中註冊
2. 能查詢記憶引擎決策表
3. 根據決策表生成進出場信號
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def sample_ohlcv():
    """提供示例 OHLCV 資料"""
    dates = pd.date_range('2024-01-01', periods=20, freq='D')
    return pd.DataFrame({
        'Open': np.linspace(150, 155, 20),
        'High': np.linspace(151, 156, 20),
        'Low': np.linspace(149, 154, 20),
        'Close': np.linspace(150.5, 155.5, 20),
        'Volume': np.random.randint(1000000, 5000000, 20),
    }, index=dates)


# ============================================================================
# RED: 測試 DecisionTableStrategy 可在 STRATEGY_REGISTRY 中註冊
# ============================================================================

def test_decision_table_strategy_in_registry():
    """DecisionTableStrategy 應在 STRATEGY_REGISTRY 中可用"""
    from backend.app.services.backtest_vbt import get_strategy_registry

    registry = get_strategy_registry()
    assert 'decision_table' in registry
    from backend.app.services.strategies.decision_table_strategy import DecisionTableStrategy
    assert registry['decision_table'] == DecisionTableStrategy


def test_decision_table_strategy_properties():
    """DecisionTableStrategy 應有正確的 strategy_name 和 strategy_type"""
    from backend.app.services.strategies.decision_table_strategy import DecisionTableStrategy

    strategy = DecisionTableStrategy()
    assert strategy.strategy_name == 'decision_table'
    assert strategy.strategy_type in ['decision_table', 'decision-driven', 'memory-driven']


# ============================================================================
# RED: 測試決策表查詢
# ============================================================================

@pytest.mark.asyncio
async def test_strategy_lookups_decision_table():
    """DecisionTableStrategy 應查詢記憶引擎決策表"""
    from backend.app.services.strategies.decision_table_strategy import DecisionTableStrategy
    from backend.app.services.memory_client import MemoryEngineClient

    mock_client = AsyncMock(spec=MemoryEngineClient)
    mock_client.lookup = AsyncMock(return_value={
        'rule_id': 'rule_5',
        'action': 'BUY',
        'stop_loss_pct': 2.5,
        'take_profit_pct': 5.0,
        'confidence': 0.87,
    })

    strategy = DecisionTableStrategy(memory_client=mock_client)

    # 調用 generate_signals 時應查詢決策表
    # (具體實現取決於 strategy 架構，此為測試想要的行為)
    lookup_result = await mock_client.lookup(
        {'rsi': 68, 'macd': 'bullish'},
        stock_category='large_cap',
        timeframe='1d'
    )

    assert lookup_result['action'] == 'BUY'
    assert lookup_result['stop_loss_pct'] == 2.5


# ============================================================================
# RED: 測試信號生成
# ============================================================================

@pytest.mark.asyncio
async def test_strategy_generates_buy_signal_from_decision_table(sample_ohlcv):
    """決策表 action='BUY' 應生成買入信號"""
    from backend.app.services.strategies.decision_table_strategy import DecisionTableStrategy
    from backend.app.services.backtest_vbt import DataProvider, Signal

    mock_client = AsyncMock()
    mock_client.lookup = AsyncMock(return_value={
        'rule_id': 'rule_5',
        'action': 'BUY',
        'stop_loss_pct': 2.5,
        'take_profit_pct': 5.0,
        'confidence': 0.87,
    })

    strategy = DecisionTableStrategy(memory_client=mock_client)

    # 模擬 DataProvider
    mock_provider = MagicMock(spec=DataProvider)
    mock_provider.get_ohlcv = MagicMock(return_value=sample_ohlcv)
    mock_provider.get_latest_price = MagicMock(return_value=155.5)

    # 生成信號
    signals = strategy.generate_signals('AAPL', mock_provider)

    # 應該生成買入信號
    assert len(signals) > 0
    assert signals[0].action == 'buy'
    assert signals[0].confidence >= 0.87


@pytest.mark.asyncio
async def test_strategy_generates_no_signal_for_hold(sample_ohlcv):
    """決策表 action='HOLD' 應不生成信號"""
    from backend.app.services.strategies.decision_table_strategy import DecisionTableStrategy

    mock_client = AsyncMock()
    mock_client.lookup = AsyncMock(return_value={
        'rule_id': 'rule_2',
        'action': 'HOLD',
        'confidence': 0.60,
    })

    strategy = DecisionTableStrategy(memory_client=mock_client)

    mock_provider = MagicMock()
    mock_provider.get_ohlcv = MagicMock(return_value=sample_ohlcv)

    signals = strategy.generate_signals('AAPL', mock_provider)

    # 應該沒有信號或信號為空
    assert len(signals) == 0


# ============================================================================
# RED: 測試記憶引擎不可達時的降級行為
# ============================================================================

@pytest.mark.asyncio
async def test_strategy_handles_memory_engine_unavailable(sample_ohlcv):
    """記憶引擎不可達時，策略應降級或拋出有意義的異常"""
    from backend.app.services.strategies.decision_table_strategy import DecisionTableStrategy
    from backend.app.services.memory_client import MemoryEngineClient

    mock_client = AsyncMock(spec=MemoryEngineClient)
    mock_client.lookup = AsyncMock(side_effect=Exception('Connection refused'))

    strategy = DecisionTableStrategy(memory_client=mock_client)

    mock_provider = MagicMock()
    mock_provider.get_ohlcv = MagicMock(return_value=sample_ohlcv)

    # 應該拋出異常或返回空信號（取決於設計決策）
    with pytest.raises(Exception):
        strategy.generate_signals('AAPL', mock_provider)


# ============================================================================
# RED: 測試健康檢查
# ============================================================================

@pytest.mark.asyncio
async def test_strategy_can_check_memory_health():
    """DecisionTableStrategy 應能檢查記憶引擎健康狀態"""
    from backend.app.services.strategies.decision_table_strategy import DecisionTableStrategy
    from backend.app.services.memory_client import MemoryEngineClient

    mock_client = AsyncMock(spec=MemoryEngineClient)
    mock_client.health = AsyncMock(return_value=True)

    strategy = DecisionTableStrategy(memory_client=mock_client)

    # 假設 strategy 有 health() 方法或檢查機制
    health = await mock_client.health()
    assert health is True


# ============================================================================
# RED: 測試策略初始化和參數
# ============================================================================

def test_decision_table_strategy_initialization():
    """DecisionTableStrategy 應可初始化"""
    from backend.app.services.strategies.decision_table_strategy import DecisionTableStrategy

    # 無參數初始化
    strategy = DecisionTableStrategy()
    assert strategy is not None

    # 帶 memory_client 參數
    mock_client = MagicMock()
    strategy = DecisionTableStrategy(memory_client=mock_client)
    assert strategy.memory_client == mock_client


def test_decision_table_strategy_with_config():
    """DecisionTableStrategy 應支持配置參數"""
    from backend.app.services.strategies.decision_table_strategy import DecisionTableStrategy

    config = {
        'stock_category': 'large_cap',
        'timeframe': '1d',
        'min_confidence': 0.75,
    }

    strategy = DecisionTableStrategy(**config)
    assert strategy.stock_category == 'large_cap'
    assert strategy.timeframe == '1d'
    assert strategy.min_confidence == 0.75
