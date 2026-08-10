from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from apps.positions.models import Position
from .serializers import PositionSerializer


class PositionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Position data with a dashboard action."""
    queryset = Position.objects.select_related('match').all()
    serializer_class = PositionSerializer
    pagination_class = PageNumberPagination
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """
        Return positions with matches sorted by overall_score descending.
        Only positions with a match are included.
        """
        # Filter positions that have a match
        positions = Position.objects.filter(
            match__isnull=False
        ).select_related('match').order_by('-match__overall_score')

        # Optional: apply additional filters (e.g. status)
        status = request.query_params.get('status')
        if status:
            positions = positions.filter(status=status)

        # Apply pagination
        page = self.paginate_queryset(positions)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Fallback (should not happen if pagination is enabled)
        serializer = self.get_serializer(positions, many=True)
        return Response(serializer.data)