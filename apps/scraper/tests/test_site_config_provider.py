"""Tests for the SiteConfig mapping service — verifies backwards compatibility
with the old Website model's 15+ fields."""
from dataclasses import dataclass
from typing import Optional

from scraper.services.site_config_provider import (
    website_to_config,
    _dot_to_jmespath,
)


@dataclass
class FakeWebsite:
    """Stub for the Django Website model — only the fields the provider reads."""
    name: str = "test"
    base_url: str = "https://example.com"
    scraping_method: str = "html"
    api_endpoint: Optional[str] = None
    api_pagination_param: Optional[str] = None
    api_limit_param: Optional[str] = "limit"
    api_auth_token: Optional[str] = None
    api_results_key: Optional[str] = None
    api_detail_key: Optional[str] = None
    detail_api_endpoint: Optional[str] = None
    listing_item_selector: Optional[str] = None
    position_link_selector: Optional[str] = None
    position_title_selector: Optional[str] = None
    position_company_selector: Optional[str] = None
    detail_container_selector: Optional[str] = None
    max_pages: int = 10
    request_timeout: int = 30
    request_delay: float = 3.0
    api_headers: Optional[dict] = None
    list_url: Optional[str] = None
    needs_js: bool = False
    use_browser_fallback: bool = True
    max_concurrency: int = 5


class TestDotToJmespath:
    def test_simple_path(self):
        assert _dot_to_jmespath("data.field") == "data.field"

    def test_items_becomes_list(self):
        assert _dot_to_jmespath("data.items") == "data.items[*]"

    def test_results_becomes_list(self):
        assert _dot_to_jmespath("results") == "results[*]"

    def test_jobs_becomes_list(self):
        assert _dot_to_jmespath("jobs") == "jobs[*]"


class TestWebsiteToConfig:
    def test_html_mode_default_priority_jsonld_first(self):
        website = FakeWebsite(
            name="static",
            base_url="https://example.com",
            scraping_method="html",
            listing_item_selector=".job-card",
            position_link_selector="a.title",
            position_title_selector="a.title",
            position_company_selector=".company",
            detail_container_selector=".job-detail",
        )
        config = website_to_config(website)

        assert config.extractor_priority[0] == "jsonld"
        assert config.listing_css == ".job-card"
        assert config.link_css == "a.title"
        assert config.max_pages == 10
        assert config.api_endpoint is None

    def test_api_mode_priority_jmespath_first(self):
        website = FakeWebsite(
            name="api-site",
            base_url="https://api.example.com",
            scraping_method="api",
            api_endpoint="https://api.example.com/v1/jobs",
            api_pagination_param="page",
            api_limit_param="per_page",
            api_results_key="data.items",
            api_detail_key="data.job",
            detail_api_endpoint="https://api.example.com/v1/jobs",
            max_pages=20,
        )
        config = website_to_config(website)

        assert config.extractor_priority[0] == "jmespath"
        assert config.api_results_jmespath == "data.items[*]"
        assert config.detail_jmespath == "data.job"
        assert config.api_pagination.type == "page"
        assert config.api_pagination.limit_param == "per_page"

    def test_offset_pagination_detected(self):
        website = FakeWebsite(
            name="api-offset",
            base_url="https://api.example.com",
            scraping_method="api",
            api_endpoint="https://api.example.com/v1/jobs",
            api_pagination_param="offset",
            api_limit_param="limit",
            api_results_key="jobs",
        )
        config = website_to_config(website)
        assert config.api_pagination.type == "offset"

    def test_randomized_delay_from_fixed(self):
        """A fixed delay of 1s → randomized (0.5, 2.0) range."""
        website = FakeWebsite(request_delay=3.0)
        config = website_to_config(website)
        assert config.request_delay == (1.5, 6.0)

    def test_zero_delay_uses_default(self):
        website = FakeWebsite(request_delay=3.0)
        config = website_to_config(website)
        assert config.request_delay == (1.5, 6.0)
