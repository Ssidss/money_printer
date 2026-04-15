from __future__ import annotations
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── 資料庫 ─────────────────────────────────────────────
    DB_HOST: Optional[str] = None  # None = 使用嵌入式 PostgreSQL，否則使用外部數據庫
    DB_PORT: int = 54330  # 預設改為 54330，避免與系統 PG (5432) 衝突
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""
    DB_NAME: str = "money_printer"

    # ── 嵌入式 PostgreSQL 配置 ─────────────────────────────
    DATA_DIR: Optional[str] = None  # None = ~/.kingarmy/db/，可透過環境變數覆寫
    EMBEDDED_PG_PORT: int = 54330  # 嵌入式 PG 埠號，預設 54330

    @property
    def embedded_db_mode(self) -> bool:
        """是否使用嵌入式 PostgreSQL（當 DB_HOST 為 None 或空字串時）"""
        return not self.DB_HOST

    @property
    def DATABASE_URL(self) -> str:
        """
        回傳資料庫 URL

        嵌入式模式：連接至本機 localhost:EMBEDDED_PG_PORT
        外部模式：連接至 DB_HOST:DB_PORT
        """
        if self.embedded_db_mode:
            # 嵌入式模式：使用 localhost + EMBEDDED_PG_PORT
            port = self.EMBEDDED_PG_PORT
            pwd = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
            return f"postgresql+asyncpg://{self.DB_USER}{pwd}@localhost:{port}/{self.DB_NAME}"

        # 外部數據庫模式：使用 DB_HOST + DB_PORT
        pwd = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
        return f"postgresql+asyncpg://{self.DB_USER}{pwd}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def AUTO_DB(self) -> bool:
        """[已廢棄] 使用 embedded_db_mode 替代"""
        return self.embedded_db_mode

    # ── 認證 ───────────────────────────────────────────────
    SECRET_KEY: str = "dev-only-change-in-production-please"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 小時
    ALGORITHM: str = "HS256"

    @model_validator(mode="after")
    def _validate_secret_key_in_production(self) -> Settings:
        """[CRITICAL-SEC] 生產環境必須使用自訂 SECRET_KEY，不允許預設值"""
        default_key = "dev-only-change-in-production-please"
        if self.ENVIRONMENT == "production" and self.SECRET_KEY == default_key:
            raise ValueError(
                f"CRITICAL SECURITY ERROR: Cannot use default SECRET_KEY in production. "
                f"Set SECRET_KEY environment variable to a strong random value. "
                f"Current: ENVIRONMENT='{self.ENVIRONMENT}', SECRET_KEY='{default_key}'"
            )
        return self

    # ── 通知 ───────────────────────────────────────────────
    DISCORD_WEBHOOK_URL: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # ── 部署 ───────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000"  # 逗號分隔
    ENVIRONMENT: str = "development"  # development | production

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── 每日推薦 ──────────────────────────────────────────
    DAILY_RECOMMEND_COUNT: int = 3

    # ── 歷史資料抓取天數 ──────────────────────────────────
    PRICE_HISTORY_DAYS: int = 1825  # 5 年，供週線/月線 SMC 分析用

    # ── TWSE 台股 API 配置 ────────────────────────────────
    TWSE_API_BASE: str = "https://www.twse.com.tw/exchangeReport"
    TWSE_STOCK_DAY_ENDPOINT: str = "STOCK_DAY"  # TWSE_API_BASE/STOCK_DAY
    TWSE_API_TIMEOUT: int = 10
    TWSE_API_RETRY_COUNT: int = 3

    # ── 技術分析參數 ──────────────────────────────────────
    RSI_PERIOD: int = 14
    RSI_OVERSOLD: float = 35.0
    RSI_OVERBOUGHT: float = 65.0
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    BB_PERIOD: int = 20
    MA_SHORT: int = 5
    MA_MID: int = 20
    MA_LONG: int = 60
    VOLUME_MA: int = 20

    # ── 停利停損 ──────────────────────────────────────────
    STOP_LOSS_PCT: float = 0.07
    TAKE_PROFIT_PCT: float = 0.15
    TRAILING_STOP_PCT: float = 0.05

    # ── 追蹤的股票清單 ────────────────────────────────────
    US_STOCKS: list[str] = [
        # 科技巨頭
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
        # 半導體
        "AMD", "INTC", "QCOM", "TSM", "AVGO", "MU", "MRVL", "ARM", "ASML", "ALAB",
        # AI / 雲端 / 軟體
        "PLTR", "SNOW", "NET", "CRWD", "PANW", "NOW", "CRM",
        # 其他科技
        "UBER", "SHOP", "SMCI",
        # 無人機 / 無線通訊
        "ONDS",
        # ETF
        "QQQ", "SPY", "SOXX",
        # 醫療 / 金融
        "UNH", "JPM",
    ]
    TW_STOCKS: list[str] = [
        # 半導體
        "2330", "2303", "2454", "3034", "2379", "3711", "6770",
        # 電子代工 / 零組件 / 伺服器
        "2317", "2308", "2357", "2382", "3231", "2356",
        # AI / 機器人 / 散熱
        "3443", "2059", "3017", "6547",
        # IC 設計
        "3661", "5274",
        # 光學
        "3008",
        # 電信
        "2412",
        # 金融
        "2882", "2881", "2886", "2891", "2884",
        # 傳產 / 航運
        "1301", "1303", "2002", "2603", "2609",
        # ETF
        "0050", "00919",
    ]


settings = Settings()
