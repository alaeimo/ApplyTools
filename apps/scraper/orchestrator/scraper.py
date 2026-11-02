"""Top-level scraper — ties fetcher, extractor, pagination, pipeline together.
Yields PositionExtracted items asynchronously, with concurrent detail fetching."""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional

from ..domain.models import (
    FetchResult,
    PositionExtracted,
    ScrapeStats,
    SiteConfig,
)
from ..extractors.composite import CompositeExtractor
from ..fetchers.factory import AutoFetcher
from ..middleware.rate_limiter import RateLimiter
from ..pagination.strategies import make_strategy
from ..pipeline.base import Pipeline

log = logging.getLogger(__name__)


class PositionScraper:
    """Top-level orchestrator. Yields PositionExtracted items one by one.

    Usage:
        scraper = PositionScraper(config, pipeline=pipeline)
        async for position in scraper.iter_positions():
            print(position.title, position.url)
        # OR, with DB persistence:
        saved = await scraper.run()
    """

    def __init__(
        self,
        config: SiteConfig,
        *,
        fetcher: Optional[AutoFetcher] = None,
        extractor: Optional[CompositeExtractor] = None,
        pipeline: Optional[Pipeline] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.config = config
        self.fetcher = fetcher or AutoFetcher()
        self.extractor = extractor or CompositeExtractor()
        self.pipeline = pipeline
        self.rate_limiter = rate_limiter or RateLimiter(
            max_concurrency=config.max_concurrency
        )
        self._strategy = make_strategy(config.api_pagination)

    async def iter_positions(self) -> AsyncIterator[PositionExtracted]:
        """Yield positions across pages, with concurrent detail fetching per page."""
        # Decide starting URL: API endpoint, list_url, or base_url
        if self.config.api_endpoint:
            url = str(self.config.api_endpoint)
        elif self.config.list_url:
            url = self.config.list_url
        else:
            url = str(self.config.base_url)

        page = 1
        last_result: Optional[FetchResult] = None
        pages_fetched = 0

        while True:
            # Fetch listing page
            async with self.rate_limiter():
                result = await self.fetcher.fetch(url, self.config)
            if not result:
                log.warning("Listing fetch failed: %s", url)
                break
            pages_fetched += 1

            # Extract positions from listing
            items = await self.extractor.extract_listing(result, self.config)
            if not items:
                log.info("No items extracted from page %d — stopping", page)
                break

            log.info("Page %d: extracted %d items", page, len(items))

            # Fan out detail fetches concurrently (bounded by rate_limiter)
            async for detail in self._fetch_details_concurrently(items):
                yield detail

            # Advance to next page
            last_result = result
            if not self._strategy:
                break
            next_url = self._strategy.next_url(url, page, last_result, self.config)
            if not next_url or next_url == url:
                break
            url = next_url
            page += 1

    async def _fetch_details_concurrently(
        self, items: list[PositionExtracted]
    ) -> AsyncIterator[PositionExtracted]:
        """Fetch detail pages concurrently while preserving source order.

        If no detail config is set (no detail_jmespath / detail_container_css /
        detail_api_endpoint), the listing item is yielded as-is.
        """
        if not (self.config.detail_jmespath or self.config.detail_container_css
                or self.config.detail_api_endpoint):
            for item in items:
                yield item
            return

        async def _enrich(item: PositionExtracted) -> PositionExtracted:
            async with self.rate_limiter():
                res = await self.fetcher.fetch(item.url, self.config)
            if not res:
                return item
            detail = await self.extractor.extract_detail(res, self.config)
            if detail:
                if detail.cleaned_text:
                    item.cleaned_text = detail.cleaned_text
                item.raw_data = {**item.raw_data, **detail.raw_data}
                item.extractor_used = f"{item.extractor_used}+{detail.extractor_used}"
            return item

        # Concurrent gather; rate limiter inside _enrich bounds concurrency
        results = await asyncio.gather(
            *[_enrich(i) for i in items], return_exceptions=False,
        )
        for r in results:
            yield r

    async def run(self) -> ScrapeStats:
        """Scrape everything and push through pipeline. Returns final stats."""
        if not self.pipeline:
            raise RuntimeError("Pipeline required for run()")

        import time
        start = time.perf_counter()
        saved = skipped = failed = 0
        pages = 0

        async for item in self.iter_positions():
            try:
                ok = await self.pipeline.process(item)
                if ok:
                    saved += 1
                    log.info("[%d] Saved: %s", saved, item.title[:60])
                else:
                    skipped += 1
                    log.debug("Skipped (dup): %s", item.title[:60])
            except Exception as e:
                failed += 1
                log.exception("Pipeline error: %s", e)
            pages = max(pages, 1)

        await self.fetcher.close()
        await self.pipeline.close()

        return ScrapeStats(
            saved=saved,
            skipped=skipped,
            failed=failed,
            pages=pages,
            elapsed_s=time.perf_counter() - start,
        )
