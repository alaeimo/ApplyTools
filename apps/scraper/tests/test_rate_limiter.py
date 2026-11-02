"""Tests for the rate limiter middleware."""
import asyncio
import time

import pytest

from scraper.middleware.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_concurrency_limit():
    """Only `max_concurrency` tasks should be in the critical section at once."""
    limiter = RateLimiter(max_concurrency=2)
    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    async def task():
        nonlocal in_flight, max_in_flight
        async with limiter:
            async with lock:
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.05)
            async with lock:
                in_flight -= 1

    await asyncio.gather(*[task() for _ in range(6)])
    assert max_in_flight <= 2


@pytest.mark.asyncio
async def test_min_interval():
    """Concurrent calls should respect min_interval between starts."""
    limiter = RateLimiter(max_concurrency=1, min_interval=0.1)
    timestamps = []

    async def task():
        async with limiter:
            timestamps.append(time.perf_counter())

    await asyncio.gather(*[task() for _ in range(3)])
    # Three starts with min 0.1s between them
    deltas = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
    assert all(d >= 0.09 for d in deltas), f"deltas too small: {deltas}"
