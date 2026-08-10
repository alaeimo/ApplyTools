from rest_framework import serializers
from apps.positions.models import Position, PositionMatch


class PositionMatchSerializer(serializers.ModelSerializer):
    """Serializer for PositionMatch with readable labels and calculated fields."""
    
    # ─── Readable Labels ────────────────────────────────────────────
    match_category_label = serializers.SerializerMethodField()
    confidence_label = serializers.SerializerMethodField()
    application_recommendation_label = serializers.SerializerMethodField()
    
    # ─── Calculated Fields ──────────────────────────────────────────
    days_until_deadline = serializers.SerializerMethodField()
    is_deadline_passed = serializers.SerializerMethodField()
    is_high_match = serializers.SerializerMethodField()
    is_medium_match = serializers.SerializerMethodField()

    class Meta:
        model = PositionMatch
        fields = [
            # ─── Core Match Results ─────────────────────────────────
            'id',
            'overall_score',
            'match_category',
            'match_category_label',
            'confidence',
            'confidence_label',
            'application_recommendation',
            'application_recommendation_label',
            'summary',
            'main_reason',
            
            # ─── Position Summary ──────────────────────────────────
            'position_title',
            'institution',
            'position_type',
            'research_area',
            'main_research_objective',
            'research_methods',
            'required_skills',
            'required_background',
            'funding_and_duration',
            
            # ─── Dates ──────────────────────────────────────────────
            'application_deadline',
            'days_until_deadline',
            'is_deadline_passed',
            'start_date',
            
            # ─── Application Info ──────────────────────────────────
            'application_url',
            
            # ─── Detailed Scores ────────────────────────────────────
            'eligibility_score',
            'academic_fit_score',
            'research_fit_score',
            'technical_methodological_fit_score',
            'domain_fit_score',
            'research_experience_score',
            'competitiveness_score',
            'weighted_dimensions',
            'evidence',
            
            # ─── Calculated Flags ───────────────────────────────────
            'is_high_match',
            'is_medium_match',
            
            # ─── Metadata ───────────────────────────────────────────
            'matched_at',
        ]

    # ─── Readable Labels ────────────────────────────────────────────
    def get_match_category_label(self, obj):
        return obj.get_match_category_display()

    def get_confidence_label(self, obj):
        return obj.get_confidence_display()

    def get_application_recommendation_label(self, obj):
        return obj.get_application_recommendation_display()

    # ─── Calculated Fields ──────────────────────────────────────────
    def get_days_until_deadline(self, obj):
        if obj.application_deadline:
            from datetime import date
            return (obj.application_deadline - date.today()).days
        return None

    def get_is_deadline_passed(self, obj):
        if obj.application_deadline:
            from datetime import date
            return obj.application_deadline < date.today()
        return False

    def get_is_high_match(self, obj):
        return obj.is_high_match()

    def get_is_medium_match(self, obj):
        return obj.is_medium_match()


class PositionSerializer(serializers.ModelSerializer):
    """Serializer for Position with nested match data."""
    match = PositionMatchSerializer(read_only=True)
    status_label = serializers.SerializerMethodField()

    class Meta:
        model = Position
        fields = [
            'id',
            'title',
            'company',
            'status',
            'status_label',
            'scraped_at',
            'url',
            'match',
        ]

    def get_status_label(self, obj):
        return dict(Position.STATUS_CHOICES).get(obj.status, obj.status)