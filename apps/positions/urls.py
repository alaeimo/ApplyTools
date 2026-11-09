# apps/positions/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PositionViewSet, position_detail_view, match_single_position, delete_position_match #, match_positions_stream

router = DefaultRouter()
router.register(r'positions', PositionViewSet, basename='position')

urlpatterns = [
    path('positions/<int:position_id>/match/', match_single_position, name='match_single'),
    path('positions/<int:position_id>/delete-match/', delete_position_match, name='delete_match'),
    path('positions/<int:position_id>/view/', position_detail_view, name='position_detail'),
    path('', include(router.urls)),
]
