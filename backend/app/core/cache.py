"""Cache / ephemeral store.

Prod uses Redis (settings.redis_url) for session context, rate limits and a
simple job queue. For the keyless dev run we fall back to a process-local
in-memory cache with TTL semantics. Same interface either way.
"""
from __future__ import annotations

import time
from threading import RLock

from app.config import settings


class InMemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float | None, object]] = {}
        # Reentrant: some methods (incr) read state while already holding the lock.
        self._lock = RLock()

    def get(self, key: str):
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires, value = item
            if expires is not None and expires < time.time():
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value, ttl: int | None = None) -> None:
        with self._lock:
            expires = time.time() + ttl if ttl else None
            self._data[key] = (expires, value)

    def incr(self, key: str, ttl: int | None = None) -> int:
        """Fixed-window counter: the first increment sets the TTL; subsequent
        increments within the window keep the original expiry (so a 60s window
        actually expires after 60s rather than sliding forever)."""
        with self._lock:
            now = time.time()
            item = self._data.get(key)
            if item and (item[0] is None or item[0] >= now):
                expires, cur = item[0], int(item[1]) + 1
            else:
                expires, cur = (now + ttl if ttl else None), 1
            self._data[key] = (expires, cur)
            return cur

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


_cache: InMemoryCache | None = None


def get_cache() -> InMemoryCache:
    """Return the shared cache. (Swap for a Redis-backed impl when redis_url set.)"""
    global _cache
    if _cache is None:
        # if settings.redis_url: return RedisCache(settings.redis_url)
        _cache = InMemoryCache()
    return _cache
