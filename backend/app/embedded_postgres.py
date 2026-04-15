"""
嵌入式 PostgreSQL 啟動管理器
優先使用系統 pg_ctl/initdb，fallback 至 embedded-postgres 套件
"""

import asyncio
import logging
import os
import socket
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PostgreSQLManager:
    """管理嵌入式 PostgreSQL 實例的啟動、停止、狀態檢查"""

    def __init__(
        self,
        pgdata_dir: Optional[str] = None,
        db_user: str = "postgres",
        db_password: str = "",
        db_port: Optional[int] = None,
    ):
        """
        初始化 PostgreSQL 管理器

        Args:
            pgdata_dir: PostgreSQL 資料目錄。
                若為 None，使用 DATA_DIR 環境變數或預設 ~/.kingarmy/db/
            db_user: PostgreSQL 用戶名，預設 postgres
            db_password: PostgreSQL 密碼，預設為空
            db_port: PostgreSQL 埠號。
                若為 None，使用 EMBEDDED_PG_PORT 環境變數或預設 54330
        """
        # 解析資料目錄：優先順序：參數 > DATA_DIR env > ~/.kingarmy/db/
        if pgdata_dir:
            self.pgdata_dir = Path(pgdata_dir).expanduser().absolute()
        else:
            data_dir = os.getenv("DATA_DIR", "~/.kingarmy/db")
            self.pgdata_dir = Path(data_dir).expanduser().absolute()
        self.db_user = db_user
        self.db_password = db_password
        # 解析埠號：優先順序：參數 > EMBEDDED_PG_PORT env > 54330
        if db_port is not None:
            self.db_port = db_port
        else:
            port_str = os.getenv("EMBEDDED_PG_PORT", "54330")
            try:
                self.db_port = int(port_str)
            except ValueError:
                raise ValueError(
                    f"EMBEDDED_PG_PORT 必須為整數，目前值: {port_str!r}"
                )
        self.process: Optional[subprocess.Popen] = None
        self.use_embedded_postgres = False
        self._startup_attempted = False

    async def start(self) -> dict:
        """
        啟動 PostgreSQL 實例

        Returns:
            dict with keys: host, port, running, method (pg_ctl or embedded_postgres)

        Raises:
            RuntimeError: 如果無法啟動 PostgreSQL
        """
        if self._startup_attempted:
            return {
                "host": "localhost",
                "port": self.db_port,
                "running": await self.is_running(),
                "method": "embedded_postgres" if self.use_embedded_postgres else "pg_ctl",
            }

        self._startup_attempted = True
        self.pgdata_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"PostgreSQL 資料目錄: {self.pgdata_dir}")

        # 嘗試使用系統 pg_ctl（優先）
        try:
            await self._start_with_pg_ctl()
            logger.info(f"✓ 使用系統 pg_ctl 成功啟動 PostgreSQL (port={self.db_port})")
            return {
                "host": "localhost",
                "port": self.db_port,
                "running": True,
                "method": "pg_ctl",
            }
        except Exception as e:
            logger.warning(f"系統 pg_ctl 啟動失敗: {e}，嘗試 fallback 至 embedded-postgres")

        # Fallback: 嘗試 embedded-postgres 套件
        try:
            await self._start_with_embedded_postgres()
            self.use_embedded_postgres = True
            logger.info(f"✓ 使用 embedded-postgres 成功啟動 PostgreSQL (port={self.db_port})")
            return {
                "host": "localhost",
                "port": self.db_port,
                "running": True,
                "method": "embedded_postgres",
            }
        except Exception as e:
            logger.error(f"embedded-postgres 啟動失敗: {e}")
            raise RuntimeError(f"無法啟動 PostgreSQL: {e}")

    async def _start_with_pg_ctl(self) -> None:
        """使用系統 pg_ctl 啟動 PostgreSQL"""
        # 檢查 pg_ctl 是否可用
        try:
            subprocess.run(
                ["pg_ctl", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            raise RuntimeError(f"pg_ctl not found or not working: {e}")

        # 初始化資料庫集群（如果尚未初始化）
        if not (self.pgdata_dir / "PG_VERSION").exists():
            logger.info(f"初始化 PostgreSQL 資料庫集群在 {self.pgdata_dir}")
            env = os.environ.copy()
            env["PGUSER"] = self.db_user
            if self.db_password:
                env["PGPASSWORD"] = self.db_password

            try:
                result = subprocess.run(
                    ["initdb", "-D", str(self.pgdata_dir), "-U", self.db_user],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env,
                    check=True,
                )
                logger.info(f"initdb 輸出: {result.stdout}")
            except subprocess.CalledProcessError as e:
                logger.error(f"initdb 失敗: {e.stderr}")
                raise RuntimeError(f"initdb failed: {e.stderr}")

        # 啟動 PostgreSQL
        logger.info(f"啟動 PostgreSQL，埠 {self.db_port}")
        try:
            result = subprocess.run(
                [
                    "pg_ctl",
                    "-D",
                    str(self.pgdata_dir),
                    "-l",
                    str(self.pgdata_dir / "postgres.log"),
                    "-o",
                    f"-p {self.db_port}",
                    "start",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            logger.info(f"pg_ctl start 輸出: {result.stdout}")

            # 等待 PostgreSQL 就緒
            await self._wait_for_ready(timeout=30)
        except subprocess.CalledProcessError as e:
            logger.error(f"pg_ctl start 失敗: {e.stderr}")
            raise RuntimeError(f"pg_ctl start failed: {e.stderr}")

    async def _start_with_embedded_postgres(self) -> None:
        """使用 embedded-postgres 套件啟動 PostgreSQL"""
        try:
            import embedded_postgres  # type: ignore
        except ImportError:
            raise ImportError("embedded-postgres 套件未安裝，請執行: pip install embedded-postgres")

        logger.info("使用 embedded-postgres 套件啟動 PostgreSQL")
        # embedded-postgres 支持自動尋找可用埠
        pg = embedded_postgres.PostgreSQL(
            pgdata=str(self.pgdata_dir),
            user=self.db_user,
            password=self.db_password or "",
        )
        self.process = pg.start()
        await self._wait_for_ready(timeout=30)

    async def _wait_for_ready(self, timeout: int = 30) -> None:
        """等待 PostgreSQL 就緒（能接受連接）"""
        logger.info(f"等待 PostgreSQL 就緒（最多 {timeout} 秒）")
        start_time = asyncio.get_event_loop().time()

        while True:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"PostgreSQL 未在 {timeout} 秒內就緒")

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(("localhost", self.db_port))
                sock.close()
                if result == 0:
                    logger.info("✓ PostgreSQL 已就緒，接受連接")
                    return
            except Exception:
                pass

            await asyncio.sleep(0.5)

    async def stop(self) -> None:
        """優雅停止 PostgreSQL 實例"""
        if not self._startup_attempted:
            logger.info("PostgreSQL 未啟動，跳過停止")
            return

        logger.info("停止 PostgreSQL...")

        if self.use_embedded_postgres and self.process:
            # embedded-postgres 的停止邏輯
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
                logger.info("✓ embedded-postgres 已停止")
            except Exception as e:
                logger.error(f"embedded-postgres 停止失敗: {e}")

        else:
            # pg_ctl 的停止邏輯
            try:
                result = subprocess.run(
                    ["pg_ctl", "-D", str(self.pgdata_dir), "stop", "-m", "fast"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,  # 不拋出例外，即使失敗
                )
                if result.returncode == 0:
                    logger.info("✓ pg_ctl 已停止 PostgreSQL")
                else:
                    logger.warning(f"pg_ctl stop 返回碼 {result.returncode}: {result.stderr}")
            except Exception as e:
                logger.error(f"pg_ctl 停止失敗: {e}")

    async def is_running(self) -> bool:
        """檢查 PostgreSQL 是否正在運行"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("localhost", self.db_port))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def ensure_database_exists(self, db_name: str) -> None:
        """確保指定的資料庫存在（若不存在則建立）"""
        import asyncpg

        try:
            # 連接至預設 postgres 資料庫
            if self.db_password:
                dsn = f"postgresql://{self.db_user}:{self.db_password}@localhost:{self.db_port}/postgres"
            else:
                dsn = f"postgresql://{self.db_user}@localhost:{self.db_port}/postgres"
            conn = await asyncpg.connect(dsn)
            try:
                # 檢查資料庫是否存在
                exists = await conn.fetchval(
                    "SELECT 1 FROM pg_database WHERE datname = $1", db_name
                )
                if not exists:
                    logger.info(f"建立資料庫: {db_name}")
                    # 使用 quote_ident 防止 SQL Injection
                    safe_name = await conn.fetchval("SELECT quote_ident($1)", db_name)
                    await conn.execute(f"CREATE DATABASE {safe_name}")
                else:
                    logger.info(f"資料庫已存在: {db_name}")
            finally:
                await conn.close()
        except Exception as e:
            logger.error(
                f"確保資料庫存在失敗: connect to {self.db_user}@localhost:{self.db_port} - {e}"
            )
            raise
