# from django.contrib import admin
# from django.utils.html import format_html
# from django.db.models import Avg
# from .models import Position, PositionMatch


# @admin.register(Position)
# class PositionAdmin(admin.ModelAdmin):
#     list_display = ['title', 'company', 'website', 'status', 'scraped_at']
#     list_filter = ['status', 'website', 'scraped_at']
#     search_fields = ['title', 'company', 'url']
#     readonly_fields = ['scraped_at', 'updated_at']
#     list_editable = ['status']
    
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('website', 'url', 'title', 'company')
#         }),
#         ('Content', {
#             'fields': ('raw_html', 'cleaned_text'),
#             'classes': ('wide',)
#         }),
#         ('Status', {
#             'fields': ('status', 'scraped_at', 'updated_at')
#         })
#     )


# @admin.register(PositionMatch)
# class PositionMatchAdmin(admin.ModelAdmin):
#     list_display = [
#         'position', 'overall_score_display', 'match_category_display', 
#         'confidence_display', 'matched_at'
#     ]
#     list_filter = ['match_category', 'confidence', 'matched_at']
#     search_fields = ['position__title', 'position__company', 'summary', 'main_reason']
#     readonly_fields = ['matched_at', 'updated_at', 'full_json_response']
    
#     fieldsets = (
#         ('Position', {
#             'fields': ('position',)
#         }),
#         ('Position Summary', {
#             'fields': (
#                 'position_title', 'institution', 'country', 'position_type',
#                 'research_area', 'main_research_objective', 'key_topics',
#                 'required_background', 'required_skills', 'preferred_skills',
#                 'funding_and_duration'
#             ),
#             'classes': ('wide', 'collapse')
#         }),
#         ('Candidate Profile', {
#             'fields': (
#                 'education_background', 'research_background',
#                 'technical_and_methodological_skills', 'professional_experience',
#                 'publication_and_academic_record'
#             ),
#             'classes': ('wide', 'collapse')
#         }),
#         ('Match Scores', {
#             'fields': (
#                 'overall_score', 'confidence',
#                 'academic_fit_score', 'research_fit_score', 'competitiveness_score'
#             )
#         }),
#         ('Final Verdict', {
#             'fields': ('match_category', 'summary', 'main_reason')
#         }),
#         ('Metadata', {
#             'fields': (
#                 'prompt_id', 'prompt_name', 'prompt_version', 'language',
#                 'raw_response', 'full_json_response'
#             ),
#             'classes': ('collapse',)
#         }),
#         ('Timestamps', {
#             'fields': ('matched_at', 'updated_at')
#         })
#     )
    
#     def overall_score_display(self, obj):
#         """Display overall score with color coding."""
#         score = obj.overall_score
#         if score >= 80:
#             color = 'green'
#         elif score >= 60:
#             color = 'orange'
#         else:
#             color = 'red'
#         return format_html(
#             '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
#             color, score
#         )
#     overall_score_display.short_description = 'Score'
    
#     def match_category_display(self, obj):
#         """Display match category with badge."""
#         colors = {
#             'excellent_match': 'green',
#             'good_match': 'blue',
#             'possible_match': 'orange',
#             'weak_match': 'red',
#             'error': 'gray'
#         }
#         color = colors.get(obj.match_category, 'gray')
#         return format_html(
#             '<span style="color: {}; font-weight: bold;">{}</span>',
#             color, obj.get_match_category_display()
#         )
#     match_category_display.short_description = 'Category'
    
#     def confidence_display(self, obj):
#         """Display confidence with indicator."""
#         icons = {
#             'high': '🟢',
#             'medium': '🟡',
#             'low': '🔴'
#         }
#         icon = icons.get(obj.confidence, '⚪')
#         return format_html('{} {}', icon, obj.get_confidence_display())
#     confidence_display.short_description = 'Confidence'