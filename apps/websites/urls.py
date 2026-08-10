# apps/websites/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WebsiteViewSet, scrape_website_stream

router = DefaultRouter()
router.register(r'websites', WebsiteViewSet, basename='website')

urlpatterns = [
    path('scrape/<int:website_id>/stream/', scrape_website_stream, name='scrape_website_stream'),
    path('', include(router.urls)),
]