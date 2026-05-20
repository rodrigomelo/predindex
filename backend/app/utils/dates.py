"""Date/time utility functions.

Provides timezone-aware datetime helpers for consistent time handling.
Import and use instead of raw datetime.now() calls.
"""

from datetime import datetime, timezone


def now_utc() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def now_brazil() -> datetime:
    """Return current Brazil (America/Sao_Paulo) datetime."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Sao_Paulo")
    return datetime.now(tz)
