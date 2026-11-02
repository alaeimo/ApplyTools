"""Async rate limiter. Combines a concurrency semaphore (max in-flight) with
an optional minimum interval between requests (per-host)."""
from __future__ import annotations

import asyncio
from typing import Optional


class RateLimiter:
    """Two-axis limiter:
      1. `max_concurrency` — bounds parallel in-flight requests
      2. `min_interval` — guarantees at least N seconds between starts (per host)

    Usage:
        limiter = RateLimiter(max_concurrency=5, min_interval=1.0)
        async with limiter:
            ...
    """

    def __init__(self, max_concurrency: int = 5, min_interval: float = 0.0):
        self._sem = asyncio.Semaphore(max_concurrency)
        self._min_interval = min_interval
        self._last_start = 0.0
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "RateLimiter":
        await self._sem.acquire()
        if self._min_interval > 0:
            async with self._lock:
                now = asyncio.get_event_loop().time()
                wait = max(0.0, self._last_start + self._min_interval - now)
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last_start = asyncio.get_event_loop().time()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._sem.release()

    # Backwards-compat: support `async with limiter()` style too
    def __call__(self) -> "RateLimiter":
        return self
