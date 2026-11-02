from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CVViewSet, match_start, match_stream, match_status, match_cancel

router = DefaultRouter()
router.register(r'cvs', CVViewSet, basename='cv')

urlpatterns = [
    path('match/start/', match_start, name='match_start'),
    path('match/<str:session_key>/stream/', match_stream, name='match_stream'),
    path('match/<str:session_key>/status/', match_status, name='match_status'),
    path('match/<str:session_key>/cancel/', match_cancel, name='match_cancel'),  
    path('', include(router.urls)),
]