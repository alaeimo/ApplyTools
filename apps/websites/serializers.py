"""DRF serializer for Website model.

Security fix: api_auth_token is now write_only (never exposed in API responses).
Validation: ensures HTML sites have required HTML fields, API sites have api_endpoint.
"""
from rest_framework import serializers
from .models import Website


class WebsiteSerializer(serializers.ModelSerializer):
    """Serializer for Website CRUD operations.

    Security:
      - api_auth_token is write_only — never returned in GET responses.

    Validation:
      - HTML sites must have base_url and listing selectors.
      - API sites must have api_endpoint.
      - detail_source='html' requires detail_container_selector.
      - detail_source='api' requires detail_api_endpoint + api_detail_key.
    """

    api_auth_token = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        style={'input_type': 'password'},
        help_text="Bearer token (write-only — never returned in responses)",
    )
    api_extra_params = serializers.JSONField(required=False, default=dict)

    class Meta:
        model = Website
        fields = '__all__'
        read_only_fields = (
            'last_scraped_at',
            'last_scrape_count',
            'total_scraped_count',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        """Cross-field validation for HTML/API consistency."""
        # Use the instance's current values for fields not in attrs (partial updates)
        instance = self.instance
        scraping_method = attrs.get('scraping_method', getattr(instance, 'scraping_method', 'html'))
        detail_source = attrs.get('detail_source', getattr(instance, 'detail_source', 'html'))

        errors = {}

        if scraping_method == 'html':
            base_url = attrs.get('base_url', getattr(instance, 'base_url', ''))
            listing_selector = attrs.get(
                'listing_item_selector',
                getattr(instance, 'listing_item_selector', ''),
            )
            link_selector = attrs.get(
                'position_link_selector',
                getattr(instance, 'position_link_selector', ''),
            )
            if not base_url:
                errors.setdefault('base_url', []).append("Required for HTML scraping.")
            if not listing_selector:
                errors.setdefault('listing_item_selector', []).append(
                    "Required for HTML scraping."
                )
            if not link_selector:
                errors.setdefault('position_link_selector', []).append(
                    "Required for HTML scraping."
                )

        elif scraping_method == 'api':
            api_endpoint = attrs.get('api_endpoint', getattr(instance, 'api_endpoint', ''))
            api_results_key = attrs.get(
                'api_results_key', getattr(instance, 'api_results_key', ''),
            )
            if not api_endpoint:
                errors.setdefault('api_endpoint', []).append("Required for API scraping.")
            if not api_results_key:
                errors.setdefault('api_results_key', []).append(
                    "Required for API scraping."
                )

        if detail_source == 'html':
            detail_container = attrs.get(
                'detail_container_selector',
                getattr(instance, 'detail_container_selector', ''),
            )
            if not detail_container:
                errors.setdefault('detail_container_selector', []).append(
                    "Required when detail_source is HTML."
                )
        elif detail_source == 'api':
            detail_api = attrs.get(
                'detail_api_endpoint',
                getattr(instance, 'detail_api_endpoint', ''),
            )
            api_detail_key = attrs.get(
                'api_detail_key', getattr(instance, 'api_detail_key', ''),
            )
            if not detail_api:
                errors.setdefault('detail_api_endpoint', []).append(
                    "Required when detail_source is API."
                )
            if not api_detail_key:
                errors.setdefault('api_detail_key', []).append(
                    "Required when detail_source is API."
                )

        if errors:
            raise serializers.ValidationError(errors)

        return attrs
