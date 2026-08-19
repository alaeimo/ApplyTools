from django.db import models
from django.core.validators import URLValidator
from django.utils import timezone


class Website(models.Model):
    """Website configuration for scraping positions."""
    SCRAPING_METHOD_CHOICES = [
        ('html', 'HTML Scraping'),
        ('api', 'API Scraping'),
    ]
    # Basic Information
    name = models.CharField(max_length=200, unique=True, help_text="Name of the website")
    description = models.TextField(blank=True, help_text="Optional description of the website")
    
    # URL Configuration
    base_url = models.URLField(max_length=500, blank=True, validators=[URLValidator()], help_text="Base URL of the website")
    pagination_url_pattern = models.CharField(max_length=500, blank=True, help_text="URL pattern with {page} placeholder")
    
    # Selectors for Scraping
    listing_item_selector = models.CharField(max_length=500, blank=True, help_text="CSS selector for each position container (e.g., '.job-list-item', '.job-card')")
    position_link_selector = models.CharField(max_length=500, blank=True, help_text="CSS selector for position link within the container (e.g., 'a.job-link', '.title a')")
    position_title_selector = models.CharField(max_length=500, blank=True, help_text="CSS selector for position title within the container (e.g., 'h4', '.job-title')")
    position_company_selector = models.CharField(max_length=500, blank=True, help_text="CSS selector for company name within the container (e.g., '.company', '.employer')")
    
    detail_container_selector = models.CharField(max_length=500, blank=True, help_text="CSS selector for detail container")

    # Scraping Configuration
    max_pages = models.IntegerField(default=0, help_text="Maximum pages to scrape per run - 0: Unlimited")
    request_timeout = models.IntegerField(default=30, help_text="Request timeout in seconds")
    request_delay = models.FloatField(default=1.0, help_text="Delay between requests in seconds")
    user_agent = models.CharField(max_length=500, default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", help_text="User agent string")
    
    # Status & Metadata
    is_active = models.BooleanField(default=True, help_text="Whether this website is active for scraping")
    is_enabled = models.BooleanField(default=True, help_text="Alias for is_active")
    last_scraped_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of the last successful scrape")
    last_scrape_count = models.IntegerField(default=0, help_text="Number of positions scraped in the last run")
    total_scraped_count = models.IntegerField(default=0, help_text="Total number of positions scraped from this website")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    scraping_method = models.CharField(max_length=10, choices=SCRAPING_METHOD_CHOICES, default='html', help_text="Select whether to scrape HTML pages or use a JSON API.")

    api_endpoint = models.URLField(max_length=500, blank=True, help_text="Full API endpoint URL (e.g., https://api.example.com/v1/jobs/)")
    api_pagination_param = models.CharField(max_length=50, blank=True, default='page', help_text="Query parameter name for page number (e.g., 'page', 'offset')")
    api_limit_param = models.CharField(max_length=50, blank=True, default='limit', help_text="Query parameter name for items per page (e.g., 'limit', 'per_page')")
    api_results_key = models.CharField(max_length=100, blank=True, default='results', help_text="JSON key where the list of items is located (e.g., 'results', 'data.items')")
    api_next_key = models.CharField(max_length=100, blank=True, help_text="JSON key for the next page URL (if provided by the API)")
    api_count_key = models.CharField(max_length=100, blank=True, help_text="JSON key for the total count of items (if provided)")
    api_item_url_key = models.CharField(max_length=100, blank=True, help_text="JSON key for the position URL (e.g., 'absolute_url', 'link.url')")
    api_item_title_key = models.CharField(max_length=100, blank=True, help_text="JSON key for the position title (e.g., 'title', 'headline')")
    api_item_company_key = models.CharField(max_length=100, blank=True, help_text="JSON key for the company/organization (e.g., 'organisation_name', 'subline')")
    api_item_description_key = models.CharField(max_length=100, blank=True, help_text="JSON key for the description/cleaned text (if included in listing)")
    api_auth_token = models.CharField(max_length=500, blank=True, help_text="Bearer token or API key for authentication (if required)")
    api_extra_params = models.JSONField(default=dict, blank=True, help_text="Additional static query parameters as a JSON object, e.g., {'boost_spotlights': True, 'is_active': True}")
    detail_source = models.CharField(max_length=10, choices=SCRAPING_METHOD_CHOICES, default='html')
    detail_api_endpoint = models.URLField(max_length=500, blank=True, help_text="Detail API endpoint URL (e.g., https://api.example.com/v1/jobs/)")
    api_detail_key = models.CharField(max_length=100, blank=True, help_text="JSON key for the full description/cleaned text in the API detail response. If blank, falls back to api_item_description_key from listing.")

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['last_scraped_at']),
            models.Index(fields=['name', 'is_active']),
        ]
        verbose_name = "Website"
        verbose_name_plural = "Websites"
    
    def __str__(self):
        return self.name
    
    def get_pagination_url(self, page: int) -> str:
        """Build the pagination URL for a specific page."""
        path = self.pagination_url_pattern.format(page=page)
        return self.base_url.rstrip('/') + '/' + path.lstrip('/')
    
    def get_absolute_url(self, path: str) -> str:
        """Build an absolute URL from a relative path."""
        return self.base_url.rstrip('/') + '/' + path.lstrip('/')
    
    def update_scrape_stats(self, count: int):
        """Update scraping statistics after a successful scrape."""
        self.last_scraped_at = timezone.now()
        self.last_scrape_count = count
        self.total_scraped_count += count
        self.save(update_fields=['last_scraped_at', 'last_scrape_count', 'total_scraped_count'])
    
    def get_field_selectors(self) -> dict:
        """Get all field selectors as a dictionary."""
        return {
            'listing_item': self.listing_item_selector,
            'position_link': self.position_link_selector,
            'position_title': self.position_title_selector,
            'position_company': self.position_company_selector,
            'detail_container': self.detail_container_selector,
        }