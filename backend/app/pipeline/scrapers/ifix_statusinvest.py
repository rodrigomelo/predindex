"""IFIX historical data scraper using StatusInvest via Playwright.

StatusInvest (https://statusinvest.com.br/indices/ifix) renders IFIX
chart data via ECharts. Yahoo Finance only has 1 data point for IFIX.SA,
so we scrape from StatusInvest as the primary source.

Usage:
    python -m app.pipeline.scrapers.ifix_statusinvest

Requires: playwright (pip install playwright && python -m playwright install chromium)
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

STATUSINVEST_URL = "https://statusinvest.com.br/indices/ifix"


async def fetch_ifix_daily(period: str = "6 meses") -> list[dict]:
    """Fetch IFIX daily data from StatusInvest using headless browser.

    Args:
        period: Chart period tab to click. Options: "1 dia", "5 dias",
                "30 dias", "6 meses", "1 ano", "5 anos"

    Returns:
        List of {"date": "YYYY-MM-DD", "close": float} dicts.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        try:
            logger.info(f"Loading StatusInvest IFIX page...")
            await page.goto(STATUSINVEST_URL, wait_until="load", timeout=30000)
            await page.wait_for_timeout(6000)

            # Click the desired period tab
            clicked = await page.evaluate(
                """(period) => {
                    const tabs = document.querySelectorAll('li.tab');
                    for (const tab of tabs) {
                        if (tab.textContent.trim() === period) {
                            tab.querySelector('a')?.click();
                            return true;
                        }
                    }
                    return false;
                }""",
                period,
            )

            if not clicked:
                logger.warning(f"Period tab '{period}' not found, using default chart")
            else:
                await page.wait_for_timeout(5000)

            # Extract daily chart data (the one without time in dates)
            daily_data = await page.evaluate(
                """() => {
                    const charts = document.querySelectorAll('div[_echarts_instance_]');
                    for (const chart of charts) {
                        const instance = window.echarts.getInstanceByDom(chart);
                        if (instance) {
                            const option = instance.getOption();
                            const xData = option.xAxis?.[0]?.data || [];
                            const yData = option.series?.[0]?.data || [];
                            const hasTime = xData.some(x => String(x).includes(':'));
                            if (!hasTime && xData.length > 5) {
                                return { dates: xData, prices: yData, count: xData.length };
                            }
                        }
                    }
                    return null;
                }"""
            )

            if not daily_data:
                logger.warning("No daily chart data found on page")
                return []

            records = []
            for date_str, price in zip(daily_data["dates"], daily_data["prices"]):
                try:
                    dt = datetime.strptime(date_str, "%d/%m/%y")
                    records.append({"date": dt.strftime("%Y-%m-%d"), "close": float(price)})
                except (ValueError, TypeError) as e:
                    logger.debug(f"Skipping malformed data point: {date_str} = {price} ({e})")

            logger.info(f"Scraped {len(records)} IFIX daily data points from StatusInvest")
            return records

        finally:
            await browser.close()


def store_ifix_history(records: list[dict]) -> int:
    """Store scraped IFIX records into the database.

    Returns the number of records stored.
    """
    from app.models.db import get_session, IndexHistoryModel

    if not records:
        return 0

    session = get_session()

    # Clear existing IFIX history
    session.query(IndexHistoryModel).filter(IndexHistoryModel.symbol == "IFIX.SA").delete()

    for r in records:
        dt = datetime.strptime(r["date"], "%Y-%m-%d")
        rec = IndexHistoryModel(
            symbol="IFIX.SA",
            date=dt,
            open_price=r["close"],
            high=r["close"],
            low=r["close"],
            close=r["close"],
            volume=None,
            interval="1d",
            fetched_at=datetime.utcnow(),
        )
        session.add(rec)

    # Update quote
    latest = records[-1]
    prev = records[-2] if len(records) > 1 else records[-1]
    price = latest["close"]
    prev_close = prev["close"]
    change = price - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0

    from app.models.db import IndexQuoteModel

    session.query(IndexQuoteModel).filter(IndexQuoteModel.symbol == "IFIX.SA").delete()
    session.add(
        IndexQuoteModel(
            symbol="IFIX.SA",
            price=round(price, 2),
            change=round(change, 2),
            change_percent=round(change_pct, 2),
            volume=None,
            high=round(price, 2),
            low=round(price, 2),
            open_price=round(price, 2),
            previous_close=round(prev_close, 2),
            fetched_at=datetime.utcnow(),
        )
    )

    session.commit()
    return len(records)


async def refresh_ifix_data(period: str = "1 ano") -> int:
    """Fetch and store IFIX data in one call. Returns records stored."""
    records = await fetch_ifix_daily(period=period)
    if records:
        count = store_ifix_history(records)
        logger.info(f"IFIX refresh complete: {count} records stored")
        return count
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    records = asyncio.run(fetch_ifix_daily(period="6 meses"))
    if records:
        count = store_ifix_history(records)
        print(f"Stored {count} IFIX records")
    else:
        print("No data scraped")
