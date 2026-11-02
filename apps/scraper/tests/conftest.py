"""Pytest fixtures shared across tests.

Tests are pure (no Django) — they exercise the scraper package on its own.
Django integration is tested separately via `apps.scraper.tests.test_django_pipeline`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# Allow tests to import the scraper package without Django installed
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scraper.domain.models import (
    PaginationConfig,
    SiteConfig,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def basic_html_config() -> SiteConfig:
    """Config for a typical static HTML job board."""
    return SiteConfig(
        name="static-board",
        base_url="https://example.com",
        list_url="https://example.com/jobs",
        listing_css=".job-card",
        link_css="a.title",
        title_css="a.title",
        company_css=".company",
        detail_container_css=".job-detail",
        max_pages=3,
    )


@pytest.fixture
def api_config() -> SiteConfig:
    """Config for a JSON API job board."""
    return SiteConfig(
        name="api-board",
        base_url="https://api.example.com",
        api_endpoint="https://api.example.com/v1/jobs",
        api_results_jmespath="jobs[*]",
        api_pagination=PaginationConfig(
            type="page",
            param="page",
            limit_param="per_page",
            limit_value=10,
        ),
        detail_api_endpoint="https://api.example.com/v1/jobs",
        detail_jmespath="data.job",
        max_pages=3,
    )


@pytest.fixture
def jsonld_config() -> SiteConfig:
    """Config for a JSON-LD-heavy site (zero selectors needed)."""
    return SiteConfig(
        name="jsonld-board",
        base_url="https://example.com",
        list_url="https://example.com/jobs",
        max_pages=1,
    )


@pytest.fixture
def listing_html() -> str:
    return (FIXTURES_DIR / "listing.html").read_text(encoding="utf-8")


@pytest.fixture
def detail_html() -> str:
    return (FIXTURES_DIR / "detail.html").read_text(encoding="utf-8")


@pytest.fixture
def jsonld_listing_html() -> str:
    return (FIXTURES_DIR / "jsonld_listing.html").read_text(encoding="utf-8")


@pytest.fixture
def api_response_json() -> dict:
    return json.loads((FIXTURES_DIR / "api_response.json").read_text(encoding="utf-8"))


@pytest.fixture
def api_detail_response_json() -> dict:
    return json.loads((FIXTURES_DIR / "api_detail_response.json").read_text(encoding="utf-8"))


def make_fetch_result(
    *,
    url: str = "https://example.com",
    status: int = 200,
    body: bytes = b"",
    content_type: str = "text/html; charset=utf-8",
    elapsed_ms: float = 10.0,
    from_browser: bool = False,
):
    """Helper to build a FetchResult without going through the network."""
    from scraper.domain.models import FetchResult
    return FetchResult(
        url=url,
        status=status,
        headers={"content-type": content_type},
        body_bytes=body,
        elapsed_ms=elapsed_ms,
        from_browser=from_browser,
    )


@pytest.fixture
def make_result():
    return make_fetch_result
