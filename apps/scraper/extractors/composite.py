"""Composite extractor — tries each extractor in priority order, uses the
first that yields results. Default priority: JSON-LD → JMESPath → CSS."""
from __future__ import annotations

import logging

from ..domain.models import FetchResult, PositionExtracted, SiteConfig
from .base import Extractor
from .css import CssExtractor
from .jmespath_extractor import JmespathExtractor
from .jsonld import JsonLdExtractor

log = logging.getLogger(__name__)


class CompositeExtractor:
    """Tries extractors in order. First non-empty result wins."""

    def __init__(self, registry: dict[str, Extractor] | None = None):
        self._registry = registry or {
            "jsonld": JsonLdExtractor(),
            "jmespath": JmespathExtractor(),
            "css": CssExtractor(),
        }

    async def extract_listing(
        self, result: FetchResult, config: SiteConfig
    ) -> list[PositionExtracted]:
        for name in config.extractor_priority:
            extractor = self._registry.get(name)
            if not extractor:
                continue
            try:
                items = await extractor.extract_listing(result, config)
            except Exception as e:
                log.warning("Extractor %s failed: %s", name, e)
                continue
            if items:
                log.debug("Extractor %s yielded %d items", name, len(items))
                return items
        return []

    async def extract_detail(
        self, result: FetchResult, config: SiteConfig
    ) -> PositionExtracted | None:
        for name in config.extractor_priority:
            extractor = self._registry.get(name)
            if not extractor:
                continue
            try:
                item = await extractor.extract_detail(result, config)
                if item:
                    return item
            except Exception as e:
                log.warning("Detail extractor %s failed: %s", name, e)
                continue
        return None
