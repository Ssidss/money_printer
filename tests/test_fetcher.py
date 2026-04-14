"""
測試 fetcher.py — 台股 symbol 快取 + time.sleep 移除
"""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

# 使用 conftest 的路徑設定
from app.services.fetcher import _resolve_tw_symbol, _TW_SYMBOL_CACHE


class TestResolveTwSymbol:
    """測試 _resolve_tw_symbol 的快取和效能"""

    def setup_method(self):
        """清空快取，確保每個測試獨立"""
        _TW_SYMBOL_CACHE.clear()

    def test_resolve_tw_symbol_with_tw_suffix(self):
        """測試成功解析 .TW 後綴"""
        with patch('app.services.fetcher.yf.Ticker') as mock_ticker:
            # 模擬 .TW 後綴成功
            mock_stock = MagicMock()
            mock_df = pd.DataFrame({
                'Open': [100.0],
                'High': [101.0],
                'Low': [99.0],
                'Close': [100.5],
                'Volume': [1000000],
            }, index=pd.to_datetime(['2024-01-01']))
            mock_stock.history.return_value = mock_df
            mock_ticker.return_value = mock_stock

            result = _resolve_tw_symbol("2330")

            assert result is not None
            symbol, suffix = result
            assert symbol == "2330.TW"
            assert suffix == ".TW"

    def test_resolve_tw_symbol_with_tow_suffix(self):
        """測試 .TW 失敗後回退到 .TWO"""
        with patch('app.services.fetcher.yf.Ticker') as mock_ticker:
            # 模擬：.TW 失敗，.TWO 成功
            call_count = [0]
            def side_effect(*args, **kwargs):
                call_count[0] += 1
                mock_stock = MagicMock()
                if call_count[0] == 1:  # 第一次 (.TW)
                    mock_stock.history.return_value = pd.DataFrame()  # 空
                else:  # 第二次 (.TWO)
                    mock_df = pd.DataFrame({
                        'Open': [100.0],
                        'High': [101.0],
                        'Low': [99.0],
                        'Close': [100.5],
                        'Volume': [1000000],
                    }, index=pd.to_datetime(['2024-01-01']))
                    mock_stock.history.return_value = mock_df
                return mock_stock

            mock_ticker.side_effect = side_effect

            result = _resolve_tw_symbol("2330")

            assert result is not None
            symbol, suffix = result
            assert symbol == "2330.TWO"
            assert suffix == ".TWO"

    def test_resolve_tw_symbol_not_found(self):
        """測試找不到台股符號"""
        with patch('app.services.fetcher.yf.Ticker') as mock_ticker:
            mock_stock = MagicMock()
            mock_stock.history.return_value = pd.DataFrame()  # 兩種都失敗
            mock_ticker.return_value = mock_stock

            result = _resolve_tw_symbol("9999")

            assert result is None

    def test_resolve_tw_symbol_caching(self):
        """測試快取機制 — 第二次呼叫應從快取取得"""
        with patch('app.services.fetcher.yf.Ticker') as mock_ticker:
            mock_stock = MagicMock()
            mock_df = pd.DataFrame({
                'Open': [100.0],
                'High': [101.0],
                'Low': [99.0],
                'Close': [100.5],
                'Volume': [1000000],
            }, index=pd.to_datetime(['2024-01-01']))
            mock_stock.history.return_value = mock_df
            mock_ticker.return_value = mock_stock

            # 第一次呼叫
            result1 = _resolve_tw_symbol("2330")
            call_count_1 = mock_ticker.call_count

            # 第二次呼叫（應該從快取取得，不再呼叫 yf.Ticker）
            result2 = _resolve_tw_symbol("2330")
            call_count_2 = mock_ticker.call_count

            assert result1 == result2
            assert result1 == ("2330.TW", ".TW")
            # 第二次呼叫時 mock_ticker 不應該被呼叫
            assert call_count_1 == call_count_2

    def test_resolve_tw_symbol_no_sleep_delay(self):
        """測試不存在 time.sleep 延遲（效能檢查）"""
        # 驗證 fetcher.py 中不存在 time.sleep 調用
        import inspect
        import app.services.fetcher as fetcher_module

        source = inspect.getsource(fetcher_module._resolve_tw_symbol)
        assert "time.sleep" not in source, "time.sleep should be removed from _resolve_tw_symbol"
