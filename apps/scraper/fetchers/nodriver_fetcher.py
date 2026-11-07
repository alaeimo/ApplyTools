"""nodriver-based fetcher — drives Chrome via raw CDP, invisible to Cloudflare.

Used as the final fallback tier when HTTP (curl_cffi) and Playwright both fail
to bypass Cloudflare Turnstile. nodriver doesn't set navigator.webdriver and
patches Chrome at the CDP level, making it indistinguishable from a real user
browser for most anti-bot systems.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from ..domain.models import FetchResult, SiteConfig

log = logging.getLogger(__name__)


class NodriverFetcher:
    """Last-resort fetcher using nodriver (raw CDP, no webdriver flag)."""

    def __init__(self, headless: bool = False):
        # nodriver works best in headed mode — Cloudflare detects headless
        # even with CDP. Headed mode pops up a real Chrome window.
        self._headless = headless
        self._browser = None
        self._lock = asyncio.Lock()

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
        try:
            import nodriver as uc
        except ImportError:
            log.error("nodriver not installed: pip install nodriver")
            return None

        start = time.perf_counter()
        browser = None
        try:
            browser = await uc.start(headless=self._headless)
            tab = await browser.get(url)

            # ─── Wait for Cloudflare challenge to solve ──────────────
            solved = await self._wait_for_cloudflare(tab, timeout=40)
            if not solved:
                log.warning("Cloudflare challenge did not resolve via nodriver")

            # ─── Wait for content selector ────────────────────────────
            content_selectors = []
            if hasattr(config, "listing_css") and config.listing_css:
                content_selectors.append(config.listing_css.split(",")[0].strip())
            if hasattr(config, "detail_container_css") and config.detail_container_css:
                content_selectors.append(config.detail_container_css.split(",")[0].strip())
            content_selectors.extend(["main", "article", ".container", "body"])

            for sel in content_selectors:
                if not sel:
                    continue
                try:
                    await tab.wait_for(selector=sel, timeout=8)
                    log.info("nodriver content ready (matched %s)", sel)
                    break
                except Exception:
                    continue

            # ─── Get final HTML ────────────────────────────────────────
            content = await tab.get_content()
            # get_content returns the full HTML document
            if isinstance(content, bytes):
                html_str = content.decode("utf-8", errors="replace")
            else:
                html_str = str(content)

            # Try to get final URL (may have redirected after challenge)
            try:
                final_url = await tab.evaluate(
                    "window.location.href", return_by_value=True
                )
                if isinstance(final_url, str) and final_url.startswith("http"):
                    url = final_url
            except Exception:
                pass

            elapsed = (time.perf_counter() - start) * 1000
            return FetchResult(
                url=url,
                status=200,
                headers={},
                body_bytes=html_str.encode("utf-8", errors="replace"),
                elapsed_ms=elapsed,
                from_browser=True,
            )
        except Exception as e:
            log.error("nodriver failed on %s: %s", url, e)
            return None
        finally:
            if browser is not None:
                try:
                    # stop() is sync in nodriver — run in executor to avoid
                    # blocking the event loop
                    await asyncio.get_event_loop().run_in_executor(
                        None, browser.stop
                    )
                except Exception:
                    pass

    async def _wait_for_cloudflare(self, tab, timeout: int = 40) -> bool:
        """Wait for Cloudflare challenge to resolve. Returns True if solved."""
        try:
            title = await tab.evaluate("document.title", return_by_value=True)
            title_str = str(title or "").lower()
            if "just a moment" not in title_str and "checking your browser" not in title_str:
                return True  # No challenge present
        except Exception:
            pass

        log.info("nodriver: Cloudflare challenge detected, waiting...")
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            await asyncio.sleep(1)
            try:
                title = await tab.evaluate("document.title", return_by_value=True)
                title_str = str(title or "").lower()
                if "just a moment" not in title_str and "checking your browser" not in title_str:
                    log.info("nodriver: Cloudflare challenge resolved")
                    return True
            except Exception:
                continue
        return False

    async def close(self) -> None:
        # nodriver browser is stopped per-fetch in finally block
        pass