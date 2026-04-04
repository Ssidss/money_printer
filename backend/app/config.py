from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://postgres@localhost/money_printer"
    DISCORD_WEBHOOK_URL: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # 排程（台灣時間）
    SCHEDULE_TW_HOUR: int = 18
    SCHEDULE_TW_MINUTE: int = 30
    SCHEDULE_US_HOUR: int = 6
    SCHEDULE_US_MINUTE: int = 30

    # 每日推薦數量
    DAILY_RECOMMEND_COUNT: int = 3

    # 歷史資料抓取天數
    PRICE_HISTORY_DAYS: int = 365

    # 技術分析參數
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

    # 評分權重
    WEIGHT_TECHNICAL: float = 0.6
    WEIGHT_SENTIMENT: float = 0.4

    # 停利停損
    STOP_LOSS_PCT: float = 0.07
    TAKE_PROFIT_PCT: float = 0.15
    TRAILING_STOP_PCT: float = 0.05

    # 追蹤的股票清單
    US_STOCKS: list[str] = [
        # 科技巨頭
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
        # 半導體
        "AMD", "INTC", "QCOM", "TSM", "AVGO", "MU", "MRVL", "ARM", "ASML", "ALAB",
        # AI / 雲端 / 軟體
        "PLTR", "SNOW", "NET", "CRWD", "PANW", "NOW", "CRM",
        # 其他科技
        "UBER", "SHOP", "SMCI",
        # ETF
        "QQQ", "SPY", "SOXX",
        # 醫療 / 金融
        "UNH", "JPM",
    ]
    TW_STOCKS: list[str] = [
        "2330", "2303", "2308", "2317", "2357",
        "2882", "2881", "2886", "2891",
        "2412", "2454", "3008", "2379",
        "1301", "1303", "2002",
    ]


settings = Settings()
