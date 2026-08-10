# apps/api/urls.py

from django.urls import path, include

urlpatterns = [
    path('', include('apps.websites.urls')),
    path('', include('apps.positions.urls')),
]
