"""Market data service — fetches and caches financial data via yfinance."""

import logging
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf

from app.models.schemas import IndexQuote, IndexHistory, IndexHistoryPoint
from app.utils.cache import SimpleCache

logger = logging.getLogger(__name__)


class MarketDataService:
    """Service for fetching market data from Yahoo Finance."""

    def __init__(self, cache_ttl: int = 300):
        self._cache = SimpleCache(ttl=cache_ttl)

    def invalidate_cache(self, symbol: str) -> None:
        """Clear cached data for a given symbol."""
        keys_to_remove = [
            k for k in self._cache._store
            if symbol in k
        ]
        for key in keys_to_remove:
            del self._cache._store[key]

    async def get_quote(self, symbol: str, force_refresh: bool = False) -> IndexQuote:
        """Fetch current quote for an index from Yahoo Finance.

        Args:
            symbol: Yahoo Finance ticker (e.g. ^BVSP, ^GSPC, USDBRL=X).

        Returns:
            IndexQuote with current market data.
        """
        cache_key = f"quote:{symbol}"
        if not force_refresh:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
            previous_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0.0
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
            logger.warning(f"Yahoo Finance error for {symbol}: {e}")
            # Fallback: try to get latest data from DB
            try:
                from app.models.db import get_session, IndexQuoteModel
                session = get_session()
                latest = session.query(IndexQuoteModel).filter(
                    IndexQuoteModel.symbol == symbol
                ).order_by(IndexQuoteModel.fetched_at.desc()).first()
                if latest and latest.price > 0:
                    logger.info(f"Using cached DB data for {symbol}: {latest.price}")
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
                logger.warning(f"DB fallback also failed for {symbol}: {db_err}")

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
        """Fetch historical data for an index from Yahoo Finance.

        Args:
            symbol: Yahoo Finance ticker.
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 5y, max).
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 1d, 1wk, 1mo).

        Returns:
            IndexHistory with list of data points.
        """
        cache_key = f"history:{symbol}:{period}:{interval}"
        if not force_refresh:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)

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
            logger.warning(f"Yahoo Finance history error for {symbol}: {e}")
            return IndexHistory(
                symbol=symbol,
                period=period,
                interval=interval,
                data=[],
            )


# Singleton instance
market_data_service = MarketDataService()
