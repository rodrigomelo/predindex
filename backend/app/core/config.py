"""PredIndex — Core configuration and settings."""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = "PredIndex"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 5004

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5004"]

    # Database — use absolute path for SQLite to avoid working directory issues
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(_BASE_DIR, 'data', 'predindex.db')}")

    # External APIs
    YAHOO_FINANCE_ENABLED: bool = True
    ALPHA_VANTAGE_API_KEY: Optional[str] = os.getenv("ALPHA_VANTAGE_API_KEY")

    # Default indices to track
    DEFAULT_INDICES: List[str] = [
        "^BVSP", "^GSPC", "IFIX.SA",
        "USDBRL=X", "EURBRL=X",
        "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
    ]

    # Cache TTL in seconds
    CACHE_TTL: int = 300  # 5 minutes

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
