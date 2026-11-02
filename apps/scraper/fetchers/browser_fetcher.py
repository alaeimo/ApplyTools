"""Headless Chromium fetcher for JS-rendered pages. Uses Playwright async API
with stealth init script to defeat automation detection."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Error as PWError,
    Response as PWResponse,
)

from ..domain.models import FetchResult, SiteConfig
from ..middleware.retry import with_retry

log = logging.getLogger(__name__)

_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'permissions', {get: () => ({ query: () => Promise.resolve({ state: 'granted' }) }) });
"""


class BrowserFetcher:
    """Playwright-backed fetcher for sites requiring JS execution."""

    def __init__(self, headless: bool = True, stealth: bool = True):
        self._headless = headless
        self._stealth = stealth
        self._pw = None
        self._browser: Optional[Browser] = None
        self._lock = asyncio.Lock()  # serialize browser launch

    async def _ensure_browser(self) -> Browser:
        async with self._lock:
            if self._browser is None:
                self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch(
                    headless=self._headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )
            return self._browser

    @with_retry(max_attempts=2, initial_wait=2.0, max_wait=20.0)
    async def fetch(
        self,
        url: str,
        config: SiteConfig,
        *,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
        body: Optional[dict[str, Any]] = None,
        use_browser: bool = True,
    ) -> Optional[FetchResult]:
        browser = await self._ensure_browser()
        context = await browser.new_context(
            user_agent=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
        )

        if self._stealth:
            await context.add_init_script(_STEALTH_INIT_SCRIPT)

        page: BrowserContext = await context.new_page()
        start = time.perf_counter()
        try:
            response: Optional[PWResponse] = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=int(config.request_timeout * 1000),
            )
            # Wait for body — covers React/Vue hydration
            try:
                await page.wait_for_selector("body", timeout=5000)
            except PWError:
                pass

            content = await page.content()
            final_url = page.url
            status = response.status if response else 0
            resp_headers = await response.all_headers() if response else {}
        except PWError as e:
            log.warning("Playwright error on %s: %s", url, e)
            raise
        finally:
            await context.close()

        elapsed = (time.perf_counter() - start) * 1000
        return FetchResult(
            url=final_url or url,
            status=status,
            headers={k: v for k, v in resp_headers.items()},
            body_bytes=content.encode("utf-8", errors="replace"),
            elapsed_ms=elapsed,
            from_browser=True,
        )

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None
