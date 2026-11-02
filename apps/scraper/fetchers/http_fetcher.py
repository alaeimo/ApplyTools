"""Async HTTP fetcher with TLS/JA3 impersonation via curl_cffi.

Replaces the original scraper's hardcoded session-per-extractor pattern with
a shared AsyncSession, randomized UA per request, and proper Accept headers.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Optional

from curl_cffi import requests as curl_requests

from ..domain.models import FetchResult, SiteConfig
from ..middleware.headers import build_browser_headers
from ..middleware.retry import with_retry, RetryableError

log = logging.getLogger(__name__)


class HttpFetcher:
    """Async HTTP fetcher with TLS impersonation."""

    def __init__(self, impersonate: str = "chrome124"):
        # impersonate value must match a profile supported by curl_cffi.
        # Newer versions of curl_cffi ship multiple chrome/firefox versions.
        self._impersonate = impersonate
        self._session: Optional[curl_requests.AsyncSession] = None

    async def _ensure_session(self) -> curl_requests.AsyncSession:
        if self._session is None:
            self._session = curl_requests.AsyncSession(
                impersonate=self._impersonate,
                timeout=30.0,
            )
        return self._session

    @with_retry(max_attempts=5, initial_wait=2.0, max_wait=60.0)
    async def fetch(
        self,
        url: str,
        config: SiteConfig,
        *,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
        body: Optional[dict[str, Any]] = None,
        use_browser: bool = False,
    ) -> Optional[FetchResult]:
        session = await self._ensure_session()

        # Detect if this is a JSON API call (determines Accept header)
        is_html = not (".json" in url.lower() or "/api/" in url.lower()
                       or method == "POST" or headers and "accept" in {k.lower() for k in headers})

        merged_headers = build_browser_headers(
            accept=headers.get("Accept") if headers else None,
            referer=str(config.base_url),
            extra={**headers, **config.api_headers} if headers else dict(config.api_headers),
            is_html=is_html,
        )
        if config.api_auth_token:
            token = config.api_auth_token.strip()
            if not token.lower().startswith("bearer "):
                token = f"Bearer {token}"
            merged_headers["Authorization"] = token

        start = time.perf_counter()
        try:
            resp = await session.request(
                method=method,
                url=url,
                headers=merged_headers,
                json=body if method in ("POST", "PUT", "PATCH") else None,
                params=body if method == "GET" else None,
                timeout=config.request_timeout,
                allow_redirects=True,
            )
        except (TimeoutError, ConnectionError, OSError) as e:
            log.warning("HTTP %s on %s: %s", method, url, e)
            raise   # let @with_retry handle backoff
        except Exception as e:
            # Unexpected — log and return None, no retry
            log.exception("Unexpected HTTP error on %s: %s", url, e)
            return None

        elapsed = (time.perf_counter() - start) * 1000

        # Map retryable HTTP statuses to RetryableError so tenacity backoffs
        if resp.status_code in (408, 429, 503):
            log.warning("HTTP %d on %s — retrying", resp.status_code, url)
            raise RetryableError(f"HTTP {resp.status_code}")

        # Politeness delay (randomized, not fixed — defeats WAF pattern matching)
        if config.request_delay and config.request_delay != (0.0, 0.0):
            lo, hi = config.request_delay
            await asyncio.sleep(random.uniform(lo, hi))

        return FetchResult(
            url=str(resp.url),
            status=resp.status_code,
            headers={k: v for k, v in resp.headers.items()},
            body_bytes=resp.content,
            elapsed_ms=elapsed,
            from_browser=False,
        )

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
