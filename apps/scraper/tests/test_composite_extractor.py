"""Tests for the composite extractor — verifies it tries extractors in priority
order and uses the first that yields results."""
import json

import pytest

from scraper.extractors.composite import CompositeExtractor


@pytest.mark.asyncio
async def test_jsonld_priority_over_css(jsonld_config, jsonld_listing_html, make_result):
    """JSON-LD extractor should win on a page that has both JSON-LD and CSS-extractable content."""
    result = make_result(
        url="https://example.com/jobs",
        body=jsonld_listing_html.encode(),
        content_type="text/html; charset=utf-8",
    )
    # The page has both JSON-LD JobPostings and .job-card divs
    jsonld_config.listing_css = ".job-card"
    jsonld_config.link_css = "a"
    jsonld_config.title_css = "a"

    items = await CompositeExtractor().extract_listing(result, jsonld_config)
    # JSON-LD yields 2 structured JobPostings; CSS would also yield 2 anchors.
    # But JSON-LD is configured first → that's what wins. We assert by checking
    # the extractor_used field on results.
    assert len(items) == 2
    assert all(item.extractor_used == "jsonld" for item in items)


@pytest.mark.asyncio
async def test_falls_back_to_css_when_no_jsonld(basic_html_config, listing_html,
                                                 make_result):
    """If JSON-LD yields nothing, composite should fall through to CSS."""
    result = make_result(
        url="https://example.com/jobs",
        body=listing_html.encode(),
        content_type="text/html; charset=utf-8",
    )
    items = await CompositeExtractor().extract_listing(result, basic_html_config)
    assert len(items) == 3
    assert all(item.extractor_used == "css" for item in items)


@pytest.mark.asyncio
async def test_jmespath_used_for_json_api(api_config, api_response_json, make_result):
    """JSON-LD extractor returns [] for JSON content; JMESPath should kick in."""
    result = make_result(
        url="https://api.example.com/v1/jobs?page=1",
        body=json.dumps(api_response_json).encode(),
        content_type="application/json",
    )
    items = await CompositeExtractor().extract_listing(result, api_config)
    assert len(items) == 3
    assert all(item.extractor_used == "jmespath" for item in items)


@pytest.mark.asyncio
async def test_returns_empty_when_no_extractor_matches(make_result):
    """Plain text response with no configured extractor → empty list."""
    from scraper.domain.models import SiteConfig
    config = SiteConfig(name="t", base_url="https://x.com")
    result = make_result(
        url="https://x.com",
        body=b"just plain text, no JSON-LD, no JSON",
        content_type="text/plain",
    )
    items = await CompositeExtractor().extract_listing(result, config)
    assert items == []
