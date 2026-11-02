"""Tests for the website scraper — rewritten for the new async architecture.

Run with:
    python manage.py test apps.websites
    # or
    pytest apps/websites/tests.py -v
"""
import asyncio
import pytest
from django.test import TestCase

from apps.websites.models import Website
from apps.websites.services import ScrapeOrchestrator


def test_scraper(website_id, max_pages=None):
    """Test the scraper on a real website (run from Django shell).

    Usage:
        from apps.websites.tests import test_scraper
        test_scraper(website_id=1, max_pages=1)
    """
    website = Website.objects.get(id=website_id, is_active=True)
    print(f"Testing scraper for: {website.name} ({website.scraping_method})")
    print("=" * 60)

    orchestrator = ScrapeOrchestrator(website)
    count = 0

    try:
        for position in orchestrator.scrape(max_pages=max_pages):
            count += 1
            print(f"\n📌 Position #{count}")
            print(f"  Title:    {position.title}")
            print(f"  URL:      {position.url}")
            print(f"  Company:  {position.company}")
            text = position.cleaned_text or ''
            snippet = text[:300] + ('...' if len(text) > 300 else '')
            print(f"  Text:     {snippet}")
            print(f"  Extractor: {position.extractor_used}")
            print(f"  Confidence: {position.confidence}")
            print("-" * 50)
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n✅ Scraping finished. Total positions saved: {count}")


@pytest.mark.django_db
def test_scraper_async(website_id, max_pages=None):
    """Async version — for pytest-asyncio.

    Usage:
        pytest -s -k test_scraper_async --website-id=1
    """
    website = Website.objects.get(id=website_id, is_active=True)
    orchestrator = ScrapeOrchestrator(website)

    async def _run():
        count = 0
        async for position in orchestrator.scrape_async(max_pages=max_pages):
            count += 1
            print(f"  [{count}] {position.title} — {position.url}")
        return count

    count = asyncio.run(_run())
    print(f"\n✅ Saved {count} positions")
    return count


# ─── Unit tests (no network required) ────────────────────────

class WebsiteConfigValidationTest(TestCase):
    """Tests for the Website model's clean() method."""

    def test_html_site_requires_base_url(self):
        """An HTML site without base_url should fail validation."""
        from django.core.exceptions import ValidationError
        website = Website(
            name="test",
            scraping_method="html",
            # base_url missing
            listing_item_selector=".job",
            position_link_selector="a",
            detail_source="html",
            detail_container_selector=".detail",
        )
        with self.assertRaises(ValidationError) as ctx:
            website.clean()
        self.assertIn('base_url', ctx.exception.message_dict)

    def test_api_site_requires_api_endpoint(self):
        """An API site without api_endpoint should fail validation."""
        from django.core.exceptions import ValidationError
        website = Website(
            name="test",
            scraping_method="api",
            base_url="https://example.com",
            # api_endpoint missing
            api_results_key="results",
            detail_source="html",
            detail_container_selector=".detail",
        )
        with self.assertRaises(ValidationError) as ctx:
            website.clean()
        self.assertIn('api_endpoint', ctx.exception.message_dict)

    def test_valid_html_site_passes(self):
        """A properly configured HTML site should pass validation."""
        website = Website(
            name="valid-html",
            scraping_method="html",
            base_url="https://example.com",
            pagination_url_pattern="/jobs?page={page}",
            listing_item_selector=".job-card",
            position_link_selector="a.title",
            detail_source="html",
            detail_container_selector=".job-detail",
        )
        # Should not raise
        website.clean()

    def test_valid_api_site_passes(self):
        """A properly configured API site should pass validation."""
        website = Website(
            name="valid-api",
            scraping_method="api",
            base_url="https://example.com",
            api_endpoint="https://api.example.com/v1/jobs",
            api_results_key="results",
            detail_source="api",
            detail_api_endpoint="https://api.example.com/v1/jobs",
            api_detail_key="data.job",
        )
        # Should not raise
        website.clean()


class WebsiteSerializerTest(TestCase):
    """Tests for the WebsiteSerializer's validation and security."""

    def test_api_auth_token_is_write_only(self):
        """The api_auth_token should never appear in serialized output."""
        from apps.websites.serializers import WebsiteSerializer
        website = Website.objects.create(
            name="token-test",
            base_url="https://example.com",
            scraping_method="html",
            listing_item_selector=".job",
            position_link_selector="a",
            detail_container_selector=".detail",
            api_auth_token="secret-bearer-token-123",
        )
        serializer = WebsiteSerializer(website)
        data = serializer.data
        self.assertNotIn('api_auth_token', data,
                         "Token must not be exposed in API responses")

    def test_html_site_without_selectors_fails(self):
        """Serializer should reject HTML sites without required selectors."""
        from apps.websites.serializers import WebsiteSerializer
        from rest_framework.exceptions import ValidationError
        serializer = WebsiteSerializer(data={
            'name': 'bad-html',
            'scraping_method': 'html',
            # missing base_url, listing_item_selector, etc.
        })
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_api_site_without_endpoint_fails(self):
        """Serializer should reject API sites without api_endpoint."""
        from apps.websites.serializers import WebsiteSerializer
        from rest_framework.exceptions import ValidationError
        serializer = WebsiteSerializer(data={
            'name': 'bad-api',
            'scraping_method': 'api',
            'api_results_key': 'results',
            # missing api_endpoint
        })
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)
