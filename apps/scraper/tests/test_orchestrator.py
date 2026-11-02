"""Integration test for PositionScraper with a mocked fetcher — verifies the
end-to-end flow of pagination + extraction + concurrent detail fetching."""
from __future__ import annotations

import asyncio
import json
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from scraper.domain.models import (
    FetchResult,
    PaginationConfig,
    SiteConfig,
)
from scraper.orchestrator.scraper import PositionScraper


def _make_result(url: str, body: bytes, content_type: str = "text/html") -> FetchResult:
    return FetchResult(
        url=url, status=200,
        headers={"content-type": content_type},
        body_bytes=body, elapsed_ms=10.0,
    )


@pytest.mark.asyncio
async def test_scraper_iterates_pages_until_exhausted(api_config, api_response_json,
                                                       api_detail_response_json):
    """End-to-end: scrape 2 pages of an API, fetch details for each item."""

    # Page 1 response: 3 items, has_next=True
    page1 = dict(api_response_json)
    page2 = json.loads(json.dumps(api_response_json))  # deep copy
    page2["meta"]["page"] = 2
    page2["meta"]["has_next"] = False  # last page

    # Mock fetcher — returns different responses based on URL
    page_call_count = {"value": 0}

    async def mock_fetch(url, config, **kwargs):
        if "page=1" in url or "page=1" not in url and page_call_count["value"] == 0:
            page_call_count["value"] += 1
            return _make_result(url, json.dumps(page1).encode(), "application/json")
        if "page=2" in url:
            page_call_count["value"] += 1
            return _make_result(url, json.dumps(page2).encode(), "application/json")
        # Detail fetch — return the same detail for any URL
        return _make_result(url, json.dumps(api_detail_response_json).encode(),
                            "application/json")

    # Configure for 2 pages
    api_config.max_pages = 2
    scraper = PositionScraper(api_config)
    scraper.fetcher.fetch = mock_fetch  # type: ignore

    items = []
    async for item in scraper.iter_positions():
        items.append(item)

    # Page 1 + Page 2 = 6 items total (3 per page)
    assert len(items) == 6
    # All items should have detail text enriched
    assert all("language models" in item.cleaned_text.lower() or
               "phd in" in item.title.lower() for item in items)


@pytest.mark.asyncio
async def test_scraper_stops_when_listing_empty(api_config, api_response_json):
    """If extract_listing returns [], the scraper stops."""
    empty_response = {"jobs": [], "meta": {"has_next": False}}

    async def mock_fetch(url, config, **kwargs):
        return _make_result(url, json.dumps(empty_response).encode(),
                            "application/json")

    scraper = PositionScraper(api_config)
    scraper.fetcher.fetch = mock_fetch  # type: ignore

    items = []
    async for item in scraper.iter_positions():
        items.append(item)

    assert items == []


@pytest.mark.asyncio
async def test_scraper_yields_listing_item_when_no_detail_config(basic_html_config,
                                                                  listing_html):
    """If no detail config (no detail_container_css), listing items are yielded as-is."""
    basic_html_config.detail_container_css = None
    basic_html_config.max_pages = 1

    async def mock_fetch(url, config, **kwargs):
        return _make_result(url, listing_html.encode(), "text/html")

    scraper = PositionScraper(basic_html_config)
    scraper.fetcher.fetch = mock_fetch  # type: ignore

    items = []
    async for item in scraper.iter_positions():
        items.append(item)

    assert len(items) == 3
    assert items[0].title == "PhD in Artificial Intelligence"
    assert items[0].company == "MIT CSAIL"
