"""Retry decorator built on tenacity. Exponential backoff + jitter, only on
retryable network errors."""
from __future__ import annotations

import functools
import logging
from typing import Awaitable, Callable, TypeVar

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
    before_sleep_log,
)

log = logging.getLogger(__name__)

T = TypeVar("T")

# Retry only on transient I/O errors. Do NOT retry on 4xx (client error)
# except 408/429/503 which the caller can map to RetryableError explicitly.
_RETRYABLE = (
    TimeoutError,
    ConnectionError,
    OSError,
)


class RetryableError(Exception):
    """Wrap a non-retryable-looking error that should still be retried
    (e.g. HTTP 503 with a Cloudflare challenge body)."""


def with_retry(
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 30.0,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Async retry decorator. Apply to Fetcher.fetch implementations."""
    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        decorated = retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential_jitter(multiplier=initial_wait, max=max_wait),
            retry=retry_if_exception_type(_RETRYABLE + (RetryableError,)),
            before_sleep=before_sleep_log(log, logging.WARNING),
            reraise=True,
        )(fn)

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await decorated(*args, **kwargs)

        return wrapper

    return decorator
