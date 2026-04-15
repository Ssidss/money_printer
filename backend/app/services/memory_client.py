"""
Memory Engine Client — 調用記憶引擎 API

提供 async client，支持所有記憶引擎 API 端點。
"""

import os
import logging
from typing import Optional, Any

import httpx

logger = logging.getLogger(__name__)


class MemoryEngineClient:
    """Async HTTP client for Memory Engine API."""

    def __init__(self, base_url: Optional[str] = None):
        """
        初始化記憶引擎客戶端。

        Args:
            base_url: 記憶引擎基礎 URL (優先級: 參數 > 環境變數 > 預設)
        """
        if base_url:
            self.base_url = base_url
        else:
            self.base_url = os.getenv('MEMORY_ENGINE_URL', 'http://localhost:8001')

        self._http_client: Optional[httpx.AsyncClient] = None
        self._timeout = httpx.Timeout(30.0)

    async def _get_client(self) -> httpx.AsyncClient:
        """取得或建立 AsyncClient。"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout
            )
        return self._http_client

    async def health(self) -> bool:
        """健康檢查 — GET /api/v1/health。不拋出異常。"""
        try:
            client = await self._get_client()
            response = await client.get('/api/v1/health')
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Memory engine health check failed: {e}")
            return False

    async def remember(self, trade: dict) -> dict:
        """記錄單筆交易 — POST /api/v1/remember"""
        client = await self._get_client()
        response = await client.post('/api/v1/remember', json=trade)
        if response.status_code >= 400:
            raise Exception(f"API error: {response.status_code} {response.text}")
        return response.json()

    async def remember_batch(self, trades: list[dict]) -> dict:
        """批次記錄交易 — POST /api/v1/remember/batch"""
        client = await self._get_client()
        response = await client.post('/api/v1/remember/batch', json={'trades': trades})
        if response.status_code >= 400:
            raise Exception(f"API error: {response.status_code}")
        return response.json()

    async def recall(self, indicators: dict, **filters) -> dict:
        """查詢相似記憶 — POST /api/v1/recall"""
        client = await self._get_client()
        payload = {'indicators': indicators, **filters}
        response = await client.post('/api/v1/recall', json=payload)
        if response.status_code >= 400:
            raise Exception(f"API error: {response.status_code}")
        return response.json()

    async def get_decision_table(self, timeframe: Optional[str] = None) -> dict:
        """獲取最新決策表 — GET /api/v1/decision-table/latest"""
        client = await self._get_client()
        params = {'timeframe': timeframe} if timeframe else {}
        response = await client.get('/api/v1/decision-table/latest', params=params)
        if response.status_code >= 400:
            raise Exception(f"API error: {response.status_code}")
        return response.json()

    async def lookup(self, indicators: dict, stock_category: str, timeframe: str) -> dict:
        """查詢決策規則 — POST /api/v1/decision-table/lookup"""
        client = await self._get_client()
        payload = {
            'indicators': indicators,
            'stock_category': stock_category,
            'timeframe': timeframe,
        }
        response = await client.post('/api/v1/decision-table/lookup', json=payload)
        if response.status_code >= 400:
            raise Exception(f"API error: {response.status_code}")
        return response.json()

    async def trigger_reflect(self) -> dict:
        """觸發反思引擎 — POST /api/v1/reflect"""
        client = await self._get_client()
        response = await client.post('/api/v1/reflect', json={})
        if response.status_code >= 400:
            raise Exception(f"API error: {response.status_code}")
        return response.json()

    async def trigger_generate_table(self, **params) -> dict:
        """觸發決策表生成 — POST /api/v1/decision-table/generate"""
        client = await self._get_client()
        response = await client.post('/api/v1/decision-table/generate', json=params)
        if response.status_code >= 400:
            raise Exception(f"API error: {response.status_code}")
        return response.json()

    async def get_stats(self, group_by: str = None, **filters) -> dict:
        """取得統計資訊 — GET /api/v1/stats"""
        client = await self._get_client()
        params = {}
        if group_by:
            params['group_by'] = group_by
        params.update(filters)
        response = await client.get('/api/v1/stats', params=params)
        if response.status_code >= 400:
            raise Exception(f"API error: {response.status_code}")
        return response.json()

    async def close(self):
        """關閉 HTTP 客戶端。"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self):
        """async with 支持。"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """async with 支持。"""
        await self.close()
