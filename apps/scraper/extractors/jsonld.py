"""JSON-LD extractor — uses schema.org JobPosting to extract positions with
ZERO per-site config. Works on ~60% of modern job boards."""
from __future__ import annotations

import logging
from typing import Any, Iterator

import extruct

from ..domain.models import FetchResult, PositionExtracted, SiteConfig
from ..parsers.text import html_to_text

log = logging.getLogger(__name__)


class JsonLdExtractor:
    """Extract JobPosting data from <script type="application/ld+json">.

    This is the most generalizable extractor: many modern job boards (Greenhouse,
    Workable, Lever, EU Institutions, etc.) embed structured JobPosting data.
    """

    name = "jsonld"

    async def extract_listing(
        self, result: FetchResult, config: SiteConfig
    ) -> list[PositionExtracted]:
        if not result.is_html:
            return []
        try:
            data = extruct.extract(
                result.text,
                base_url=result.url,
                syntaxes=["json-ld"],
                uniform=True,
            )
        except Exception as e:
            log.warning("extruct failed on %s: %s", result.url, e)
            return []

        positions: list[PositionExtracted] = []
        for obj in data.get("json-ld", []):
            for item in _iter_jobpostings(obj):
                positions.append(_build_position(item, result.url))
        return positions

    async def extract_detail(
        self, result: FetchResult, config: SiteConfig
    ) -> PositionExtracted | None:
        positions = await self.extract_listing(result, config)
        return positions[0] if positions else None


def _iter_jobpostings(obj: Any) -> Iterator[dict]:
    """Yield JobPosting dicts from possibly nested ItemList / ListItem / @graph."""
    if not isinstance(obj, dict):
        return
    t = obj.get("@type")
    types = t if isinstance(t, list) else [t]
    if "JobPosting" in types:
        yield obj
    if "ItemList" in types:
        for el in obj.get("itemListElement", []):
            yield from _iter_jobpostings(el)
    if "ListItem" in types:
        # ListItem wraps a JobPosting in its 'item' field
        inner = obj.get("item")
        if isinstance(inner, dict):
            yield from _iter_jobpostings(inner)
    if "@graph" in obj:
        for el in obj.get("@graph", []):
            yield from _iter_jobpostings(el)


def _build_position(item: dict, fallback_url: str) -> PositionExtracted:
    url = item.get("url") or fallback_url
    title = item.get("title") or "Unknown Title"
    org = item.get("hiringOrganization", {})
    company = org.get("name", "") if isinstance(org, dict) else str(org)
    desc = item.get("description", "") or item.get("responsibilities", "") or ""
    cleaned = html_to_text(str(desc))
    return PositionExtracted(
        url=str(url),
        title=str(title),
        company=str(company),
        cleaned_text=cleaned,
        raw_data=item,
        extractor_used="jsonld",
        confidence=0.95,
    )
