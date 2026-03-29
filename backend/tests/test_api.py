"""Tests for PredIndex Backend — API endpoints with mocked market data."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone

from app.main import app
from app.models.schemas import IndexQuote, IndexHistory


# ── Fixtures ────────────────────────────────────────────────────

MOCK_QUOTE = IndexQuote(
    symbol="^BVSP",
    price=125000.50,
    change=1200.30,
    change_percent=0.97,
    volume=150000000,
    high=125500.00,
    low=123800.00,
    open=124000.00,
    previous_close=123800.20,
    timestamp=datetime.now(timezone.utc),
)

MOCK_HISTORY = IndexHistory(
    symbol="^GSPC",
    period="1mo",
    interval="1d",
    data=[],
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_market_data():
    """Mock the market data service for all tests."""
    with patch("app.api.routes.market_data_service") as mock_service:
        mock_service.get_quote = AsyncMock(return_value=MOCK_QUOTE)
        mock_service.get_history = AsyncMock(return_value=MOCK_HISTORY)
        mock_service.invalidate_cache = MagicMock()
        yield mock_service


@pytest.fixture
def mock_analyzer():
    """Mock the technical analyzer."""
    from app.models.schemas import AnalysisResult
    mock_result = AnalysisResult(
        symbol="^BVSP",
        timestamp=datetime.now(timezone.utc),
        trend="upward",
        recommendation="buy",
        confidence=0.75,
        indicators={"rsi_14": 45.2, "macd": 120.5},
        notes="Mock analysis",
    )
    mock_instance = MagicMock()
    mock_instance.analyze = AsyncMock(return_value=mock_result)
    with patch("app.analysis.technical.TechnicalAnalyzer", return_value=mock_instance):
        yield mock_instance


# ── Tests ───────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_health_check():
    """Test the health check endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


@pytest.mark.anyio
async def test_list_indices():
    """Test listing available indices."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/indices")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    symbols = [idx["symbol"] for idx in data]
    assert "^BVSP" in symbols
    assert "^GSPC" in symbols
    assert "IFIX.SA" in symbols


@pytest.mark.anyio
async def test_get_index_quote(mock_market_data):
    """Test getting a quote for a specific index."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/indices/^BVSP")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "^BVSP"
    assert data["price"] == 125000.50


@pytest.mark.anyio
async def test_get_index_quote_not_found():
    """Test getting a quote for an unknown index."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/indices/INVALID")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_index_history(mock_market_data):
    """Test getting historical data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/indices/^GSPC/history")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "^GSPC"


@pytest.mark.anyio
async def test_get_index_history_with_params(mock_market_data):
    """Test getting historical data with custom period and interval."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/indices/^GSPC/history?period=3mo&interval=1h")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_analyze_index(mock_analyzer):
    """Test analysis endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/analysis/^BVSP")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "^BVSP"
    assert data["trend"] == "upward"
    assert data["recommendation"] == "buy"
    assert data["confidence"] == 0.75


@pytest.mark.anyio
async def test_analyze_index_not_found():
    """Test analysis for an unknown index."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/analysis/INVALID")
    assert response.status_code == 404
