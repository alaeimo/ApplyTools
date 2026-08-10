from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import Position, PositionMatch


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'website', 'status', 'status_display', 'scraped_at']
    list_filter = ['status', 'website', 'scraped_at']
    search_fields = ['title', 'company', 'url']
    readonly_fields = ['scraped_at', 'updated_at']
    list_editable = ['status']

    fieldsets = (
        ('Basic Information', {'fields': ('website', 'url', 'title', 'company')}),
        ('Content', {'fields': ('cleaned_text',), 'classes': ('wide',)}),
        ('Status', {'fields': ('status', 'scraped_at', 'updated_at')}),
    )

    def status_display(self, obj):
        colors = {'PENDING': 'gray', 'SCRAPED': 'blue', 'PROCESSED': 'green', 'FAILED': 'red'}
        return mark_safe(f'<span style="color: {colors.get(obj.status, "black")}; font-weight: bold;">{obj.status}</span>')
    status_display.short_description = 'Status (colored)'


@admin.register(PositionMatch)
class PositionMatchAdmin(admin.ModelAdmin):
    list_display = ['position', 'overall_score_display', 'match_category_display', 'confidence_display', 'matched_at']
    list_filter = ['match_category', 'confidence', 'matched_at']
    search_fields = ['position__title', 'position__company', 'summary', 'main_reason']
    readonly_fields = ['matched_at', 'updated_at', 'full_json_response', 'raw_response']

    fieldsets = (
        ('Position', {'fields': ('position',)}),
        ('Position Summary', {
            'fields': (
                'position_title', 'institution', 'country', 'city', 'address',
                'position_type', 'research_area', 'main_research_objective',
                'key_topics', 'research_methods', 'target_application_domain',
                'required_background', 'required_skills',
                'funding_and_duration',
                'application_deadline', 'application_deadline_timezone',
                'application_deadline_iso', 'start_date', 'start_date_iso',
                'application_url', 'contact_email', 'contact_name', 'required_documents'
            ),
            'classes': ('wide', 'collapse')
        }),
        ('Candidate Profile', {
            'fields': (
                'education_background', 'research_background',
                'technical_and_methodological_skills', 'professional_experience',
                'publication_and_academic_record'
            ),
            'classes': ('wide', 'collapse')
        }),
        ('Match Scores', {
            'fields': (
                'overall_score', 'confidence',
                'eligibility_score', 'academic_fit_score', 'research_fit_score',
                'technical_methodological_fit_score', 'domain_fit_score',
                'research_experience_score', 'competitiveness_score',
                'weighted_dimensions', 'evidence'
            ),
            'classes': ('wide', 'collapse')
        }),
        ('Final Verdict', {
            'fields': ('match_category', 'application_recommendation', 'summary', 'main_reason')
        }),
        ('Metadata', {
            'fields': (
                'prompt_id', 'prompt_name', 'prompt_version',
                'language', 'raw_response', 'full_json_response'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('matched_at', 'updated_at')
        }),
    )

    def overall_score_display(self, obj):
        score = float(obj.overall_score)
        color = 'green' if score >= 80 else 'orange' if score >= 50 else 'red'
        return mark_safe(f'<span style="color: {color}; font-weight: bold;">{score:.1f}%</span>')
    overall_score_display.short_description = 'Score'

    def match_category_display(self, obj):
        colors = {'excellent_match': 'green', 'good_match': 'blue', 'possible_match': 'orange', 'weak_match': 'red', 'error': 'gray'}
        color = colors.get(obj.match_category, 'black')
        return mark_safe(f'<span style="color: {color}; font-weight: bold;">{obj.get_match_category_display()}</span>')
    match_category_display.short_description = 'Category'

    def confidence_display(self, obj):
        icons = {'high': '🟢', 'medium': '🟡', 'low': '🔴'}
        return mark_safe(f'{icons.get(obj.confidence, "⚪")} {obj.get_confidence_display()}')
    confidence_display.short_description = 'Confidence'