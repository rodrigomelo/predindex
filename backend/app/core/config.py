"""PredIndex — Core configuration and settings."""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = "PredIndex"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 5004

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5004",
        "https://predindex.rodrigolanna.com.br",
    ]

    # Database — PostgreSQL by default; SQLite still supported via DATABASE_URL
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://predindex:predindex@localhost:5432/predindex")

    # App URL (production awareness)
    APP_URL: str = os.getenv("APP_URL", f"http://localhost:{os.getenv('PORT', '5004')}")

    # External APIs
    YAHOO_FINANCE_ENABLED: bool = True
    ALPHA_VANTAGE_API_KEY: Optional[str] = os.getenv("ALPHA_VANTAGE_API_KEY")
    ADMIN_API_KEY: Optional[str] = os.getenv("ADMIN_API_KEY")

    # Default indices to track
    DEFAULT_INDICES: List[str] = [
        "^BVSP", "^GSPC",
        "USDBRL=X", "EURBRL=X",
        "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
    ]

    # Cache TTL in seconds
    CACHE_TTL: int = 300  # 5 minutes
    FETCH_DELAY_SECONDS: float = float(os.getenv("FETCH_DELAY_SECONDS", "1.5"))

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
