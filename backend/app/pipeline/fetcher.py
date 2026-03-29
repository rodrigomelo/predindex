"""Data fetcher — Yahoo Finance integration via yfinance.

Fetches quotes and historical data for tracked indices.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db import (
    IndexHistoryModel,
    IndexQuoteModel,
    get_session,
)

logger = logging.getLogger(__name__)

# ── Ticker Mapping ───────────────────────────────────────────────


TICKER_MAP: dict[str, str] = {
    "^BVSP": "Ibovespa",
    "^GSPC": "S&P 500",
    "^IFIX": "IFIX",
    "USDBRL=X": "USD/BRL",
    "EURBRL=X": "EUR/BRL",
}


INTERVAL_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "1d": "1d",
}

PERIOD_MAP: dict[str, str] = {
    "1d": "1d",
    "5d": "5d",
    "1mo": "1mo",
    "3mo": "3mo",
    "6mo": "6mo",
    "1y": "1y",
    "5y": "5y",
}


# ── DataFetcher ──────────────────────────────────────────────────


class DataFetcher:
    """Fetches market data from Yahoo Finance."""

    def __init__(self, db_session: Optional[Session] = None):
        self._db_session = db_session

    @property
    def db(self) -> Session:
        if self._db_session is None:
            self._db_session = get_session()
        return self._db_session

    def fetch_quote(self, symbol: str) -> Optional[IndexQuoteModel]:
        """Fetch and store the latest quote for a symbol."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info

            quote = IndexQuoteModel(
                symbol=symbol,
                price=info.last_price or 0.0,
                change=info.last_price - (info.previous_close or info.last_price or 0),
                change_percent=(
                    ((info.last_price - (info.previous_close or info.last_price)) / info.previous_close * 100)
                    if info.previous_close and info.previous_close > 0
                    else 0.0
                ),
                volume=int(info.last_volume or 0),
                high=info.day_high or None,
                low=info.day_low or None,
                open_price=info.open or None,
                previous_close=info.previous_close or None,
                currency=getattr(info, "currency", "USD"),
                exchange=getattr(info, "exchange", None),
                fetched_at=datetime.utcnow(),
            )

            self.db.add(quote)
            self.db.commit()
            logger.info(f"Quote fetched: {symbol} @ {quote.price}")
            return quote

        except Exception as e:
            logger.error(f"Failed to fetch quote for {symbol}: {e}")
            self.db.rollback()
            return None

    def fetch_history(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> list[IndexHistoryModel]:
        """Fetch and store historical OHLCV data for a symbol."""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)

            if hist.empty:
                logger.warning(f"No history data for {symbol}")
                return []

            models = []
            for dt, row in hist.iterrows():
                model = IndexHistoryModel(
                    symbol=symbol,
                    date=dt.to_pydatetime() if hasattr(dt, "to_pydatetime") else dt,
                    open_price=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
                    interval=interval,
                    fetched_at=datetime.utcnow(),
                )
                models.append(model)

            # Upsert: replace history for this symbol + interval
            self.db.query(IndexHistoryModel).filter(
                IndexHistoryModel.symbol == symbol,
                IndexHistoryModel.interval == interval,
            ).delete()

            self.db.add_all(models)
            self.db.commit()
            logger.info(f"History fetched: {symbol} ({len(models)} points, {interval})")
            return models

        except Exception as e:
            logger.error(f"Failed to fetch history for {symbol}: {e}")
            self.db.rollback()
            return []

    def fetch_all_default(self) -> dict[str, list]:
        """Fetch quotes and history for all default indices."""
        results = {}
        for symbol in settings.DEFAULT_INDICES:
            quote = self.fetch_quote(symbol)
            history = self.fetch_history(symbol, period="1mo", interval="1d")
            results[symbol] = {"quote": quote, "history": len(history)}
        return results

    def close(self):
        """Close the database session."""
        if self._db_session:
            self._db_session.close()
            self._db_session = None
