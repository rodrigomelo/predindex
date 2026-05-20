"""Pipeline scheduler — APScheduler-based data fetch automation."""

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.pipeline.fetcher import DataFetcher

logger = logging.getLogger(__name__)


class PipelineScheduler:
    """Manages periodic data fetching jobs."""

    def __init__(self):
        self._scheduler = BackgroundScheduler()

    def _fetch_job(self):
        """Periodic job: fetch all default indices from Yahoo Finance."""
        logger.info(f"[{datetime.now(timezone.utc)}] Pipeline job starting...")
        try:
            fetcher = DataFetcher()
            results = fetcher.fetch_all_default()
            for symbol, data in results.items():
                logger.info(
                    f"  {symbol}: quote={data['quote'] is not None}, "
                    f"history_points={data['history']}"
                )
        except Exception as e:
            logger.error(f"Pipeline job failed: {e}")

    def _ifix_scrape_job(self):
        """Periodic job: scrape IFIX from StatusInvest."""
        logger.info(f"[{datetime.now(timezone.utc)}] IFIX scrape job starting...")
        try:
            from app.pipeline.scrapers.ifix_statusinvest import refresh_ifix_data

            count = asyncio.run(refresh_ifix_data(period="6 meses"))
            logger.info(f"  IFIX scrape: {count} records stored")
        except Exception as e:
            logger.error(f"IFIX scrape job failed: {e}")

    def start(self):
        """Start the scheduler with configured jobs."""
        # Primary fetch: every 15 minutes (Yahoo Finance)
        self._scheduler.add_job(
            self._fetch_job,
            trigger=IntervalTrigger(minutes=15),
            id="fetch_all_indices",
            name="Fetch all default indices",
            replace_existing=True,
        )

        # IFIX scrape: once per day (StatusInvest)
        self._scheduler.add_job(
            self._ifix_scrape_job,
            trigger=IntervalTrigger(hours=24),
            id="scrape_ifix",
            name="Scrape IFIX from StatusInvest",
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
        """Manually trigger an immediate fetch (blocking — call from executor)."""
        self._fetch_job()
        self._ifix_scrape_job()


# Singleton instance
_pipeline_scheduler: PipelineScheduler | None = None


def get_pipeline_scheduler() -> PipelineScheduler:
    global _pipeline_scheduler
    if _pipeline_scheduler is None:
        _pipeline_scheduler = PipelineScheduler()
    return _pipeline_scheduler
