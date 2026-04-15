"""
Test Backtest VBT + Memory Integration
驗收標準:
1. run_vbt_backtest() 支持 save_to_memory 參數
2. save_to_memory=True 時自動調用轉換器
3. 轉換結果被寫入記憶引擎
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def sample_backtest_input():
    """提供示例回測輸入"""
    dates = pd.date_range('2024-01-01', periods=50, freq='D')
    ohlcv = pd.DataFrame({
        'Open': np.linspace(150, 160, 50),
        'High': np.linspace(151, 161, 50),
        'Low': np.linspace(149, 159, 50),
        'Close': np.linspace(150.5, 160.5, 50),
        'Volume': np.random.randint(1000000, 5000000, 50),
    }, index=dates)

    return {
        'symbol': 'AAPL',
        'strategy_name': 'smc_v2',
        'timeframe': '1d',
        'ohlcv': ohlcv,
        'start_date': date(2024, 1, 1),
        'end_date': date(2024, 2, 19),
    }


# ============================================================================
# RED: 測試 save_to_memory 參數
# ============================================================================

@pytest.mark.asyncio
async def test_run_vbt_backtest_without_memory_save(sample_backtest_input):
    """run_vbt_backtest() 應支持 save_to_memory=False (預設)"""
    from app.services.backtest_vbt import run_vbt_backtest

    # 預期當 save_to_memory=False 時不調用記憶引擎
    with patch('backend.app.services.memory_converter.convert_vbt_result_to_memories') as mock_convert:
        result = await run_vbt_backtest(
            symbol=sample_backtest_input['symbol'],
            strategy_name=sample_backtest_input['strategy_name'],
            timeframe=sample_backtest_input['timeframe'],
            ohlcv_df=sample_backtest_input['ohlcv'],
            save_to_memory=False
        )

        assert result is not None
        mock_convert.assert_not_called()


@pytest.mark.asyncio
async def test_run_vbt_backtest_with_memory_save(sample_backtest_input):
    """run_vbt_backtest() 應支持 save_to_memory=True"""
    from app.services.backtest_vbt import run_vbt_backtest

    with patch('backend.app.services.memory_converter.convert_vbt_result_to_memories') as mock_convert:
        mock_convert.return_value = 2  # 假設寫入 2 筆交易記憶

        result = await run_vbt_backtest(
            symbol=sample_backtest_input['symbol'],
            strategy_name=sample_backtest_input['strategy_name'],
            timeframe=sample_backtest_input['timeframe'],
            ohlcv_df=sample_backtest_input['ohlcv'],
            save_to_memory=True
        )

        assert result is not None
        mock_convert.assert_called_once()


@pytest.mark.asyncio
async def test_run_vbt_backtest_memory_save_with_market_param(sample_backtest_input):
    """save_to_memory=True 時應傳遞 market 參數"""
    from app.services.backtest_vbt import run_vbt_backtest

    with patch('backend.app.services.memory_converter.convert_vbt_result_to_memories') as mock_convert:
        mock_convert.return_value = 1

        await run_vbt_backtest(
            symbol=sample_backtest_input['symbol'],
            strategy_name=sample_backtest_input['strategy_name'],
            timeframe=sample_backtest_input['timeframe'],
            ohlcv_df=sample_backtest_input['ohlcv'],
            save_to_memory=True,
            market='us'
        )

        # 驗證轉換函數被呼叫且傳遞 market='us'
        call_kwargs = mock_convert.call_args[1]
        assert call_kwargs['market'] == 'us'


@pytest.mark.asyncio
async def test_run_vbt_backtest_memory_save_default_market(sample_backtest_input):
    """save_to_memory=True 時如果未提供 market，應使用環境變數 DEFAULT_MARKET"""
    from app.services.backtest_vbt import run_vbt_backtest

    with patch.dict('os.environ', {'DEFAULT_MARKET': 'tw'}, clear=False):
        with patch('backend.app.services.memory_converter.convert_vbt_result_to_memories') as mock_convert:
            mock_convert.return_value = 1

            await run_vbt_backtest(
                symbol=sample_backtest_input['symbol'],
                strategy_name=sample_backtest_input['strategy_name'],
                timeframe=sample_backtest_input['timeframe'],
                ohlcv_df=sample_backtest_input['ohlcv'],
                save_to_memory=True
            )

            call_kwargs = mock_convert.call_args[1]
            assert call_kwargs['market'] == 'tw'


# ============================================================================
# RED: 測試記憶寫入失敗不影響回測結果
# ============================================================================

@pytest.mark.asyncio
async def test_memory_write_failure_does_not_fail_backtest(sample_backtest_input):
    """記憶引擎寫入失敗時，回測應繼續執行並記錄警告"""
    from app.services.backtest_vbt import run_vbt_backtest

    with patch('backend.app.services.memory_converter.convert_vbt_result_to_memories') as mock_convert:
        mock_convert.side_effect = Exception('Memory engine unavailable')

        # 應該不拋出異常，只是記錄警告
        with patch('logging.Logger.warning') as mock_warning:
            result = await run_vbt_backtest(
                symbol=sample_backtest_input['symbol'],
                strategy_name=sample_backtest_input['strategy_name'],
                timeframe=sample_backtest_input['timeframe'],
                ohlcv_df=sample_backtest_input['ohlcv'],
                save_to_memory=True
            )

            assert result is not None
            # 應有警告日誌
            mock_warning.assert_called()


# ============================================================================
# RED: 測試回測結果格式對記憶轉換的相容性
# ============================================================================

@pytest.mark.asyncio
async def test_backtest_result_compatible_with_converter(sample_backtest_input):
    """回測結果應包含轉換器需要的所有欄位"""
    from app.services.backtest_vbt import run_vbt_backtest

    with patch('backend.app.services.memory_converter.convert_vbt_result_to_memories') as mock_convert:
        mock_convert.return_value = 0

        await run_vbt_backtest(
            symbol=sample_backtest_input['symbol'],
            strategy_name=sample_backtest_input['strategy_name'],
            timeframe=sample_backtest_input['timeframe'],
            ohlcv_df=sample_backtest_input['ohlcv'],
            save_to_memory=True
        )

        # 檢查轉換器被呼叫時的 vbt_result 參數
        call_args = mock_convert.call_args[1]
        vbt_result = call_args['vbt_result']

        assert 'symbol' in vbt_result
        assert 'strategy_name' in vbt_result or 'trades' in vbt_result
