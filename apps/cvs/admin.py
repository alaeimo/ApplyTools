from django.contrib import admin
from .models import CV, MatchSession


@admin.register(CV)
class CVAdmin(admin.ModelAdmin):
    list_display = ['name', 'language', 'file_type', 'is_active', 'created_at']
    list_filter = ['language', 'file_type', 'is_active']
    search_fields = ['name', 'content']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 25


@admin.register(MatchSession)
class MatchSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_key', 'cv', 'language', 'status',
        'saved', 'failed', 'total_processed', 'total_positions',
        'started_at',
    ]
    list_filter = ['status', 'language']
    search_fields = ['session_key', 'cv__name', 'conversation_id']
    readonly_fields = [
        'session_key', 'started_at', 'completed_at',
        'saved', 'skipped', 'failed', 'total_processed', 'total_positions',
        'last_position_id', 'conversation_id',
    ]
    list_per_page = 25