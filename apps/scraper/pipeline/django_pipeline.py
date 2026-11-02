"""Django-backed pipeline. Uses asgiref.sync_to_async so async code can call
Django ORM safely without blocking the event loop."""
from __future__ import annotations

import logging
from typing import Optional, Set

from asgiref.sync import sync_to_async

from ..domain.models import PositionExtracted, normalize_url

log = logging.getLogger(__name__)


class DjangoPositionPipeline:
    """Saves scraped positions to Django Position model with dedup.

    Usage:
        pipeline = DjangoPositionPipeline(website)
        await pipeline.warmup()    # load existing URLs for dedup
        # ... in scrape loop:
        ok = await pipeline.process(item)
    """

    def __init__(self, website):
        # website is the Django Website model instance
        self.website = website
        self._seen: Set[str] = set()

    async def warmup(self) -> int:
        """Pre-load existing position URLs for dedup. Returns count loaded."""
        urls = await sync_to_async(list)(
            self.website.positions.values_list("url", flat=True)
        )
        self._seen = {normalize_url(u) for u in urls}
        return len(self._seen)

    async def process(self, item: PositionExtracted) -> bool:
        key = item.normalized_url
        if key in self._seen:
            log.debug("Skip duplicate: %s", item.url)
            return False
        try:
            await sync_to_async(self._create)(item)
        except Exception as e:
            log.exception("DB save failed for %s: %s", item.url, e)
            return False
        self._seen.add(key)
        return True

    def _create(self, item: PositionExtracted):
        """Sync DB call — wrapped in sync_to_async by process()."""
        # Late import so the scraper package can be imported without Django
        from apps.positions.models import Position
        return Position.objects.create(
            website=self.website,
            status="SCRAPED",
            url=item.url,
            title=item.title or "Unknown Title",
            company=item.company,
            cleaned_text=item.cleaned_text,
        )

    async def close(self) -> None:
        pass
