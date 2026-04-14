"""
Tests for config.py AUTO_DB property
"""

import pytest
from app.config import Settings


def test_auto_db_enabled_when_conditions_met():
    """AUTO_DB 應該在 localhost + 空密碼 + postgres 用戶時啟用"""
    settings = Settings(
        DB_HOST="localhost",
        DB_PORT=5432,
        DB_USER="postgres",
        DB_PASSWORD="",
        DB_NAME="money_printer",
    )
    assert settings.AUTO_DB is True


def test_auto_db_disabled_when_host_not_localhost():
    """AUTO_DB 應該在非 localhost 時禁用"""
    settings = Settings(
        DB_HOST="db.example.com",
        DB_PORT=5432,
        DB_USER="postgres",
        DB_PASSWORD="",
        DB_NAME="money_printer",
    )
    assert settings.AUTO_DB is False


def test_auto_db_disabled_when_password_not_empty():
    """AUTO_DB 應該在密碼非空時禁用"""
    settings = Settings(
        DB_HOST="localhost",
        DB_PORT=5432,
        DB_USER="postgres",
        DB_PASSWORD="secret",
        DB_NAME="money_printer",
    )
    assert settings.AUTO_DB is False


def test_auto_db_disabled_when_user_not_postgres():
    """AUTO_DB 應該在用戶不是 postgres 時禁用"""
    settings = Settings(
        DB_HOST="localhost",
        DB_PORT=5432,
        DB_USER="appuser",
        DB_PASSWORD="",
        DB_NAME="money_printer",
    )
    assert settings.AUTO_DB is False


def test_database_url_property(mock_settings):
    """DATABASE_URL 應該正確組合成完整的連接字符串"""
    url = mock_settings.DATABASE_URL
    assert url == "postgresql+asyncpg://postgres@localhost:5432/money_printer"


def test_database_url_with_password():
    """DATABASE_URL 應該包含密碼如果有提供"""
    settings = Settings(
        DB_HOST="localhost",
        DB_PORT=5432,
        DB_USER="postgres",
        DB_PASSWORD="mypassword",
        DB_NAME="money_printer",
    )
    url = settings.DATABASE_URL
    assert url == "postgresql+asyncpg://postgres:mypassword@localhost:5432/money_printer"
