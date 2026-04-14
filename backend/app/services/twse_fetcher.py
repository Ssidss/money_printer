"""
TWSE 台股數據爬蟲 — 從台灣證券交易所官方 API 抓取歷史價格
替代 yfinance 的台股數據源，提高數據準確性與效率
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

# TWSE API 配置
TWSE_API_BASE = "https://www.twse.com.tw/exchangeReport"
TWSE_STOCK_DAY_ENDPOINT = f"{TWSE_API_BASE}/STOCK_DAY"
TWSE_API_TIMEOUT = 10
TWSE_API_RETRY_COUNT = 3


def _parse_twse_response(resp_json: dict) -> list[dict] | None:
    """
    解析 TWSE API 回應

    Args:
        resp_json: TWSE API 返回的 JSON 物件

    Returns:
        msgArray 列表，若解析失敗返回 None
    """
    try:
        if not resp_json:
            return None

        msg_array = resp_json.get("msgArray", [])
        if not msg_array:
            return []

        return msg_array
    except Exception as e:
        logger.error(f"解析 TWSE API 回應失敗: {e}")
        return None


def _convert_twse_row_to_ohlcv(row: dict) -> dict | None:
    """
    將 TWSE 行數據轉換為 OHLCV 格式

    Args:
        row: TWSE API msgArray 中的單筆記錄

    Returns:
        {"open": float, "high": float, "low": float, "close": float, "volume": int}
    """
    try:
        # 字段對應
        # o=open, h=high, l=low, d=close, v=volume
        open_str = row.get("o")
        high_str = row.get("h")
        low_str = row.get("l")
        close_str = row.get("d")
        volume_str = row.get("v")

        # 轉換為數值，處理缺失或不合法的值
        open_val = float(open_str) if open_str else None
        high_val = float(high_str) if high_str else None
        low_val = float(low_str) if low_str else None
        close_val = float(close_str) if close_str else None
        volume_val = int(volume_str.replace(",", "")) if volume_str else None

        return {
            "open": open_val,
            "high": high_val,
            "low": low_val,
            "close": close_val,
            "volume": volume_val,
        }
    except Exception as e:
        logger.error(f"轉換 TWSE 行數據失敗: {e}, row={row}")
        return None


def _get_business_days(start_date: date, end_date: date) -> list[date]:
    """
    生成指定日期範圍內的營業日（台灣）

    簡易實現：只排除周六日，不考慮假期
    未來可改用專門的台灣營業日庫

    Args:
        start_date: 開始日期
        end_date: 結束日期

    Returns:
        營業日列表
    """
    business_days = []
    current = start_date

    while current <= end_date:
        # weekday(): 0=Monday, 6=Sunday
        if current.weekday() < 5:  # Monday-Friday
            business_days.append(current)
        current += timedelta(days=1)

    return business_days


async def fetch_twse_prices(
    ticker: str,
    start_date: date,
    end_date: date,
    timeout: int = TWSE_API_TIMEOUT,
    max_retries: int = TWSE_API_RETRY_COUNT,
) -> pd.DataFrame | None:
    """
    從 TWSE API 非同步抓取台股歷史日線 OHLCV

    Args:
        ticker: 股票代碼（4位數字，如 "2330"，不含後綴）
        start_date: 開始日期
        end_date: 結束日期
        timeout: HTTP 請求超時（秒）
        max_retries: 最大重試次數

    Returns:
        DataFrame with columns [Open, High, Low, Close, Volume]，日期為 index
        若無數據或出錯返回 None
    """
    try:
        # 驗證 ticker 格式
        if not ticker or not ticker.isdigit() or len(ticker) != 4:
            logger.warning(f"無效的台股代碼: {ticker}")
            return None

        # 獲取營業日列表
        business_days = _get_business_days(start_date, end_date)
        if not business_days:
            logger.debug(f"指定日期範圍內無營業日: {start_date} ~ {end_date}")
            return None

        all_rows = []

        # 逐個營業日抓取（TWSE API 每次只回一日）
        async with httpx.AsyncClient(timeout=timeout) as client:
            for current_date in business_days:
                date_str = current_date.strftime("%Y%m%d")

                retry_count = 0
                df_for_date = None

                while retry_count < max_retries:
                    try:
                        response = await client.get(
                            TWSE_STOCK_DAY_ENDPOINT,
                            params={
                                "response": "json",
                                "date": date_str,
                                "stockNo": ticker,
                            }
                        )

                        response.raise_for_status()
                        resp_json = response.json()

                        # 解析回應
                        msg_array = _parse_twse_response(resp_json)
                        if msg_array is None:
                            break  # 解析失敗，不重試

                        if not msg_array:
                            # 無數據（可能是假期或股票不存在）
                            logger.debug(f"{ticker} {date_str} 無數據")
                            break

                        # 轉換第一筆記錄（通常只有一筆）
                        if msg_array:
                            row = msg_array[0]
                            ohlcv = _convert_twse_row_to_ohlcv(row)
                            if ohlcv:
                                all_rows.append({
                                    "date": current_date,
                                    "open": ohlcv["open"],
                                    "high": ohlcv["high"],
                                    "low": ohlcv["low"],
                                    "close": ohlcv["close"],
                                    "volume": ohlcv["volume"],
                                })

                        break  # 成功，跳出重試迴圈

                    except httpx.TimeoutException as e:
                        retry_count += 1
                        if retry_count >= max_retries:
                            logger.warning(f"{ticker} {date_str} 超時，已重試 {max_retries} 次")
                        else:
                            # 指數退避
                            await asyncio.sleep(0.5 * (2 ** (retry_count - 1)))
                    except httpx.HTTPError as e:
                        logger.error(f"{ticker} {date_str} HTTP 錯誤: {e}")
                        break
                    except Exception as e:
                        logger.error(f"{ticker} {date_str} 未預期的錯誤: {e}")
                        break

        if not all_rows:
            logger.debug(f"{ticker} 無法抓取任何數據 ({start_date} ~ {end_date})")
            return None

        # 組裝 DataFrame
        df = pd.DataFrame(all_rows)
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

        # 重新命名欄位以符合 price_history 期望的格式
        df.columns = ["Open", "High", "Low", "Close", "Volume"]

        return df[["Open", "High", "Low", "Close", "Volume"]]

    except Exception as e:
        logger.error(f"fetch_twse_prices 失敗 ({ticker}, {start_date} ~ {end_date}): {e}")
        return None
