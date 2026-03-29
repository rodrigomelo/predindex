"""Cache utility — simple in-memory cache with TTL."""

import time
from typing import Any, Optional


class SimpleCache:
    """Simple in-memory cache with time-to-live support."""

    def __init__(self, ttl: int = 300):
        self._store: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache if not expired."""
        if key in self._store:
            value, timestamp = self._store[key]
            if time.time() - timestamp < self._ttl:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set a value in cache."""
        self._store[key] = (value, time.time())

    def clear(self) -> None:
        """Clear all cached values."""
        self._store.clear()
