# apps/api/urls.py

from django.urls import path, include

urlpatterns = [
    path('v1/websites/', include('apps.websites.urls')),
    path('v1/positions/', include('apps.positions.urls')),
]