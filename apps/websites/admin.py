"""Django admin for Website model — updated to expose ALL fields including
API configuration, detail source, and new scraper options."""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import Website


@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'method_display',
        'is_active_display',
        'last_scrape_count',
        'total_scraped_count',
        'last_scraped_display',
        'created_at',
    ]
    list_filter = ['is_active', 'scraping_method', 'detail_source', 'created_at']
    search_fields = ['name', 'base_url', 'description', 'api_endpoint']
    readonly_fields = [
        'last_scraped_at', 'last_scrape_count', 'total_scraped_count',
        'created_at', 'updated_at',
    ]
    list_per_page = 25

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'base_url', 'is_active'),
        }),

        ('Scraping Method', {
            'fields': ('scraping_method', 'max_pages', 'request_timeout',
                       'request_delay', 'needs_js', 'max_concurrency',
                       'use_browser_fallback'),
            'description': (
                'Choose how to discover listings. '
                'For modern sites with schema.org JobPosting JSON-LD, '
                'use HTML mode with no selectors — the scraper auto-detects.'
            ),
        }),

        ('HTML Configuration', {
            'fields': (
                'pagination_url_pattern',
                'listing_item_selector',
                'position_link_selector',
                'position_title_selector',
                'position_company_selector',
            ),
            'classes': ('wide',),
            'description': (
                'CSS selectors for the listing page. '
                'listing_item_selector = container for each position. '
                'Other selectors are relative to that container. '
                '<strong>Leave blank if the site has JSON-LD JobPosting markup</strong>.'
            ),
        }),

        ('API Configuration', {
            'fields': (
                'api_endpoint',
                'api_pagination_param',
                'api_limit_param',
                'api_results_key',
                'api_next_key',
                'api_count_key',
                'api_item_url_key',
                'api_item_title_key',
                'api_item_company_key',
                'api_item_description_key',
                'api_auth_token',
                'api_extra_params',
            ),
            'classes': ('wide',),
            'description': (
                'JSON API configuration. The api_results_key uses dot-notation '
                '(e.g., "results.items") and is auto-converted to a JMESPath '
                'expression. Item URL/title/company keys are optional — '
                'sensible defaults are auto-detected.'
            ),
        }),

        ('Detail Source', {
            'fields': (
                'detail_source',
                'detail_container_selector',
                'detail_api_endpoint',
                'api_detail_key',
            ),
            'classes': ('wide',),
            'description': (
                'Where to fetch the full position description. '
                'Can differ from the listing method (e.g., list via API, '
                'detail via HTML).'
            ),
        }),

        ('Statistics', {
            'fields': ('last_scraped_at', 'last_scrape_count', 'total_scraped_count'),
            'classes': ('collapse',),
        }),

        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    # ─── Display helpers ─────────────────────────────────────

    def method_display(self, obj):
        """Show scraping_method + detail_source as badges."""
        method_color = '#0d6efd' if obj.scraping_method == 'api' else '#198754'
        detail_color = '#0d6efd' if obj.detail_source == 'api' else '#198754'
        return format_html(
            '<span style="color: white; background: {}; padding: 2px 8px; '
            'border-radius: 4px; font-size: 0.75rem;">List: {}</span> '
            '<span style="color: white; background: {}; padding: 2px 8px; '
            'border-radius: 4px; font-size: 0.75rem;">Detail: {}</span>',
            method_color, obj.scraping_method.upper(),
            detail_color, obj.detail_source.upper(),
        )
    method_display.short_description = 'Method'

    def is_active_display(self, obj):
        if obj.is_active:
            return mark_safe(
                '<span style="color: green; font-weight: bold;">🟢 Active</span>'
            )
        return mark_safe(
            '<span style="color: red; font-weight: bold;">🔴 Inactive</span>'
        )
    is_active_display.short_description = 'Status'

    def last_scraped_display(self, obj):
        if obj.last_scraped_at:
            days_ago = (timezone.now() - obj.last_scraped_at).days
            if days_ago == 0:
                return mark_safe('<span style="color: green;">Today</span>')
            elif days_ago < 7:
                return mark_safe(
                    f'<span style="color: orange;">{days_ago} days ago</span>'
                )
            else:
                return mark_safe(
                    f'<span style="color: red;">{days_ago} days ago</span>'
                )
        return 'Never'
    last_scraped_display.short_description = 'Last Scraped'

    # ─── Actions ─────────────────────────────────────────────

    actions = ['activate_selected', 'deactivate_selected', 'reset_statistics',
               'enable_browser_fallback', 'disable_browser_fallback']

    def activate_selected(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"✅ {count} website(s) activated.")
    activate_selected.short_description = "Activate selected websites"

    def deactivate_selected(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"⚠️ {count} website(s) deactivated.")
    deactivate_selected.short_description = "Deactivate selected websites"

    def reset_statistics(self, request, queryset):
        count = 0
        for website in queryset:
            website.last_scrape_count = 0
            website.total_scraped_count = 0
            website.last_scraped_at = None
            website.save()
            count += 1
        self.message_user(request, f"🔄 Statistics reset for {count} website(s).")
    reset_statistics.short_description = "Reset statistics for selected websites"

    def enable_browser_fallback(self, request, queryset):
        count = queryset.update(use_browser_fallback=True)
        self.message_user(
            request,
            f"🌐 Browser fallback enabled for {count} website(s)."
        )
    enable_browser_fallback.short_description = (
        "Enable browser fallback for selected websites"
    )

    def disable_browser_fallback(self, request, queryset):
        count = queryset.update(use_browser_fallback=False)
        self.message_user(
            request,
            f"🚫 Browser fallback disabled for {count} website(s)."
        )
    disable_browser_fallback.short_description = (
        "Disable browser fallback for selected websites"
    )
