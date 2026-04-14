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


def test_secret_key_fail_fast_on_production_default():
    """[SECURITY] 在生產環境使用預設 SECRET_KEY 應該立即拋出異常"""
    with pytest.raises(ValueError, match="SECRET_KEY.*production"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="dev-only-change-in-production-please",
        )


def test_secret_key_allowed_on_development_default():
    """在開發環境使用預設 SECRET_KEY 應該被允許"""
    settings = Settings(
        ENVIRONMENT="development",
        SECRET_KEY="dev-only-change-in-production-please",
    )
    assert settings.SECRET_KEY == "dev-only-change-in-production-please"


def test_secret_key_allowed_on_production_custom():
    """在生產環境使用自訂 SECRET_KEY 應該被允許"""
    settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="my-super-secret-key-xyz123",
    )
    assert settings.SECRET_KEY == "my-super-secret-key-xyz123"
