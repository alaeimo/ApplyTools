from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import Website


@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active_display', 'last_scrape_count', 'total_scraped_count', 'last_scraped_display', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'base_url', 'description']
    readonly_fields = ['last_scraped_at', 'last_scrape_count', 'total_scraped_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'base_url', 'is_active')
        }),
        ('Pagination', {
            'fields': ('pagination_url_pattern', 'max_pages')
        }),
        ('Selectors - Listing Page (Hierarchical)', {
            'fields': (
                'listing_item_selector',
                'position_link_selector',
                'position_title_selector',
                'position_company_selector',
            ),
            'classes': ('wide',),
            'description': (
                'These selectors are used to extract position data from the listing page. '
                'The listing_item_selector is the container for each position. '
                'Other selectors are relative to that container.'
            )
        }),
        ('Selectors - Detail Page', {
            'fields': ('detail_container_selector',),
            'classes': ('wide',),
        }),
        ('Scraping Configuration', {
            'fields': ('request_timeout', 'request_delay', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('last_scraped_at', 'last_scrape_count', 'total_scraped_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def is_active_display(self, obj):
        """Display active status with colored indicator."""
        if obj.is_active:
            return mark_safe('<span style="color: green; font-weight: bold;">🟢 Active</span>')
        return mark_safe('<span style="color: red; font-weight: bold;">🔴 Inactive</span>')
    is_active_display.short_description = 'Status'
    
    def last_scraped_display(self, obj):
        """Display last scraped time with color coding."""
        if obj.last_scraped_at:
            days_ago = (timezone.now() - obj.last_scraped_at).days
            if days_ago == 0:
                return mark_safe('<span style="color: green;">Today</span>')
            elif days_ago < 7:
                return mark_safe(f'<span style="color: orange;">{days_ago} days ago</span>')
            else:
                return mark_safe(f'<span style="color: red;">{days_ago} days ago</span>')
        return 'Never'
    last_scraped_display.short_description = 'Last Scraped'
    
    actions = ['activate_selected', 'deactivate_selected', 'reset_statistics']
    
    def activate_selected(self, request, queryset):
        """Activate selected websites."""
        count = queryset.update(is_active=True)
        self.message_user(request, f"✅ {count} website(s) activated successfully!")
    activate_selected.short_description = "Activate selected websites"
    
    def deactivate_selected(self, request, queryset):
        """Deactivate selected websites."""
        count = queryset.update(is_active=False)
        self.message_user(request, f"⚠️ {count} website(s) deactivated.")
    deactivate_selected.short_description = "Deactivate selected websites"
    
    def reset_statistics(self, request, queryset):
        """Reset statistics for selected websites."""
        count = 0
        for website in queryset:
            website.last_scrape_count = 0
            website.total_scraped_count = 0
            website.last_scraped_at = None
            website.save()
            count += 1
        self.message_user(request, f"🔄 Statistics reset for {count} website(s).")
    reset_statistics.short_description = "Reset statistics for selected websites"