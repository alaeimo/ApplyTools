"""Admin interface for extension tokens."""
from django.contrib import admin
from .models import ExtensionToken


@admin.register(ExtensionToken)
class ExtensionTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'is_active', 'created_at', 'last_used_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__username', 'token')
    readonly_fields = ('token', 'created_at', 'last_used_at')
    ordering = ('-created_at',)
