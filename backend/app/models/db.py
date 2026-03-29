"""SQLAlchemy database models for PredIndex time-series data."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# ── Engine & Session ────────────────────────────────────────────

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
        )
    return _engine


def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal()


Base = declarative_base()


# ── Models ──────────────────────────────────────────────────────


class IndexQuoteModel(Base):
    """Latest quote for an index."""

    __tablename__ = "index_quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    price = Column(Float, nullable=False)
    change = Column(Float, default=0.0)
    change_percent = Column(Float, default=0.0)
    volume = Column(Integer, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    open_price = Column("open", Float, nullable=True)
    previous_close = Column(Float, nullable=True)
    currency = Column(String(10), default="USD")
    exchange = Column(String(50), nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<IndexQuoteModel(symbol={self.symbol}, price={self.price}, fetched_at={self.fetched_at})>"


class IndexHistoryModel(Base):
    """Historical OHLCV data point for an index."""

    __tablename__ = "index_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    open_price = Column("open", Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=True)
    interval = Column(String(10), default="1d", nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        # Composite unique constraint: symbol + date + interval
        # (use unique() method for SQLite compatibility)
    )

    def __repr__(self):
        return f"<IndexHistoryModel(symbol={self.symbol}, date={self.date}, close={self.close})>"


class TechnicalIndicatorModel(Base):
    """Cached technical indicators for an index."""

    __tablename__ = "technical_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    indicator_name = Column(String(50), nullable=False)
    value = Column(Float, nullable=False)
    period = Column(String(20), nullable=True)
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<TechnicalIndicatorModel(symbol={self.symbol}, name={self.indicator_name}, value={self.value})>"


# ── Schema Init ─────────────────────────────────────────────────


def init_db():
    """Create all tables if they don't exist."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
