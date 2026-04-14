"""
pytest 配置和通用 fixtures
"""

import os
import sys
from pathlib import Path

# 添加 backend 模組到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

import pytest


@pytest.fixture
def temp_pgdata_dir(tmp_path):
    """提供臨時的 PostgreSQL 資料目錄"""
    return str(tmp_path / "pgdata")


@pytest.fixture
def mock_settings():
    """提供測試用的 Settings 物件"""
    from app.config import Settings

    settings = Settings(
        DB_HOST="localhost",
        DB_PORT=5432,
        DB_USER="postgres",
        DB_PASSWORD="",
        DB_NAME="money_printer",
    )
    return settings
