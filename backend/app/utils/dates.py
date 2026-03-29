"""Date/time utility functions."""

from datetime import datetime, timezone


def now_utc() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def now_brazil() -> datetime:
    """Return current Brazil (America/Sao_Paulo) datetime."""
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Sao_Paulo")
    return datetime.now(tz)
