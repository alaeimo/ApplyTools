import json
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from apps.positions.models import Position
from .serializers import PositionSerializer
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from apps.ai.services.matcher import match_and_save

logger = logging.getLogger(__name__)

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

@csrf_exempt
@require_http_methods(["POST"])
def match_positions_stream(request):
    try:
        body = json.loads(request.body)
        cv = body.get('cv')
        language = body.get('language', 'English')
        
        if not cv:
            return StreamingHttpResponse(
                f"data: {json.dumps({'type': 'error', 'message': 'CV text is required'})}\n\n",
                content_type='text/event-stream'
            )
    except json.JSONDecodeError as e:
        return StreamingHttpResponse(
            f"data: {json.dumps({'type': 'error', 'message': f'Invalid JSON: {str(e)}'})}\n\n",
            content_type='text/event-stream'
        )
    
    def event_stream():
        try:
            positions = Position.objects.filter(status='SCRAPED', match__isnull=True).order_by('scraped_at')
            total = positions.count()
            
            if total == 0:
                yield f"data: {json.dumps({'type': 'complete', 'total': 0, 'saved': 0, 'skipped': 0, 'failed': 0, 'message': 'No positions to match'})}\n\n"
                return
            
            yield f"data: {json.dumps({'type': 'start', 'message': f'Starting match analysis for {total} positions...', 'total': total})}\n\n"
            
            saved = skipped = failed = 0
            conversation_id = None  # Store conversation ID for continuity
            
            for idx, position in enumerate(positions, 1):
                yield f"data: {json.dumps({'type': 'progress', 'message': f'Processing {idx}/{total}: {position.title[:50]}...', 'percentage': int((idx/total)*100), 'current': idx, 'total': total})}\n\n"
                
                try:
                    # Pass conversation_id if available
                    result = match_and_save(cv, position.id, language, conversation_id=conversation_id)
                    
                    # Extract conversation_id from result for next iteration
                    if result and '_metadata' in result and 'conversation_id' in result['_metadata']:
                        conversation_id = result['_metadata']['conversation_id']
                        logger.info(f"🔄 Using conversation_id: {conversation_id}")
                    
                    if 'error' in result:
                        failed += 1
                        yield f"data: {json.dumps({'type': 'position_failed', 'position_id': position.id, 'title': position.title, 'error': result.get('error', 'Unknown error'), 'saved': saved, 'skipped': skipped, 'failed': failed})}\n\n"
                    else:
                        saved += 1
                        yield f"data: {json.dumps({'type': 'position_matched', 'position_id': position.id, 'title': position.title, 'score': result.get('matching_score', {}).get('overall_score', 0), 'category': result.get('final_verdict', {}).get('match_category', 'unknown'), 'match_id': result.get('_metadata', {}).get('match_id'), 'saved': saved, 'skipped': skipped, 'failed': failed})}\n\n"
                except Exception as e:
                    failed += 1
                    yield f"data: {json.dumps({'type': 'position_failed', 'position_id': position.id, 'title': position.title, 'error': str(e), 'saved': saved, 'skipped': skipped, 'failed': failed})}\n\n"
            
            yield f"data: {json.dumps({'type': 'complete', 'total': total, 'saved': saved, 'skipped': skipped, 'failed': failed, 'summary': f'✅ {saved} matched, ⏭️ {skipped} skipped, ❌ {failed} failed (out of {total})'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response