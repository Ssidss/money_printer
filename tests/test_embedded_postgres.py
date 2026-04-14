"""
Tests for embedded_postgres.py PostgreSQLManager
"""

import asyncio
import socket
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from app.embedded_postgres import PostgreSQLManager


class TestPostgreSQLManager:
    """PostgreSQL 管理器的單元測試"""

    @pytest.fixture
    def pg_manager(self, temp_pgdata_dir):
        """提供 PostgreSQL 管理器實例"""
        return PostgreSQLManager(
            pgdata_dir=temp_pgdata_dir,
            db_user="postgres",
            db_password="",
            db_port=5432,
        )

    def test_initialization(self, pg_manager):
        """測試管理器初始化"""
        assert pg_manager.db_user == "postgres"
        assert pg_manager.db_password == ""
        assert pg_manager.db_port == 5432
        assert pg_manager.process is None
        assert pg_manager.use_embedded_postgres is False
        assert pg_manager._startup_attempted is False

    def test_pgdata_dir_expansion(self, temp_pgdata_dir):
        """測試 pgdata_dir 的路徑擴展"""
        pg_manager = PostgreSQLManager(
            pgdata_dir="~/.money_printer/pgdata",
            db_user="postgres",
            db_password="",
            db_port=5432,
        )
        expected = Path.home() / ".money_printer/pgdata"
        assert pg_manager.pgdata_dir == expected

    def test_is_running_returns_false_when_not_listening(self, pg_manager):
        """當連接埠沒有監聽時，is_running 應返回 False"""
        # 使用一個不太可能有服務監聽的埠
        pg_manager.db_port = 59999
        running = asyncio.run(pg_manager.is_running())
        assert running is False

    def test_wait_for_ready_timeout(self, pg_manager):
        """wait_for_ready 應該在超時後拋出 TimeoutError"""
        pg_manager.db_port = 59999  # 未監聽的埠

        with pytest.raises(TimeoutError):
            asyncio.run(pg_manager._wait_for_ready(timeout=1))

    def test_stop_when_not_started(self, pg_manager):
        """如果未啟動，stop() 應該安全地返回"""
        # 這不應該拋出異常
        asyncio.run(pg_manager.stop())

    def test_stop_calls_pg_ctl(self, pg_manager):
        """stop() 應該使用 pg_ctl 停止（當使用 pg_ctl 啟動時）"""
        pg_manager._startup_attempted = True
        pg_manager.use_embedded_postgres = False

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            asyncio.run(pg_manager.stop())

            # 驗證 pg_ctl stop 被調用
            call_args = mock_run.call_args
            assert "pg_ctl" in call_args[0][0]
            assert "stop" in call_args[0][0]

    def test_stop_terminates_process(self, pg_manager):
        """stop() 應該終止進程（當使用 embedded-postgres 時）"""
        pg_manager._startup_attempted = True
        pg_manager.use_embedded_postgres = True
        pg_manager.process = MagicMock()
        pg_manager.process.terminate = MagicMock()
        pg_manager.process.wait = MagicMock()

        asyncio.run(pg_manager.stop())

        pg_manager.process.terminate.assert_called_once()

    def test_ensure_database_exists_creates_if_not_exists(self, pg_manager):
        """ensure_database_exists 應該在資料庫不存在時建立它"""

        async def mock_async_test():
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(side_effect=[None, "'test_db'"])  # 資料庫不存在，然後 quote_ident 返回結果
            mock_conn.execute = AsyncMock()
            mock_conn.close = AsyncMock()

            with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_connect.return_value = mock_conn

                await pg_manager.ensure_database_exists("test_db")

                # fetchval 應該被調用兩次：一次檢查資料庫，一次 quote_ident
                assert mock_conn.fetchval.call_count == 2
                # execute 應該被調用來建立資料庫
                mock_conn.execute.assert_called_once()
                call_args = mock_conn.execute.call_args
                # 應該使用 quote_ident 的結果，而不是直接插入
                assert "CREATE DATABASE" in call_args[0][0]

        asyncio.run(mock_async_test())

    def test_ensure_database_exists_skips_existing(self, pg_manager):
        """ensure_database_exists 應該跳過已存在的資料庫"""

        async def mock_async_test():
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(return_value=1)  # 資料庫存在
            mock_conn.execute = AsyncMock()
            mock_conn.close = AsyncMock()

            with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
                mock_connect.return_value = mock_conn

                await pg_manager.ensure_database_exists("test_db")

                # fetchval 應該被調用一次（檢查資料庫是否存在）
                mock_conn.fetchval.assert_called_once()
                # execute 不應該被調用（資料庫已存在）
                mock_conn.execute.assert_not_called()

        asyncio.run(mock_async_test())

    def test_startup_idempotent(self, pg_manager):
        """多次調用 start() 應該是冪等的"""
        pg_manager._startup_attempted = True

        async def mock_async_test():
            result1 = await pg_manager.start()
            result2 = await pg_manager.start()

            # 兩次調用應該返回相同的結果
            assert result1["host"] == result2["host"]
            assert result1["port"] == result2["port"]

        asyncio.run(mock_async_test())

    def test_start_pg_ctl_uses_correct_port_flag(self, pg_manager):
        """pg_ctl start 應使用 -o "-p PORT" 而非 -p PORT"""
        pg_manager.pgdata_dir.mkdir(parents=True, exist_ok=True)
        # 建立 PG_VERSION 檔案，跳過 initdb
        (pg_manager.pgdata_dir / "PG_VERSION").touch()

        async def mock_async_test():
            with patch("subprocess.run") as mock_run, \
                 patch.object(pg_manager, "_wait_for_ready", new_callable=AsyncMock):
                mock_run.return_value = MagicMock(returncode=0, stdout="server started", stderr="")

                await pg_manager._start_with_pg_ctl()

                # 找出 pg_ctl start 那次呼叫
                start_call = None
                for call in mock_run.call_args_list:
                    if "start" in call[0][0]:
                        start_call = call
                        break

                assert start_call is not None, "未找到包含 'start' 的 pg_ctl 呼叫"
                cmd = start_call[0][0]

                # 正確：應包含 ["-o", "-p 5432"]
                assert "-o" in cmd, f"命令缺少 '-o' 旗標: {cmd}"
                o_index = cmd.index("-o")
                assert o_index + 1 < len(cmd), f"'-o' 後面應該有參數"
                assert f"-p {pg_manager.db_port}" in cmd[o_index + 1], \
                    f"'-o' 後面的參數應該包含 '-p {pg_manager.db_port}'，得到: {cmd[o_index + 1]}"

                # 錯誤：不應直接出現 ["-p", "5432"]（作為獨立參數）
                if "-p" in cmd:
                    p_index = cmd.index("-p")
                    # 確認 -p 不是獨立出現，而是在 -o 的參數內
                    assert p_index == o_index + 1 or cmd[p_index - 1] == "-o", \
                        f"'-p' 不應直接出現為獨立參數: {cmd}"

        asyncio.run(mock_async_test())
