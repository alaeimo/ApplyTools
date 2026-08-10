# apps/api/urls.py

from django.urls import path, include

urlpatterns = [
    # path('v1/websites/', include('apps.websites.urls')),
    path('v1/', include('apps.positions.urls')),
]
