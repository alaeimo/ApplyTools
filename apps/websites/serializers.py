from rest_framework import serializers
from .models import Website


class WebsiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Website
        fields = '__all__'
        read_only_fields = ('last_scraped_at', 'last_scrape_count', 'total_scraped_count', 'created_at', 'updated_at')