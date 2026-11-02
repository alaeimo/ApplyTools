"""Website configuration model.

Updated for the new async scraper architecture (apps/scraper).
Adds 3 new fields: needs_js, max_concurrency, use_browser_fallback.
All old fields are preserved for backward compatibility with existing fixtures.
"""
from django.db import models
from django.core.validators import URLValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone


class Website(models.Model):
    """Website configuration for scraping positions."""

    SCRAPING_METHOD_CHOICES = [
        ('html', 'HTML Scraping'),
        ('api', 'API Scraping'),
    ]

    DETAIL_SOURCE_CHOICES = [
        ('html', 'HTML Scraping'),
        ('api', 'API Scraping'),
    ]

    # ─── Basic Information ───────────────────────────────────
    name = models.CharField(
        max_length=200, unique=True,
        help_text="Name of the website"
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description of the website"
    )

    # ─── URL Configuration ───────────────────────────────────
    base_url = models.URLField(
        max_length=500, blank=True, validators=[URLValidator()],
        help_text="Base URL of the website"
    )
    pagination_url_pattern = models.CharField(
        max_length=500, blank=True,
        help_text="URL pattern with {page} placeholder (used by HTML mode)"
    )

    # ─── Selectors for HTML Scraping ─────────────────────────
    listing_item_selector = models.CharField(
        max_length=500, blank=True,
        help_text="CSS selector for each position container (e.g., '.job-list-item')"
    )
    position_link_selector = models.CharField(
        max_length=500, blank=True,
        help_text="CSS selector for position link within the container"
    )
    position_title_selector = models.CharField(
        max_length=500, blank=True,
        help_text="CSS selector for position title within the container"
    )
    position_company_selector = models.CharField(
        max_length=500, blank=True,
        help_text="CSS selector for company name within the container"
    )
    detail_container_selector = models.CharField(
        max_length=500, blank=True,
        help_text="CSS selector for the detail page content container"
    )

    # ─── API Configuration ───────────────────────────────────
    api_endpoint = models.URLField(
        max_length=500, blank=True,
        help_text="Full API endpoint URL for listing (e.g., https://api.example.com/v1/jobs/)"
    )
    api_pagination_param = models.CharField(
        max_length=50, blank=True, default='page',
        help_text="Query parameter name for page number (e.g., 'page', 'offset')"
    )
    api_limit_param = models.CharField(
        max_length=50, blank=True, default='limit',
        help_text="Query parameter name for items per page (e.g., 'limit', 'per_page')"
    )
    api_results_key = models.CharField(
        max_length=100, blank=True, default='results',
        help_text="Dot-notation path to the items list (e.g., 'results.items' → auto-converted to JMESPath 'results.items[*]')"
    )
    api_next_key = models.CharField(
        max_length=100, blank=True,
        help_text="JSON key for the next page URL (if provided by the API)"
    )
    api_count_key = models.CharField(
        max_length=100, blank=True,
        help_text="JSON key for the total count of items (if provided)"
    )
    api_item_url_key = models.CharField(
        max_length=100, blank=True,
        help_text="JSON key for the position URL (optional — auto-detected via JMESPath)"
    )
    api_item_title_key = models.CharField(
        max_length=100, blank=True,
        help_text="JSON key for the position title (optional — auto-detected)"
    )
    api_item_company_key = models.CharField(
        max_length=100, blank=True,
        help_text="JSON key for the company/organization (optional — auto-detected)"
    )
    api_item_description_key = models.CharField(
        max_length=100, blank=True,
        help_text="JSON key for the description (optional — auto-detected)"
    )
    api_auth_token = models.CharField(
        max_length=500, blank=True,
        help_text="Bearer token or API key for authentication (if required)"
    )
    api_extra_params = models.JSONField(
        default=dict, blank=True,
        help_text="Additional static query parameters as a JSON object"
    )

    # ─── Detail Source ───────────────────────────────────────
    detail_source = models.CharField(
        max_length=10, choices=DETAIL_SOURCE_CHOICES, default='html',
        help_text="Where to fetch position details from"
    )
    detail_api_endpoint = models.URLField(
        max_length=500, blank=True,
        help_text="Detail API endpoint URL (e.g., https://api.example.com/v1/jobs/)"
    )
    api_detail_key = models.CharField(
        max_length=100, blank=True,
        help_text="Dot-notation path to the detail object in the API response"
    )

    # ─── Scraping Configuration ──────────────────────────────
    scraping_method = models.CharField(
        max_length=10, choices=SCRAPING_METHOD_CHOICES, default='html',
        help_text="How to discover listings: HTML page or JSON API"
    )
    max_pages = models.IntegerField(
        default=0,
        help_text="Maximum pages to scrape per run — 0 means unlimited (capped at 1000)"
    )
    request_timeout = models.IntegerField(
        default=30, validators=[MinValueValidator(1), MaxValueValidator(300)],
        help_text="Request timeout in seconds"
    )
    request_delay = models.FloatField(
        default=3.0, validators=[MinValueValidator(0)],
        help_text="Base delay between requests (actual delay is randomized 1.5x–6x this value)"
    )
    user_agent = models.CharField(
        max_length=500, blank=True, default="",
        help_text="User agent string (optional — the scraper rotates UAs automatically)"
    )

    # ─── NEW: Scraper Options ────────────────────────────────
    needs_js = models.BooleanField(
        default=False,
        help_text="Force browser rendering (Playwright) — for JS-heavy SPAs"
    )
    max_concurrency = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text="Max concurrent detail page fetches (1–20)"
    )
    use_browser_fallback = models.BooleanField(
        default=True,
        help_text="Auto-fallback to browser when a bot challenge (Cloudflare/Datadome) is detected"
    )

    # ─── Status & Metadata ───────────────────────────────────
    is_active = models.BooleanField(default=True, help_text="Whether this website is active for scraping")
    is_enabled = models.BooleanField(default=True, help_text="Alias for is_active (kept for backward compat)")
    last_scraped_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of the last successful scrape")
    last_scrape_count = models.IntegerField(default=0, help_text="Number of positions scraped in the last run")
    total_scraped_count = models.IntegerField(default=0, help_text="Total number of positions scraped from this website")

    # ─── Timestamps ──────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['last_scraped_at']),
            models.Index(fields=['name', 'is_active']),
            models.Index(fields=['scraping_method']),
        ]
        verbose_name = "Website"
        verbose_name_plural = "Websites"

    def __str__(self):
        return self.name

    def clean(self):
        """Validate field consistency based on scraping_method."""
        super().clean()
        errors = {}

        if self.scraping_method == 'html':
            if not self.base_url:
                errors['base_url'] = "Base URL is required for HTML scraping."
            if not self.pagination_url_pattern and not self.base_url:
                errors['pagination_url_pattern'] = (
                    "Either pagination_url_pattern or base_url must be set for HTML scraping."
                )
        elif self.scraping_method == 'api':
            if not self.api_endpoint:
                errors['api_endpoint'] = "API endpoint is required for API scraping."
            if not self.api_results_key:
                errors['api_results_key'] = "Results key path is required for API scraping."

        if self.detail_source == 'html' and not self.detail_container_selector:
            errors['detail_container_selector'] = (
                "Detail container selector is required when detail_source is HTML."
            )
        if self.detail_source == 'api':
            if not self.detail_api_endpoint:
                errors['detail_api_endpoint'] = (
                    "Detail API endpoint is required when detail_source is API."
                )
            if not self.api_detail_key:
                errors['api_detail_key'] = (
                    "API detail key is required when detail_source is API."
                )

        if errors:
            raise ValidationError(errors)

    def get_pagination_url(self, page: int) -> str:
        """Build the pagination URL for a specific page (legacy method)."""
        if not self.pagination_url_pattern:
            return self.base_url
        path = self.pagination_url_pattern.format(page=page)
        return self.base_url.rstrip('/') + '/' + path.lstrip('/')

    def get_absolute_url(self, path: str) -> str:
        """Build an absolute URL from a relative path (legacy method)."""
        return self.base_url.rstrip('/') + '/' + path.lstrip('/')

    def update_scrape_stats(self, count: int):
        """Update scraping statistics after a successful scrape."""
        self.last_scraped_at = timezone.now()
        self.last_scrape_count = count
        self.total_scraped_count += count
        self.save(update_fields=['last_scraped_at', 'last_scrape_count', 'total_scraped_count'])

    def get_field_selectors(self) -> dict:
        """Get all field selectors as a dictionary (legacy method)."""
        return {
            'listing_item': self.listing_item_selector,
            'position_link': self.position_link_selector,
            'position_title': self.position_title_selector,
            'position_company': self.position_company_selector,
            'detail_container': self.detail_container_selector,
        }
