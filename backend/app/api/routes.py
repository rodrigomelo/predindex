"""API routes — PredIndex endpoints."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from app.core.config import settings
from app.models.schemas import (
    AnalysisResult,
    IndexHistory,
    IndexQuote,
    IndexInfo,
)
from app.services.market_data import market_data_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["indices"])

# Valid query param values
VALID_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "max"}
VALID_INTERVALS = {"1m", "5m", "15m", "1h", "1d"}

# ── Index Registry ──────────────────────────────────────────────

INDEX_REGISTRY: dict[str, IndexInfo] = {
    "^BVSP": IndexInfo(symbol="^BVSP", name="Ibovespa", currency="BRL", exchange="B3"),
    "^GSPC": IndexInfo(symbol="^GSPC", name="S&P 500", currency="USD", exchange="NYSE"),
    "IFIX.SA": IndexInfo(symbol="IFIX.SA", name="IFIX", currency="BRL", exchange="B3"),
    "USDBRL=X": IndexInfo(symbol="USDBRL=X", name="USD/BRL", currency="BRL", exchange="Forex"),
    "EURBRL=X": IndexInfo(symbol="EURBRL=X", name="EUR/BRL", currency="BRL", exchange="Forex"),
    "BTC-USD": IndexInfo(symbol="BTC-USD", name="Bitcoin", currency="USD", exchange="Crypto"),
    "ETH-USD": IndexInfo(symbol="ETH-USD", name="Ethereum", currency="USD", exchange="Crypto"),
    "SOL-USD": IndexInfo(symbol="SOL-USD", name="Solana", currency="USD", exchange="Crypto"),
    "XRP-USD": IndexInfo(symbol="XRP-USD", name="Ripple", currency="USD", exchange="Crypto"),
}

INDEX_CATEGORIES: dict[str, list[str]] = {
    "markets": ["^BVSP", "^GSPC", "IFIX.SA"],
    "currencies": ["USDBRL=X", "EURBRL=X"],
    "cryptocurrencies": ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"],
}


# ── Endpoints ───────────────────────────────────────────────────


@router.get("/indices", response_model=list[IndexInfo])
async def list_indices():
    """List all available indices."""
    return list(INDEX_REGISTRY.values())


@router.get("/indices/categories")
async def list_categories():
    """List indices grouped by category."""
    result = {}
    for category, symbols in INDEX_CATEGORIES.items():
        result[category] = [INDEX_REGISTRY[s].model_dump() for s in symbols if s in INDEX_REGISTRY]
    return result


@router.get("/quotes", response_model=dict[str, IndexQuote])
async def get_all_quotes():
    """Get latest quotes for all tracked indices from DB cache."""
    quotes = {}
    for symbol in INDEX_REGISTRY:
        try:
            quote = await market_data_service.get_quote(symbol, force_refresh=False)
            quotes[symbol] = quote
        except Exception:
            quotes[symbol] = IndexQuote(
                symbol=symbol, price=0.0, change=0.0, change_percent=0.0,
                volume=None, high=None, low=None, open=None,
                previous_close=None, timestamp=datetime.now(timezone.utc),
            )
    return quotes


@router.get("/indices/{symbol}", response_model=IndexQuote)
async def get_index_quote(symbol: str, refresh: bool = Query(default=False)):
    """Get current quote for a specific index."""
    if symbol not in INDEX_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Index '{symbol}' not found")
    try:
        return await market_data_service.get_quote(symbol, force_refresh=refresh)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching quote for {symbol}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/indices/{symbol}/history", response_model=IndexHistory)
async def get_index_history(
    symbol: str,
    period: str = Query(default="1mo", description="Time period"),
    interval: str = Query(default="1d", description="Data interval"),
    refresh: bool = Query(default=False),
):
    """Get historical data for a specific index."""
    if symbol not in INDEX_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Index '{symbol}' not found")
    if period not in VALID_PERIODS:
        raise HTTPException(status_code=400, detail=f"Invalid period. Valid: {sorted(VALID_PERIODS)}")
    if interval not in VALID_INTERVALS:
        raise HTTPException(status_code=400, detail=f"Invalid interval. Valid: {sorted(VALID_INTERVALS)}")
    try:
        return await market_data_service.get_history(symbol, period=period, interval=interval, force_refresh=refresh)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching history for {symbol}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/indices/{symbol}/refresh")
async def refresh_index_data(symbol: str):
    """Force refresh of all data for an index."""
    if symbol not in INDEX_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Index '{symbol}' not found")
    try:
        market_data_service.invalidate_cache(symbol)
        quote = await market_data_service.get_quote(symbol, force_refresh=True)
        history = await market_data_service.get_history(symbol, force_refresh=True)
        return {"status": "ok", "symbol": symbol, "quote": quote, "history_points": len(history.data)}
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception(f"Error refreshing {symbol}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/analysis/{symbol}", response_model=AnalysisResult)
async def analyze_index(symbol: str, period: str = Query(default="3mo")):
    """Run technical analysis on a specific index."""
    if symbol not in INDEX_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Index '{symbol}' not found")
    try:
        from app.analysis.technical import TechnicalAnalyzer
        analyzer = TechnicalAnalyzer()
        return await analyzer.analyze(symbol, period=period)
    except Exception as e:
        logger.exception(f"Error analyzing {symbol}")
        raise HTTPException(status_code=500, detail="Internal server error")


def _verify_api_key(x_api_key: Optional[str]) -> None:
    """Verify admin API key if configured."""
    if not settings.ADMIN_API_KEY:
        return  # No key configured — skip auth
    if x_api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/pipeline/trigger")
async def trigger_pipeline(x_api_key: Optional[str] = Header(default=None)):
    """Manually trigger the data pipeline fetch."""
    _verify_api_key(x_api_key)
    try:
        from app.pipeline.scheduler import get_pipeline_scheduler
        scheduler = get_pipeline_scheduler()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, scheduler.trigger_now)
        return {"status": "ok", "message": "Pipeline triggered"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error triggering pipeline")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/pipeline/status")
async def pipeline_status():
    """Get current pipeline status."""
    try:
        from app.pipeline.scheduler import get_pipeline_scheduler
        scheduler = get_pipeline_scheduler()
        running = scheduler._scheduler.running if scheduler else False
    except Exception:
        running = False

    return {
        "status": "running" if running else "stopped",
        "scheduler_enabled": settings.YAHOO_FINANCE_ENABLED,
        "indices": settings.DEFAULT_INDICES,
    }
