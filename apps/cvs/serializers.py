from rest_framework import serializers
from .models import CV, MatchSession


class CVSerializer(serializers.ModelSerializer):
    text_preview = serializers.SerializerMethodField()

    class Meta:
        model = CV
        fields = [
            'id', 'name', 'content', 'file', 'file_type',
            'language', 'is_active', 'text_preview',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_text_preview(self, obj):
        text = obj.content or ''
        return text[:200] + ('...' if len(text) > 200 else '')

    def validate(self, attrs):
        """Ensure at least content or file is provided."""
        instance = self.instance
        content = attrs.get('content', getattr(instance, 'content', ''))
        file = attrs.get('file', getattr(instance, 'file', None))
        if not content and not file:
            raise serializers.ValidationError(
                "Either content or file must be provided."
            )
        return attrs


class MatchSessionSerializer(serializers.ModelSerializer):
    cv_name = serializers.CharField(source='cv.name', read_only=True)

    class Meta:
        model = MatchSession
        fields = [
            'session_key', 'cv', 'cv_name', 'language',
            'conversation_id', 'status',
            'saved', 'skipped', 'failed',
            'total_processed', 'total_positions',
            'last_position_id',
            'started_at', 'completed_at', 'error',
        ]
        read_only_fields = [
            'session_key', 'conversation_id', 'status',
            'saved', 'skipped', 'failed',
            'total_processed', 'total_positions',
            'last_position_id',
            'started_at', 'completed_at', 'error',
        ]