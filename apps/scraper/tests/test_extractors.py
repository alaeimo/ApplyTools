"""Tests for extractors — pure async, no HTTP. Use fixture HTML/JSON."""
import json

import pytest

from scraper.extractors.css import CssExtractor
from scraper.extractors.jmespath_extractor import JmespathExtractor
from scraper.extractors.jsonld import JsonLdExtractor


@pytest.mark.asyncio
async def test_css_extractor_listing(basic_html_config, listing_html, make_result):
    result = make_result(
        url="https://example.com/jobs",
        body=listing_html.encode(),
        content_type="text/html; charset=utf-8",
    )
    items = await CssExtractor().extract_listing(result, basic_html_config)
    assert len(items) == 3
    assert items[0].title == "PhD in Artificial Intelligence"
    assert items[0].company == "MIT CSAIL"
    assert items[0].url == "https://example.com/jobs/phd-ai"
    assert items[1].url == "https://example.com/jobs/phd-robotics"  # absolute already


@pytest.mark.asyncio
async def test_css_extractor_detail(basic_html_config, detail_html, make_result):
    result = make_result(
        url="https://example.com/jobs/phd-ai",
        body=detail_html.encode(),
        content_type="text/html; charset=utf-8",
    )
    item = await CssExtractor().extract_detail(result, basic_html_config)
    assert item is not None
    assert "PhD student" in item.cleaned_text
    assert "natural language processing" in item.cleaned_text


@pytest.mark.asyncio
async def test_jsonld_extractor_listing(jsonld_config, jsonld_listing_html, make_result):
    result = make_result(
        url="https://example.com/jobs",
        body=jsonld_listing_html.encode(),
        content_type="text/html; charset=utf-8",
    )
    items = await JsonLdExtractor().extract_listing(result, jsonld_config)
    assert len(items) == 2
    assert items[0].title == "PhD Position in Quantum Computing"
    assert items[0].company == "ETH Zurich"
    assert items[0].url == "https://example.com/jobs/qc-1"
    assert "quantum" in items[0].cleaned_text.lower()
    assert items[1].company == "EMBL Heidelberg"


@pytest.mark.asyncio
async def test_jsonld_extractor_returns_empty_on_plain_html(jsonld_config, listing_html,
                                                              make_result):
    result = make_result(
        url="https://example.com/jobs",
        body=listing_html.encode(),
        content_type="text/html; charset=utf-8",
    )
    # No JSON-LD in plain listing.html
    items = await JsonLdExtractor().extract_listing(result, jsonld_config)
    assert items == []


@pytest.mark.asyncio
async def test_jmespath_extractor_listing(api_config, api_response_json, make_result):
    result = make_result(
        url="https://api.example.com/v1/jobs?page=1",
        body=json.dumps(api_response_json).encode(),
        content_type="application/json",
    )
    items = await JmespathExtractor().extract_listing(result, api_config)
    assert len(items) == 3
    assert items[0].title == "PhD in Machine Learning"
    assert items[0].company == "MIT CSAIL"
    assert items[0].url == "https://api.example.com/v1/jobs/1"
    assert "language models" in items[0].cleaned_text.lower()
    assert items[2].url == "https://api.example.com/v1/jobs/3"


@pytest.mark.asyncio
async def test_jmespath_extractor_detail(api_config, api_detail_response_json, make_result):
    result = make_result(
        url="https://api.example.com/v1/jobs/1",
        body=json.dumps(api_detail_response_json).encode(),
        content_type="application/json",
    )
    item = await JmespathExtractor().extract_detail(result, api_config)
    assert item is not None
    assert "language models" in item.cleaned_text.lower()
    assert "Python" in item.cleaned_text


@pytest.mark.asyncio
async def test_jmespath_extractor_returns_empty_without_config(api_response_json,
                                                                 make_result):
    """No api_results_jmespath → returns []."""
    from scraper.domain.models import SiteConfig
    config = SiteConfig(name="t", base_url="https://x.com")
    result = make_result(
        url="https://api.example.com/v1/jobs",
        body=json.dumps(api_response_json).encode(),
        content_type="application/json",
    )
    assert await JmespathExtractor().extract_listing(result, config) == []
