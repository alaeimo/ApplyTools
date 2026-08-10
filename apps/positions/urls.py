# apps/positions/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PositionViewSet, match_positions_stream

router = DefaultRouter()
router.register(r'positions', PositionViewSet, basename='position')

urlpatterns = [
    path('match/stream/', match_positions_stream, name='match_positions_stream'),
    path('', include(router.urls)),
]
