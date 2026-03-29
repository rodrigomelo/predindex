"""Data models and schemas for PredIndex."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class IndexInfo(BaseModel):
    """Basic information about a financial index."""

    symbol: str = Field(..., description="Ticker symbol (e.g. ^BVSP)")
    name: str = Field(..., description="Human-readable name")
    currency: str = Field(default="USD", description="Quote currency")
    exchange: Optional[str] = Field(default=None, description="Exchange name")


class IndexQuote(BaseModel):
    """Current quote data for an index."""

    symbol: str
    price: float
    change: float
    change_percent: float
    volume: Optional[int] = None
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    previous_close: Optional[float] = None
    timestamp: datetime


class IndexHistoryPoint(BaseModel):
    """Single data point in historical data."""

    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int] = None


class IndexHistory(BaseModel):
    """Historical data for an index."""

    symbol: str
    period: str
    interval: str
    data: list[IndexHistoryPoint]


class AnalysisResult(BaseModel):
    """Analysis output for a given index."""

    symbol: str
    timestamp: datetime
    trend: str = Field(..., description="upward, downward, or neutral")
    recommendation: str = Field(..., description="buy, sell, or hold")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    indicators: dict = Field(default_factory=dict, description="Technical indicators")
    notes: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str
    uptime_seconds: float
