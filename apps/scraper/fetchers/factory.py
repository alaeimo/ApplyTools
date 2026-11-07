"""AutoFetcher — tries HTTP first; falls back to a real browser when the
response looks like a JS challenge (Cloudflare, Datadome, etc.)."""
from __future__ import annotations

import logging
from typing import Any, Optional

from ..domain.models import FetchResult, SiteConfig
from .base import Fetcher
from .browser_fetcher import BrowserFetcher
from .http_fetcher import HttpFetcher

log = logging.getLogger(__name__)


_CHALLENGE_MARKERS = (
    "cloudflare", "datadome", "akamai", "just a moment",
    "checking your browser", "ddos protection", "incapsula",
    "challenge-platform", "perimeterx",
)


class AutoFetcher:
    """Strategy that picks the right transport automatically."""

    def __init__(
        self,
        http: Optional[HttpFetcher] = None,
        browser: Optional[BrowserFetcher] = None,
    ):
        self.http = http or HttpFetcher()
        self.browser = browser or BrowserFetcher()

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
        # If the site config explicitly says needs_js, skip HTTP entirely
        if config.needs_js or use_browser:
            result = await self._try_browser(url, config, method, headers, body)
            if result:
                return result
            # Fall through to nodriver if Playwright failed
            return await self._try_nodriver(url, config, method, headers, body)

        # Try HTTP first; on persistent failure, fall back to browser
        try:
            result = await self.http.fetch(
                url, config, method=method, headers=headers, body=body,
            )
        except Exception as http_exc:
            log.warning(
                "HTTP fetch raised %s on %s — trying browser fallback",
                type(http_exc).__name__, url,
            )
            if config.use_browser_fallback:
                result = await self._try_browser(url, config, method, headers, body)
                if result:
                    return result
                return await self._try_nodriver(url, config, method, headers, body)
            raise

        # Detect challenge responses and retry with browser
        if result and _looks_like_challenge(result) and config.use_browser_fallback:
            log.info("Detected bot challenge on %s — retrying with browser", url)
            result = await self._try_browser(url, config, method, headers, body)
            if result:
                return result
            return await self._try_nodriver(url, config, method, headers, body)
        return result

    async def _try_browser(
        self, url, config, method, headers, body
    ) -> Optional[FetchResult]:
        """Try Playwright browser fetch. Returns None on failure."""
        try:
            return await self.browser.fetch(
                url, config, method=method, headers=headers, body=body, use_browser=True,
            )
        except Exception as e:
            log.warning("Playwright browser failed on %s: %s", url, e)
            return None

    async def _try_nodriver(
        self, url, config, method, headers, body
    ) -> Optional[FetchResult]:
        """Last-resort: nodriver (raw CDP). Returns None on failure."""
        try:
            from .nodriver_fetcher import NodriverFetcher
            nd = NodriverFetcher(headless=False)
            return await nd.fetch(
                url, config, method=method, headers=headers, body=body, use_browser=True,
            )
        except Exception as e:
            log.warning("nodriver fallback failed on %s: %s", url, e)
            return None

    async def close(self) -> None:
        await self.http.close()
        await self.browser.close()


def _looks_like_challenge(result: FetchResult) -> bool:
    if result.status not in (403, 429, 503):
        return False
    body = result.text.lower()[:8000]
    return any(m in body for m in _CHALLENGE_MARKERS)
