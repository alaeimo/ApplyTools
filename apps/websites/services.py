"""Compatibility bridge — provides a sync ScrapeOrchestrator that wraps the
new async PositionScraper for code that still imports from apps.websites.services.

This lets you gradually migrate callers without breaking existing imports.

Usage (new recommended way):
    from apps.scraper.orchestrator.scraper import PositionScraper
    from apps.scraper.services.site_config_provider import website_to_config

Usage (backward-compatible):
    from apps.websites.services import ScrapeOrchestrator
    orchestrator = ScrapeOrchestrator(website)
    for position in orchestrator.scrape(max_pages=5):
        ...
"""
import asyncio
import logging

from apps.scraper.orchestrator.scraper import PositionScraper
from apps.scraper.pipeline.django_pipeline import DjangoPositionPipeline
from apps.scraper.services.site_config_provider import website_to_config
from apps.scraper.domain.models import PositionExtracted

logger = logging.getLogger(__name__)


class ScrapeOrchestrator:
    """Sync wrapper around the new async PositionScraper.

    Yields PositionExtracted objects one at a time, just like the old
    scraper.scrape() generator. Internally runs an asyncio event loop.

    The pipeline (DB persistence + dedup) is handled internally —
    callers receive already-saved positions (saved=True) or None (skipped/failed).
    For finer control, use the async PositionScraper directly.
    """

    def __init__(self, website):
        self.website = website
        self.config = website_to_config(website)
        self.pipeline = DjangoPositionPipeline(website)
        self.scraper = PositionScraper(config=self.config, pipeline=None)

    def scrape(self, max_pages=None):
        """Sync generator yielding saved PositionExtracted objects.

        Args:
            max_pages: Override config.max_pages (None = use config).

        Yields:
            PositionExtracted: Each saved position (skips duplicates).
        """
        if max_pages is not None:
            self.config.max_pages = max_pages

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Warmup dedup cache
            loop.run_until_complete(self.pipeline.warmup())

            # Drive the async generator
            async_gen = self.scraper.iter_positions()

            while True:
                try:
                    position = loop.run_until_complete(async_gen.__anext__())
                except StopAsyncIteration:
                    break

                # Save (returns True if saved, False if duplicate)
                try:
                    ok = loop.run_until_complete(self.pipeline.process(position))
                    if ok:
                        yield position
                except Exception as e:
                    logger.warning("Failed to save %s: %s", position.url, e)

        finally:
            try:
                loop.run_until_complete(self.scraper.fetcher.close())
            except Exception:
                pass
            try:
                loop.run_until_complete(self.pipeline.close())
            except Exception:
                pass
            loop.close()

    async def scrape_async(self, max_pages=None):
        """Async generator — for callers that already have an event loop."""
        if max_pages is not None:
            self.config.max_pages = max_pages

        await self.pipeline.warmup()
        try:
            async for position in self.scraper.iter_positions():
                try:
                    ok = await self.pipeline.process(position)
                    if ok:
                        yield position
                except Exception as e:
                    logger.warning("Failed to save %s: %s", position.url, e)
        finally:
            await self.scraper.fetcher.close()
            await self.pipeline.close()


# Re-export for backward compat with old imports
PositionScraper = PositionScraper  # noqa: F811 — alias for old `from .services import PositionScraper`
