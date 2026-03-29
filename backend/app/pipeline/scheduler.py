"""Pipeline scheduler — APScheduler-based data fetch automation."""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.models.db import get_session
from app.pipeline.fetcher import DataFetcher

logger = logging.getLogger(__name__)

# ── Scheduler ───────────────────────────────────────────────────


class PipelineScheduler:
    """Manages periodic data fetching jobs."""

    def __init__(self):
        self._scheduler = BackgroundScheduler()
        self._fetcher: DataFetcher | None = None

    def _get_fetcher(self) -> DataFetcher:
        if self._fetcher is None:
            self._fetcher = DataFetcher(get_session())
        return self._fetcher

    def _fetch_job(self):
        """Periodic job: fetch all default indices."""
        fetcher = self._get_fetcher()
        logger.info(f"[{datetime.utcnow()}] Pipeline job starting...")
        try:
            results = fetcher.fetch_all_default()
            for symbol, data in results.items():
                logger.info(
                    f"  {symbol}: quote={data['quote'] is not None}, "
                    f"history_points={data['history']}"
                )
        except Exception as e:
            logger.error(f"Pipeline job failed: {e}")

    def start(self):
        """Start the scheduler with configured jobs."""
        # Primary fetch: every 15 minutes
        self._scheduler.add_job(
            self._fetch_job,
            trigger=IntervalTrigger(minutes=15),
            id="fetch_all_indices",
            name="Fetch all default indices",
            replace_existing=True,
        )

        # EOD fetch: once per day at market close (19:00 BRT = 22:00 UTC)
        self._scheduler.add_job(
            self._fetch_job,
            trigger=IntervalTrigger(hours=24),
            id="fetch_eod_indices",
            name="Fetch EOD data",
            replace_existing=True,
        )

        self._scheduler.start()
        logger.info("Pipeline scheduler started.")

    def stop(self):
        """Stop the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Pipeline scheduler stopped.")

    def trigger_now(self):
        """Manually trigger an immediate fetch."""
        self._fetch_job()


# Singleton instance
_pipeline_scheduler: PipelineScheduler | None = None


def get_pipeline_scheduler() -> PipelineScheduler:
    global _pipeline_scheduler
    if _pipeline_scheduler is None:
        _pipeline_scheduler = PipelineScheduler()
    return _pipeline_scheduler
