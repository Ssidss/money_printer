from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── 資料庫 ─────────────────────────────────────────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""
    DB_NAME: str = "money_printer"

    @property
    def DATABASE_URL(self) -> str:
        pwd = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
        return f"postgresql+asyncpg://{self.DB_USER}{pwd}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def AUTO_DB(self) -> bool:
        """是否自動啟動嵌入式 PostgreSQL（條件：localhost + 空密碼 + postgres 用戶）"""
        return (
            self.DB_HOST == "localhost"
            and self.DB_PASSWORD == ""
            and self.DB_USER == "postgres"
        )

    # ── 認證 ───────────────────────────────────────────────
    SECRET_KEY: str = "dev-only-change-in-production-please"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 小時
    ALGORITHM: str = "HS256"

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
