"""
測試 fetcher.py — 股價抓取服務

注：原本的 _resolve_tw_symbol 台股 symbol 解析已被 TWSE API 替代。
台股特定的測試已移至 test_twse_fetcher.py。
本文件保留用於未來的整合測試和美股邏輯測試。
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import pandas as pd
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.fetcher import fetch_and_store_prices
from app.models.stock import Stock, PriceHistory


class TestFetchAndStorePrices:
    """測試 fetch_and_store_prices 函式，特別是 latest_date=None 的路徑"""

    @pytest.mark.asyncio
    async def test_fetch_and_store_prices_tw_first_time(self):
        """測試台股首次抓取（latest_date=None，無資料庫歷史資料）"""
        # 這個測試驗證當 latest_date 是 None 時，start_date 被正確設置
        # 從而不會發生 NameError

        mock_db = AsyncMock(spec=AsyncSession)
        mock_stock = MagicMock()
        mock_stock.id = 1

        # 模擬從 ensure_stock_exists 返回 stock
        with patch('app.services.fetcher.ensure_stock_exists', new_callable=AsyncMock) as mock_ensure:
            # 模擬 get_latest_price_date 返回 None（沒有歷史資料）
            with patch('app.services.fetcher.get_latest_price_date', new_callable=AsyncMock) as mock_latest:
                # 模擬 get_earliest_price_date 返回 None
                with patch('app.services.fetcher.get_earliest_price_date', new_callable=AsyncMock) as mock_earliest:
                    # 模擬 fetch_twse_prices 返回 DataFrame
                    with patch('app.services.fetcher.fetch_twse_prices', new_callable=AsyncMock) as mock_fetch_twse:
                        # 模擬 insert 和 execute
                        with patch('app.services.fetcher.insert'):
                            mock_ensure.return_value = mock_stock
                            mock_latest.return_value = None  # 首次抓取，無歷史資料
                            mock_earliest.return_value = None

                            # 模擬成功的 TWSE 響應
                            mock_df = pd.DataFrame({
                                "Open": [600.0],
                                "High": [605.0],
                                "Low": [598.0],
                                "Close": [602.0],
                                "Volume": [20000000]
                            }, index=pd.DatetimeIndex([datetime(2024, 4, 15)]))

                            mock_fetch_twse.return_value = mock_df
                            mock_db.execute = AsyncMock()
                            mock_db.commit = AsyncMock()

                            # 執行函式 — 應該不會拋 NameError
                            result = await fetch_and_store_prices(
                                mock_db,
                                "2330",
                                "TW",
                                days=365
                            )

                            # 驗證 fetch_twse_prices 被呼叫
                            assert mock_fetch_twse.called
                            # 驗證第一個參數是 ticker
                            call_args = mock_fetch_twse.call_args
                            assert call_args[0][0] == "2330"
                            # 驗證第二個參數是 start_date（應該被設置為 desired_start）
                            start_date_arg = call_args[0][1]
                            assert start_date_arg is not None
                            assert isinstance(start_date_arg, date)
