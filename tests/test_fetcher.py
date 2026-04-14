"""
測試 fetcher.py — 股價抓取服務

注：原本的 _resolve_tw_symbol 台股 symbol 解析已被 TWSE API 替代。
台股特定的測試已移至 test_twse_fetcher.py。
本文件保留用於未來的整合測試和美股邏輯測試。
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import pandas as pd
from datetime import date, datetime

# 未來可在此添加 fetch_and_store_prices 的整合測試
# 以及 US 股票 (yfinance) 邏輯的測試
