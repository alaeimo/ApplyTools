"""Headless Chromium fetcher for JS-rendered pages.

Uses playwright-stealth (if installed) applied per-page + persistent browser
context to defeat Cloudflare/Datadome bot detection. Falls back to manual
stealth init script if playwright-stealth is not installed or its API changes.
"""
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

# Real Windows Chrome 131 user-agent — matches what real users have in 2026.
_REAL_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Manual stealth init — fallback if playwright-stealth isn't installed or fails.
_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'vendor', {get: () => 'Google Inc.'});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
window.chrome = { runtime: {}, app: {}, csi: () => {}, loadTimes: () => {} };
Object.defineProperty(navigator, 'permissions', {get: () => ({ query: () => Promise.resolve({ state: 'granted' }) }) });
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(p) {
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel Iris OpenGL Engine';
    return getParameter.call(this, p);
};
"""


class BrowserFetcher:
    """Playwright-backed fetcher for sites requiring JS execution.

    Design:
    1. Uses regular async_playwright().start() — no fragile wrapper API
    2. Applies playwright-stealth per-page (try multiple API shapes for compat)
    3. Reuses a persistent browser context to preserve cf_clearance cookie
    4. Waits up to 40s for Cloudflare challenge to solve
    5. Tries clicking the Turnstile iframe if detected
    """

    def __init__(self, headless: bool = True, stealth: bool = True):
        self._headless = headless
        self._stealth = stealth
        self._pw = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._lock = asyncio.Lock()
        # Probe the installed playwright-stealth API once at construction
        self._stealth_apply_fn = self._probe_stealth_api()

    # ─── Stealth API detection ──────────────────────────────────────

    @staticmethod
    def _probe_stealth_api():
        """Return a callable(page) that applies stealth, or None.

        Tries multiple shapes of the playwright-stealth API for forward/backward compat:
        - v2.x: Stealth().apply_stealth_async(page_or_context)
        - v1.x: stealth_async(page) function
        Returns None if neither is available.
        """
        # Try v2.x class-based API
        try:
            from playwright_stealth import Stealth

            instance = Stealth()
            apply = getattr(instance, "apply_stealth_async", None)
            if callable(apply):
                log.info("playwright-stealth v2.x detected (apply_stealth_async)")
                return lambda page: apply(page)
        except ImportError:
            pass
        except Exception as e:
            log.debug("Stealth v2.x probe failed: %s", e)

        # Try v1.x function API
        try:
            from playwright_stealth import stealth_async

            if callable(stealth_async):
                log.info("playwright-stealth v1.x detected (stealth_async)")
                return lambda page: stealth_async(page)
        except ImportError:
            pass
        except Exception as e:
            log.debug("Stealth v1.x probe failed: %s", e)

        log.warning(
            "playwright-stealth not installed or API not recognized. "
            "Falling back to manual stealth init script. "
            "Install/upgrade with: pip install -U playwright-stealth"
        )
        return None

    # ─── Browser + context lifecycle ────────────────────────────────

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
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--disable-site-isolation-trials",
                    ],
                )
            return self._browser

    async def _ensure_context(self) -> BrowserContext:
        """Get or create the persistent browser context.

        Reusing the context preserves cookies (including cf_clearance) so
        Cloudflare doesn't re-challenge on every request.
        """
        browser = await self._ensure_browser()
        if self._context is None:
            self._context = await browser.new_context(
                user_agent=_REAL_UA,
                viewport={"width": 1366, "height": 768},
                locale="en-US",
                timezone_id="America/New_York",
                java_script_enabled=True,
                ignore_https_errors=True,
            )
            # Always add the manual stealth init script as a baseline.
            # If playwright-stealth is available, it will add additional patches
            # per-page when _apply_stealth_to_page() is called.
            if self._stealth:
                await self._context.add_init_script(_STEALTH_INIT_SCRIPT)
            # Block heavy resources to speed up page load
            await self._context.route(
                "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot,mp4,webm}",
                lambda route: route.abort(),
            )
        return self._context

    async def _apply_stealth_to_page(self, page) -> None:
        """Apply playwright-stealth to a single page (best-effort)."""
        if not self._stealth_apply_fn:
            return
        try:
            await self._stealth_apply_fn(page)
        except Exception as e:
            log.debug("Per-page stealth apply failed (continuing with init script): %s", e)

    # ─── Cloudflare handling ────────────────────────────────────────

    async def _solve_cloudflare(self, page) -> bool:
        """Wait for Cloudflare challenge to resolve.

        Returns True if challenge solved (or wasn't present), False on timeout.
        """
        try:
            title = await page.title()
        except Exception:
            title = ""
        title_lower = (title or "").lower()

        if "just a moment" not in title_lower and "checking your browser" not in title_lower:
            return True  # No challenge present

        log.info("Cloudflare challenge detected — waiting for it to solve...")

        # Try clicking the Turnstile checkbox iframe
        try:
            turnstile_frame = page.frame_locator(
                'iframe[src*="challenges.cloudflare.com"]'
            )
            checkbox = turnstile_frame.locator('input[type="checkbox"]')
            if await checkbox.count() > 0:
                await checkbox.first.click(timeout=2000)
                log.info("Clicked Turnstile checkbox")
        except Exception:
            pass

        # Wait for the title to change (challenge solved)
        try:
            await page.wait_for_function(
                "() => document.title !== 'Just a moment...' "
                "&& !document.title.includes('Checking your browser')",
                timeout=40000,
            )
            log.info("Cloudflare challenge resolved")
            return True
        except PWError:
            log.warning("Cloudflare challenge did not resolve within 40s")
            return False

    # ─── Public fetch API ───────────────────────────────────────────

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
        on_response=None,
    ) -> Optional[FetchResult]:
        context = await self._ensure_context()
        page = await context.new_page()
        start = time.perf_counter()

        # Attach XHR response listener if provided
        if on_response:
            page.on("response", on_response)
            
        # Apply playwright-stealth per-page (if available)
        await self._apply_stealth_to_page(page)

        if headers:
            try:
                await page.set_extra_http_headers(headers)
            except Exception:
                pass

        try:
            # ─── Navigate ────────────────────────────────────────────
            try:
                response: Optional[PWResponse] = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=int(config.request_timeout * 1000),
                    referer=str(config.base_url),
                )
            except PWError as e:
                log.warning("Playwright navigation error on %s: %s", url, e)
                raise

            # ─── Solve Cloudflare if present ─────────────────────────
            await self._solve_cloudflare(page)

            # ─── Wait for real content ──────────────────────────────
            content_selectors = []
            if hasattr(config, "listing_css") and config.listing_css:
                content_selectors.append(config.listing_css.split(",")[0].strip())
            if hasattr(config, "detail_container_css") and config.detail_container_css:
                content_selectors.append(config.detail_container_css.split(",")[0].strip())
            content_selectors.extend([
                "main", "article", ".container", "#content", "#mainContent",
            ])
            seen = set()
            content_selectors = [
                s for s in content_selectors
                if s and s not in seen and not seen.add(s)
            ]

            content_ready = False
            for sel in content_selectors:
                try:
                    await page.wait_for_selector(sel, timeout=5000)
                    content_ready = True
                    log.info("Content ready (matched %s) on %s", sel, url)
                    break
                except PWError:
                    continue

            if not content_ready:
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except PWError:
                    log.warning("networkidle wait timed out on %s", url)

            content = await page.content()
            final_url = page.url
            status = response.status if response else 0
            resp_headers = await response.all_headers() if response else {}
        except PWError as e:
            log.warning("Playwright error on %s: %s", url, e)
            raise
        finally:
            try:
                await page.close()
            except Exception:
                pass

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
        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:
                pass
            self._pw = None