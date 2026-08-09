from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import PromptTemplate

@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'version', 'default_language', 'is_active_display', 
        'created_at', 'activated_at'
    ]
    list_filter = ['is_active', 'default_language', 'created_at']
    search_fields = ['name', 'description', 'template']
    readonly_fields = ['created_at', 'updated_at', 'activated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'version', 'default_language', 'is_active')
        }),
        ('Prompt Content', {
            'fields': ('template',),
            'classes': ('wide',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'activated_at'),
            'classes': ('collapse',)
        })
    )
    
    def is_active_display(self, obj):
        """Display active status with colored indicator"""
        if obj.is_active:
            return mark_safe(
                '<span style="color: green; font-weight: bold;">✓ ACTIVE</span>'
            )
        return mark_safe(
            '<span style="color: gray;">○ inactive</span>'
        )
    is_active_display.short_description = 'Status'
    
    actions = ['activate_selected']
    
    def activate_selected(self, request, queryset):
        """Activate selected prompt (deactivates all others)"""
        if queryset.count() > 1:
            self.message_user(
                request, 
                "Please select only one prompt to activate.", 
                level='ERROR'
            )
            return
        
        prompt = queryset.first()
        if prompt:
            prompt.is_active = True
            prompt.save()
            self.message_user(
                request, 
                f"Prompt '{prompt.name}' activated successfully!"
            )
    activate_selected.short_description = "Activate selected prompt"