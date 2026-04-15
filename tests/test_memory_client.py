"""
Test Memory Engine Client
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


def test_memory_client_default_url():
    """MemoryEngineClient 應使用預設 URL"""
    from app.services.memory_client import MemoryEngineClient
    client = MemoryEngineClient()
    assert client.base_url == 'http://localhost:8001'


def test_memory_client_custom_url():
    """MemoryEngineClient 應支持自定義 URL"""
    from app.services.memory_client import MemoryEngineClient
    client = MemoryEngineClient(base_url='http://custom:8888')
    assert client.base_url == 'http://custom:8888'


def test_memory_client_env_url():
    """MemoryEngineClient 應優先使用環境變數"""
    with patch.dict('os.environ', {'MEMORY_ENGINE_URL': 'http://env-url:8001'}, clear=False):
        from app.services.memory_client import MemoryEngineClient
        client = MemoryEngineClient()
        assert client.base_url == 'http://env-url:8001'


@pytest.mark.asyncio
async def test_health_success():
    """health() 應回傳 True"""
    from app.services.memory_client import MemoryEngineClient

    mock_response = MagicMock()
    mock_response.status_code = 200

    client = MemoryEngineClient()
    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)

    with patch.object(client, '_get_client', new_callable=AsyncMock, return_value=mock_http_client):
        result = await client.health()
        assert result is True


@pytest.mark.asyncio
async def test_health_failed():
    """health() 應回傳 False 當異常"""
    from app.services.memory_client import MemoryEngineClient

    client = MemoryEngineClient()
    with patch.object(client, '_get_client', new_callable=AsyncMock, side_effect=httpx.ConnectError('fail')):
        result = await client.health()
        assert result is False


@pytest.mark.asyncio
async def test_remember():
    """remember() 應 POST 並回傳記憶 ID"""
    from app.services.memory_client import MemoryEngineClient

    trade_data = {'symbol': 'AAPL', 'entry_price': 150.0}

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {'id': 'mem_123'}

    client = MemoryEngineClient()
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_response)

    with patch.object(client, '_get_client', new_callable=AsyncMock, return_value=mock_http_client):
        result = await client.remember(trade_data)
        assert result['id'] == 'mem_123'


@pytest.mark.asyncio
async def test_remember_batch():
    """remember_batch() 應批次寫入"""
    from app.services.memory_client import MemoryEngineClient

    trades = [{'symbol': 'AAPL'}, {'symbol': 'MSFT'}]

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {'count': 2}

    client = MemoryEngineClient()
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_response)

    with patch.object(client, '_get_client', new_callable=AsyncMock, return_value=mock_http_client):
        result = await client.remember_batch(trades)
        assert result['count'] == 2


@pytest.mark.asyncio
async def test_recall():
    """recall() 應查詢相似記憶"""
    from app.services.memory_client import MemoryEngineClient

    indicators = {'rsi': 65}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'matches': []}

    client = MemoryEngineClient()
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_response)

    with patch.object(client, '_get_client', new_callable=AsyncMock, return_value=mock_http_client):
        result = await client.recall(indicators)
        assert 'matches' in result


@pytest.mark.asyncio
async def test_get_decision_table():
    """get_decision_table() 應取得決策表"""
    from app.services.memory_client import MemoryEngineClient

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'id': 'dt_123'}

    client = MemoryEngineClient()
    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)

    with patch.object(client, '_get_client', new_callable=AsyncMock, return_value=mock_http_client):
        result = await client.get_decision_table()
        assert result['id'] == 'dt_123'


@pytest.mark.asyncio
async def test_lookup():
    """lookup() 應查詢決策規則"""
    from app.services.memory_client import MemoryEngineClient

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'action': 'BUY'}

    client = MemoryEngineClient()
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_response)

    with patch.object(client, '_get_client', new_callable=AsyncMock, return_value=mock_http_client):
        result = await client.lookup({'rsi': 68}, 'large_cap', '1d')
        assert result['action'] == 'BUY'


@pytest.mark.asyncio
async def test_trigger_reflect():
    """trigger_reflect() 應觸發反思"""
    from app.services.memory_client import MemoryEngineClient

    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.json.return_value = {'job_id': 'job_999'}

    client = MemoryEngineClient()
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_response)

    with patch.object(client, '_get_client', new_callable=AsyncMock, return_value=mock_http_client):
        result = await client.trigger_reflect()
        assert result['job_id'] == 'job_999'


@pytest.mark.asyncio
async def test_trigger_generate_table():
    """trigger_generate_table() 應觸發生成"""
    from app.services.memory_client import MemoryEngineClient

    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.json.return_value = {'job_id': 'job_888'}

    client = MemoryEngineClient()
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_response)

    with patch.object(client, '_get_client', new_callable=AsyncMock, return_value=mock_http_client):
        result = await client.trigger_generate_table()
        assert result['job_id'] == 'job_888'


@pytest.mark.asyncio
async def test_get_stats():
    """get_stats() 應取得統計"""
    from app.services.memory_client import MemoryEngineClient

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'total_trades': 150}

    client = MemoryEngineClient()
    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)

    with patch.object(client, '_get_client', new_callable=AsyncMock, return_value=mock_http_client):
        result = await client.get_stats()
        assert result['total_trades'] == 150
