"""Market data service — fetches and caches financial data via yfinance.

Features:
- Retry with exponential backoff for Yahoo Finance rate limits
- DB fallback when API is unavailable
- Aggressive caching to minimize API calls
- Async-compatible with delay between requests
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf

from app.models.schemas import IndexQuote, IndexHistory, IndexHistoryPoint
from app.utils.cache import SimpleCache
logger = logging.getLogger(__name__)

# Rate limit guard — minimum seconds between Yahoo Finance requests
_LAST_REQUEST_TIME = 0.0
_MIN_REQUEST_INTERVAL = 3.0  # seconds between API calls


async def _rate_limit_guard():
    """Ensure minimum delay between Yahoo Finance API calls."""
    global _LAST_REQUEST_TIME
    elapsed = time.time() - _LAST_REQUEST_TIME
    if elapsed < _MIN_REQUEST_INTERVAL:
        wait = _MIN_REQUEST_INTERVAL - elapsed
        logger.debug(f"Rate limit guard: waiting {wait:.1f}s")
        await asyncio.sleep(wait)
    _LAST_REQUEST_TIME = time.time()


def _try_db_fallback(symbol: str) -> Optional[IndexQuote]:
    """Try to load latest quote from SQLite database."""
    try:
        from app.models.db import get_session, IndexQuoteModel
        session = get_session()
        latest = session.query(IndexQuoteModel).filter(
            IndexQuoteModel.symbol == symbol
        ).order_by(IndexQuoteModel.fetched_at.desc()).first()
        if latest and latest.price and latest.price > 0:
            logger.info(f"DB fallback for {symbol}: price={latest.price}")
            return IndexQuote(
                symbol=symbol,
                price=latest.price,
                change=latest.change,
                change_percent=latest.change_percent,
                volume=latest.volume,
                high=latest.high,
                low=latest.low,
                open=latest.open_price,
                previous_close=latest.previous_close,
                timestamp=latest.fetched_at,
            )
    except Exception as db_err:
        logger.debug(f"DB fallback not available for {symbol}: {db_err}")
    return None


def _try_history_db_fallback(symbol: str, period: str, interval: str) -> IndexHistory:
    """Try to load history from SQLite database."""
    try:
        from app.models.db import get_session, IndexHistoryModel
        session = get_session()
        points = session.query(IndexHistoryModel).filter(
            IndexHistoryModel.symbol == symbol
        ).order_by(IndexHistoryModel.date.asc()).limit(200).all()

        if points:
            data = [
                IndexHistoryPoint(
                    date=p.date.replace(tzinfo=timezone.utc) if p.date.tzinfo is None else p.date,
                    open=p.open_price,
                    high=p.high,
                    low=p.low,
                    close=p.close,
                    volume=p.volume,
                )
                for p in points
            ]
            return IndexHistory(symbol=symbol, period=period, interval=interval, data=data)
    except Exception as db_err:
        logger.debug(f"History DB fallback not available for {symbol}: {db_err}")
    return IndexHistory(symbol=symbol, period=period, interval=interval, data=[])


class MarketDataService:
    """Service for fetching market data from Yahoo Finance with retry and fallback."""

    def __init__(self):
        # Longer cache TTL (10 min) to reduce API calls
        self._cache = SimpleCache(ttl=600)

    def invalidate_cache(self, symbol: str) -> None:
        """Clear cached data for a given symbol."""
        keys_to_remove = [k for k in self._cache._store if symbol in k]
        for key in keys_to_remove:
            del self._cache._store[key]

    async def get_quote(self, symbol: str, force_refresh: bool = False) -> IndexQuote:
        """Fetch current quote with retry, rate limiting, and DB fallback."""
        cache_key = f"quote:{symbol}"
        if not force_refresh:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        max_retries = 3
        for attempt in range(max_retries):
            try:
                await _rate_limit_guard()
                ticker = yf.Ticker(symbol)
                info = ticker.info

                current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
                previous_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0.0

                if current_price <= 0:
                    # Yahoo returned empty data — retry
                    if attempt < max_retries - 1:
                        wait = (attempt + 1) * 5
                        logger.warning(f"Empty data for {symbol}, retrying in {wait}s (attempt {attempt+1}/{max_retries})")
                        await asyncio.sleep(wait)
                        continue
                    else:
                        raise ValueError(f"Yahoo Finance returned empty price for {symbol}")

                change = current_price - previous_close if previous_close else 0.0
                change_percent = (change / previous_close * 100) if previous_close else 0.0

                quote = IndexQuote(
                    symbol=symbol,
                    price=round(current_price, 2),
                    change=round(change, 2),
                    change_percent=round(change_percent, 2),
                    volume=info.get("regularMarketVolume"),
                    high=info.get("regularMarketDayHigh"),
                    low=info.get("regularMarketDayLow"),
                    open=info.get("regularMarketOpen"),
                    previous_close=round(previous_close, 2) if previous_close else None,
                    timestamp=datetime.now(timezone.utc),
                )
                self._cache.set(cache_key, quote)
                return quote

            except Exception as e:
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 5
                    logger.warning(f"Attempt {attempt+1}/{max_retries} failed for {symbol}: {e}. Retrying in {wait}s")
                    await asyncio.sleep(wait)
                else:
                    logger.warning(f"All retries exhausted for {symbol}: {e}")

        # All retries failed — try DB fallback
        db_quote = _try_db_fallback(symbol)
        if db_quote:
            return db_quote

        # Last resort — return zero quote
        return IndexQuote(
            symbol=symbol,
            price=0.0,
            change=0.0,
            change_percent=0.0,
            volume=None,
            high=None,
            low=None,
            open=None,
            previous_close=None,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_history(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
        force_refresh: bool = False,
    ) -> IndexHistory:
        """Fetch historical data with retry and DB fallback."""
        cache_key = f"history:{symbol}:{period}:{interval}"
        if not force_refresh:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        max_retries = 2
        for attempt in range(max_retries):
            try:
                await _rate_limit_guard()
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period, interval=interval)

                if df.empty:
                    if attempt < max_retries - 1:
                        await asyncio.sleep((attempt + 1) * 5)
                        continue
                    raise ValueError(f"Empty history for {symbol}")

                data_points = []
                for index, row in df.iterrows():
                    data_points.append(
                        IndexHistoryPoint(
                            date=index.to_pydatetime().replace(tzinfo=timezone.utc),
                            open=round(row["Open"], 2),
                            high=round(row["High"], 2),
                            low=round(row["Low"], 2),
                            close=round(row["Close"], 2),
                            volume=int(row["Volume"]) if row["Volume"] else None,
                        )
                    )

                history = IndexHistory(
                    symbol=symbol,
                    period=period,
                    interval=interval,
                    data=data_points,
                )
                self._cache.set(cache_key, history)
                return history

            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep((attempt + 1) * 5)
                else:
                    logger.warning(f"History fetch failed for {symbol}: {e}")

        # DB fallback
        return _try_history_db_fallback(symbol, period, interval)


# Singleton instance
market_data_service = MarketDataService()
