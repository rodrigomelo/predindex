"""API routes — PredIndex endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.models.schemas import (
    AnalysisResult,
    IndexHistory,
    IndexHistoryPoint,
    IndexInfo,
    IndexQuote,
)
from app.services.market_data import market_data_service

router = APIRouter(prefix="/api/v1", tags=["indices"])

# ── Index Registry ──────────────────────────────────────────────

INDEX_REGISTRY: dict[str, IndexInfo] = {
    "^BVSP": IndexInfo(
        symbol="^BVSP", name="Ibovespa", currency="BRL", exchange="B3"
    ),
    "^GSPC": IndexInfo(
        symbol="^GSPC", name="S&P 500", currency="USD", exchange="NYSE"
    ),
    "IFIX.SA": IndexInfo(
        symbol="IFIX.SA", name="IFIX", currency="BRL", exchange="B3"
    ),
    "USDBRL=X": IndexInfo(
        symbol="USDBRL=X", name="USD/BRL", currency="BRL", exchange="Forex"
    ),
    "EURBRL=X": IndexInfo(
        symbol="EURBRL=X", name="EUR/BRL", currency="BRL", exchange="Forex"
    ),
}


# ── Endpoints ───────────────────────────────────────────────────


@router.get("/indices", response_model=list[IndexInfo])
async def list_indices():
    """List all available indices."""
    return list(INDEX_REGISTRY.values())


@router.get("/indices/{symbol}", response_model=IndexQuote)
async def get_index_quote(symbol: str, refresh: bool = Query(default=False, description="Force fresh fetch")):
    """Get current quote for a specific index."""
    if symbol not in INDEX_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Index '{symbol}' not found")

    try:
        quote = await market_data_service.get_quote(symbol, force_refresh=refresh)
        return quote
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/indices/{symbol}/history", response_model=IndexHistory)
async def get_index_history(
    symbol: str,
    period: str = Query(default="1mo", description="Time period (1d,5d,1mo,3mo,6mo,1y)"),
    interval: str = Query(default="1d", description="Data interval (1m,5m,15m,1h,1d)"),
    refresh: bool = Query(default=False, description="Force fresh fetch"),
):
    """Get historical data for a specific index."""
    if symbol not in INDEX_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Index '{symbol}' not found")

    try:
        history = await market_data_service.get_history(
            symbol, period=period, interval=interval, force_refresh=refresh
        )
        return history
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/indices/{symbol}/refresh")
async def refresh_index_data(symbol: str):
    """Force refresh of all data for an index."""
    if symbol not in INDEX_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Index '{symbol}' not found")

    try:
        market_data_service.invalidate_cache(symbol)
        quote = await market_data_service.get_quote(symbol, force_refresh=True)
        history = await market_data_service.get_history(symbol, force_refresh=True)
        return {
            "status": "ok",
            "symbol": symbol,
            "quote": quote,
            "history_points": len(history.data),
        }
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/analysis/{symbol}", response_model=AnalysisResult)
async def analyze_index(
    symbol: str,
    period: str = Query(default="3mo", description="Analysis period"),
):
    """Run analysis on a specific index."""
    if symbol not in INDEX_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Index '{symbol}' not found")

    try:
        # Import here to avoid circular dependency
        from app.analysis.technical import TechnicalAnalyzer

        analyzer = TechnicalAnalyzer()
        result = await analyzer.analyze(symbol, period=period)
        return result
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/pipeline/trigger")
async def trigger_pipeline():
    """Manually trigger the data pipeline fetch."""
    try:
        from app.pipeline.scheduler import get_pipeline_scheduler

        scheduler = get_pipeline_scheduler()
        scheduler.trigger_now()
        return {"status": "ok", "message": "Pipeline triggered"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/pipeline/status")
async def pipeline_status():
    """Get current pipeline status."""
    from app.core.config import settings

    try:
        from app.pipeline.scheduler import get_pipeline_scheduler
        scheduler = get_pipeline_scheduler()
        running = scheduler.is_running() if hasattr(scheduler, "is_running") else True
        last_run = getattr(scheduler, "_last_run", None)
    except Exception:
        running = False
        last_run = None

    return {
        "status": "running" if running else "stopped",
        "scheduler_enabled": settings.YAHOO_FINANCE_ENABLED,
        "indices": settings.DEFAULT_INDICES,
        "last_run": last_run,
    }
