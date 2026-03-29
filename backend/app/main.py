"""FastAPI application entry point — PredIndex Backend."""

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.api import routes
from app.models.db import init_db
from app.pipeline.scheduler import get_pipeline_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    global _start_time
    _start_time = time.time()

    logger.info(f"🔨 {settings.APP_NAME} v{settings.APP_VERSION} starting...")

    # Ensure data directory exists
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    logger.info(f"   Data directory: {data_dir}")

    # Initialize database
    try:
        init_db()
        logger.info("   Database initialized.")
    except Exception as e:
        logger.error(f"   Database init failed: {e}")

    # Start pipeline scheduler
    if settings.YAHOO_FINANCE_ENABLED:
        try:
            scheduler = get_pipeline_scheduler()
            scheduler.start()
            logger.info("   Pipeline scheduler started.")
        except Exception as e:
            logger.error(f"   Pipeline scheduler failed to start: {e}")

    logger.info(f"   Port: {settings.PORT}")
    logger.info(f"   Debug: {settings.DEBUG}")
    logger.info(f"   Default indices: {settings.DEFAULT_INDICES}")

    yield

    # Shutdown
    logger.info(f"🔨 {settings.APP_NAME} shutting down...")
    try:
        scheduler = get_pipeline_scheduler()
        scheduler.stop()
    except Exception:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Financial Index Analysis and Prediction Platform",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(routes.router)


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    from app.models.schemas import HealthResponse

    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        uptime_seconds=time.time() - _start_time,
    )


# ── Frontend Dashboard ──────────────────────────────────────────
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serve the PredIndex dashboard."""
    dashboard = FRONTEND_DIR / "index.html"
    if dashboard.exists():
        return FileResponse(dashboard)
    return {"message": "PredIndex API running. Dashboard not found."}


# Mount frontend static assets
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
