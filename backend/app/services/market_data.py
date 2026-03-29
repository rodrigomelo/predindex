"""Market data service — serves data from DB, with optional yfinance refresh.

Architecture: Pipeline fetches → DB stores → This service reads from DB.
External API calls only happen when force_refresh=True (manual trigger).
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from app.models.schemas import IndexQuote, IndexHistory, IndexHistoryPoint
from app.utils.cache import SimpleCache

logger = logging.getLogger(__name__)

# Rate limit guard for optional refresh calls
_LAST_REQUEST_TIME = 0.0
_MIN_REQUEST_INTERVAL = 5.0


async def _rate_limit_guard():
    """Ensure minimum delay between Yahoo Finance API calls."""
    global _LAST_REQUEST_TIME
    elapsed = time.time() - _LAST_REQUEST_TIME
    if elapsed < _MIN_REQUEST_INTERVAL:
        await asyncio.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _LAST_REQUEST_TIME = time.time()


def _read_quote_from_db(symbol: str) -> Optional[IndexQuote]:
    """Read latest quote from SQLite database."""
    try:
        from app.models.db import get_session, IndexQuoteModel
        session = get_session()
        latest = session.query(IndexQuoteModel).filter(
            IndexQuoteModel.symbol == symbol
        ).order_by(IndexQuoteModel.fetched_at.desc()).first()
        if latest and latest.price and latest.price > 0:
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
    except Exception as e:
        logger.debug(f"DB read failed for {symbol}: {e}")
    return None


def _read_history_from_db(symbol: str, period: str, interval: str) -> IndexHistory:
    """Read historical data from SQLite database."""
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
    except Exception as e:
        logger.debug(f"History DB read failed for {symbol}: {e}")
    return IndexHistory(symbol=symbol, period=period, interval=interval, data=[])


class MarketDataService:
    """Service for reading market data from DB with optional live refresh.

    By default, all data is served from the local SQLite database.
    Use force_refresh=True to trigger a live fetch from Yahoo Finance
    (this should only be called by the pipeline or manual refresh).
    """

    def __init__(self):
        self._cache = SimpleCache(ttl=600)

    def invalidate_cache(self, symbol: str) -> None:
        """Clear cached data for a given symbol."""
        keys_to_remove = [k for k in self._cache._store if symbol in k]
        for key in keys_to_remove:
            del self._cache._store[key]

    async def get_quote(self, symbol: str, force_refresh: bool = False) -> IndexQuote:
        """Get latest quote — reads from DB by default, optionally refreshes from Yahoo."""
        cache_key = f"quote:{symbol}"

        # 1. Check in-memory cache
        if not force_refresh:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        # 2. If force_refresh, try Yahoo Finance
        if force_refresh:
            quote = await self._fetch_from_yahoo(symbol)
            if quote:
                self._cache.set(cache_key, quote)
                return quote

        # 3. Read from DB (primary source)
        db_quote = _read_quote_from_db(symbol)
        if db_quote:
            self._cache.set(cache_key, db_quote)
            return db_quote

        # 4. No data available
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
        """Get historical data — reads from DB by default."""
        cache_key = f"history:{symbol}:{period}:{interval}"

        if not force_refresh:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        if force_refresh:
            history = await self._fetch_history_from_yahoo(symbol, period, interval)
            if history.data:
                self._cache.set(cache_key, history)
                return history

        # Read from DB
        history = _read_history_from_db(symbol, period, interval)
        self._cache.set(cache_key, history)
        return history

    async def _fetch_from_yahoo(self, symbol: str) -> Optional[IndexQuote]:
        """Fetch quote from Yahoo Finance (only for manual refresh)."""
        try:
            import yfinance as yf
            await _rate_limit_guard()
            ticker = yf.Ticker(symbol)
            info = ticker.info

            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
            previous_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0.0

            if current_price <= 0:
                return None

            change = current_price - previous_close if previous_close else 0.0
            change_percent = (change / previous_close * 100) if previous_close else 0.0

            return IndexQuote(
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
        except Exception as e:
            logger.warning(f"Yahoo Finance fetch failed for {symbol}: {e}")
            return None

    async def _fetch_history_from_yahoo(self, symbol: str, period: str, interval: str) -> IndexHistory:
        """Fetch history from Yahoo Finance (only for manual refresh)."""
        try:
            import yfinance as yf
            await _rate_limit_guard()
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)

            if df.empty:
                return IndexHistory(symbol=symbol, period=period, interval=interval, data=[])

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
            return IndexHistory(symbol=symbol, period=period, interval=interval, data=data_points)
        except Exception as e:
            logger.warning(f"Yahoo Finance history failed for {symbol}: {e}")
            return IndexHistory(symbol=symbol, period=period, interval=interval, data=[])


# Singleton instance
market_data_service = MarketDataService()
