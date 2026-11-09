"""URL routes for the browser extension API (Phase 3+)."""
from django.urls import path
from .views import (
    ExtensionTokenView,
    ExtensionAuthCheckView,
    WebsiteByURLView,
    WebsiteSelectorsView,
    WebsitePositionsBulkView,
    PositionByURLView,
    PositionMatchView,
    PositionBulkLookupView
)

urlpatterns = [
    # Token management
    path('ext/auth/token/', ExtensionTokenView.as_view(), name='ext_token_manage'),
    path('ext/auth/check/', ExtensionAuthCheckView.as_view(), name='ext_auth_check'),

    # Extension API
    path('ext/websites/by-url/', WebsiteByURLView.as_view(), name='ext_website_by_url'),
    path('ext/websites/<int:website_id>/selectors/',
         WebsiteSelectorsView.as_view(), name='ext_website_selectors'),
    path('ext/websites/<int:website_id>/positions/bulk/',
         WebsitePositionsBulkView.as_view(), name='ext_website_positions_bulk'),
    path('ext/positions/by-url/',
         PositionByURLView.as_view(), name='ext_position_by_url'),
    path('ext/positions/<int:position_id>/match/',
         PositionMatchView.as_view(), name='ext_position_match'),
     path('ext/positions/bulk-lookup/', PositionBulkLookupView.as_view(), name='ext_position_bulk_lookup'),
]
