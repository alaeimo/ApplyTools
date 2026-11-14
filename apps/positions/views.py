import json
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Case, When, F, FloatField
from apps.positions.models import Position
from .serializers import PositionSerializer
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from apps.ai.services.matcher import match_and_save
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

logger = logging.getLogger(__name__)


class PositionViewSet(viewsets.ModelViewSet):
    """ViewSet for Position data with dashboard + heatmap-stats actions."""
    queryset = Position.objects.select_related('match').all()
    serializer_class = PositionSerializer
    pagination_class = PageNumberPagination
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """List positions with view filter, optional discovery filters (search,
        deadline_date, no_deadline, score_buckets), and sort override."""
        view = request.query_params.get('view', 'pending')
        app_status = request.query_params.get('app_status')
        search = request.query_params.get('search', '').strip()
        deadline_date = request.query_params.get('deadline_date', '').strip()
        no_deadline = request.query_params.get('no_deadline', '').strip().lower() == 'true'
        score_buckets_param = request.query_params.get('score_buckets', '').strip()
        sort = request.query_params.get('sort', '').strip()

        positions = Position.objects.select_related('match')

        # ── View filter (same as before) ──────────────────────
        if view == 'pending':
            positions = positions.filter(application_status='PENDING_REVIEW')
            status_filter = request.query_params.get('status')
            if status_filter:
                positions = positions.filter(status=status_filter)
            positions = positions.order_by(
                Case(When(match__isnull=False, then=F('match__overall_score')), default=0, output_field=FloatField()).desc(),
                '-scraped_at'
            )
        elif view == 'shortlisted':
            shortlisted_statuses = ['SHORTLISTED', 'APPLIED', 'INTERVIEWING', 'OFFERED', 'ACCEPTED', 'REJECTED', 'DEADLINE_MISSED']
            positions = positions.filter(application_status__in=shortlisted_statuses)
            if app_status:
                positions = positions.filter(application_status=app_status)
            positions = positions.order_by('match__application_deadline_iso', 'match__application_deadline', '-scraped_at')
        elif view == 'not_interested':
            positions = positions.filter(application_status='NOT_INTERESTED')
        elif view == 'bookmarked': 
            positions = positions.filter(is_bookmarked=True)
            positions = positions.order_by('-bookmarked_at')
        else:
            positions = positions.all()

        # ── Discovery filters (NEW) ──────────────────────────
        if search:
            positions = positions.filter(
                Q(title__icontains=search) |
                Q(company__icontains=search) |
                Q(match__summary__icontains=search) |
                Q(match__main_reason__icontains=search) |
                Q(match__institution__icontains=search)
            )

        if deadline_date:
            positions = positions.filter(
                Q(match__application_deadline_iso__startswith=deadline_date)
            )

        if no_deadline:
            positions = positions.filter(
                Q(match__isnull=True) |
                Q(match__application_deadline_iso__isnull=True) |
                Q(match__application_deadline_iso='')
            )

        if score_buckets_param:
            buckets = [b.strip() for b in score_buckets_param.split(',') if b.strip()]
            score_q = Q()
            for b in buckets:
                if b == 'no-match':
                    score_q |= Q(match__isnull=True)
                elif b == '0-20':
                    score_q |= Q(match__overall_score__gte=0, match__overall_score__lt=20)
                elif b == '20-40':
                    score_q |= Q(match__overall_score__gte=20, match__overall_score__lt=40)
                elif b == '40-60':
                    score_q |= Q(match__overall_score__gte=40, match__overall_score__lt=60)
                elif b == '60-80':
                    score_q |= Q(match__overall_score__gte=60, match__overall_score__lt=80)
                elif b == '80-100':
                    score_q |= Q(match__overall_score__gte=80)
            positions = positions.filter(score_q)

        # ── Sort override (NEW) ───────────────────────────────
        if sort == 'score':
            positions = positions.order_by(
                Case(When(match__isnull=False, then=F('match__overall_score')), default=0, output_field=FloatField()).desc(),
                '-scraped_at'
            )
        elif sort == 'deadline':
            positions = positions.order_by('match__application_deadline_iso', 'match__application_deadline', '-scraped_at')

        # ── Paginate ─────────────────────────────────────────
        page = self.paginate_queryset(positions)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(positions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='heatmap-stats')
    def heatmap_stats(self, request):
        """Return aggregate counts for the heatmap and score distribution.
        Computed over ALL positions in the current view (NOT paginated).
        Used by the discovery panel on the dashboard."""
        view = request.query_params.get('view', 'pending')
        app_status = request.query_params.get('app_status')
        status_filter = request.query_params.get('status')

        positions = Position.objects.select_related('match')

        # Apply same view filter as dashboard (so heatmap reflects current view)
        if view == 'pending':
            positions = positions.filter(application_status='PENDING_REVIEW')
            if status_filter:
                positions = positions.filter(status=status_filter)
        elif view == 'shortlisted':
            shortlisted_statuses = ['SHORTLISTED', 'APPLIED', 'INTERVIEWING', 'OFFERED', 'ACCEPTED', 'REJECTED', 'DEADLINE_MISSED']
            positions = positions.filter(application_status__in=shortlisted_statuses)
            if app_status:
                positions = positions.filter(application_status=app_status)
        elif view == 'not_interested':
            positions = positions.filter(application_status='NOT_INTERESTED')
        elif view == 'bookmarked':
            positions = positions.filter(is_bookmarked=True)

        deadline_counts = {}
        no_deadline_count = 0
        score_counts = {'0-20': 0, '20-40': 0, '40-60': 0, '60-80': 0, '80-100': 0, 'no-match': 0}

        for pos in positions:
            m = getattr(pos, 'match', None)
            dl = None
            if m:
                if m.application_deadline_iso:
                    dl = m.application_deadline_iso[:10]
                elif getattr(m, 'application_deadline', None):
                    dl = str(m.application_deadline)[:10]

            if dl:
                deadline_counts[dl] = deadline_counts.get(dl, 0) + 1
            else:
                no_deadline_count += 1

            score = getattr(m, 'overall_score', None) if m else None
            if score is None:
                score_counts['no-match'] += 1
            elif score < 20:
                score_counts['0-20'] += 1
            elif score < 40:
                score_counts['20-40'] += 1
            elif score < 60:
                score_counts['40-60'] += 1
            elif score < 80:
                score_counts['60-80'] += 1
            else:
                score_counts['80-100'] += 1

        return Response({
            'deadline_counts': deadline_counts,
            'no_deadline_count': no_deadline_count,
            'score_counts': score_counts,
            'total': sum(score_counts.values()),
        })

    @action(detail=False, methods=['get'], url_path='counts')
    def counts(self, request):
        counts = {
            'pending': Position.objects.filter(application_status='PENDING_REVIEW').count(),
            'shortlisted': Position.objects.filter(
                application_status__in=['SHORTLISTED', 'APPLIED', 'INTERVIEWING', 'OFFERED', 'ACCEPTED', 'REJECTED', 'DEADLINE_MISSED']
            ).count(),
            'not_interested': Position.objects.filter(application_status='NOT_INTERESTED').count(),
            'bookmarked': Position.objects.filter(is_bookmarked=True).count(),  # NEW
        }
        return Response(counts)

    @action(detail=True, methods=['post'], url_path='pending-review')
    def pending_review(self, request, pk=None):
        position = self.get_object()
        position.application_status = 'PENDING_REVIEW'
        position.save(update_fields=['application_status', 'updated_at'])
        return Response({'status': 'pending_review'})

    @action(detail=True, methods=['post'], url_path='shortlist')
    def shortlist(self, request, pk=None):
        position = self.get_object()
        position.mark_shortlisted()
        return Response({'status': 'shortlisted', 'shortlisted_at': position.shortlisted_at})

    @action(detail=True, methods=['post'], url_path='apply')
    def apply(self, request, pk=None):
        position = self.get_object()
        position.mark_applied()
        return Response({'status': 'applied', 'applied_at': position.applied_at})

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        position = self.get_object()
        reason = request.data.get('reason')
        position.mark_rejected(reason)
        return Response({'status': 'rejected', 'rejection_reason': position.rejection_reason})

    @action(detail=True, methods=['post'], url_path='accept')
    def accept(self, request, pk=None):
        position = self.get_object()
        position.mark_accepted()
        return Response({'status': 'accepted'})

    @action(detail=True, methods=['post'], url_path='not-interested')
    def not_interested(self, request, pk=None):
        position = self.get_object()
        position.mark_not_interested()
        return Response({'status': 'not_interested'})
    
    @action(detail=True, methods=['post'], url_path='bookmark')
    def bookmark(self, request, pk=None):
        """Toggle the bookmark state of a position."""
        position = self.get_object()
        position.toggle_bookmark()
        return Response({
            'status': 'bookmarked' if position.is_bookmarked else 'unbookmarked',
            'is_bookmarked': position.is_bookmarked
        })
    
    @action(detail=False, methods=['post'], url_path='check-deadlines')
    def check_deadlines(self, request):
        today_str = timezone.now().date().isoformat()
        active_statuses = ['PENDING_REVIEW', 'SHORTLISTED']
        expired = Position.objects.select_related('match').filter(
            match__isnull=False,
            application_status__in=active_statuses
        ).filter(
            Q(match__application_deadline_iso__isnull=False) &
            ~Q(match__application_deadline_iso='') &
            Q(match__application_deadline_iso__lt=today_str + 'T')
        )
        count = expired.count()
        expired.update(application_status='DEADLINE_MISSED', updated_at=timezone.now())
        return Response({
            'updated': count,
            'message': f'Updated {count} positions to DEADLINE_MISSED'
        })


@csrf_exempt
@require_http_methods(["POST"])
def match_single_position(request, position_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    try:
        body = json.loads(request.body or "{}")
        cv_id = body.get('cv_id')
        language = body.get('language', 'English')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not cv_id:
        return JsonResponse({'error': 'cv_id is required'}, status=422)

    try:
        from apps.positions.models import Position
        from apps.cvs.models import CV
        from apps.ai.services.matcher import match_and_save

        position = Position.objects.get(id=position_id)
        cv = CV.objects.get(id=cv_id, is_active=True)
        cv_text = cv.get_text()

        if not cv_text:
            return JsonResponse({'error': 'CV has no text content'}, status=400)

        result = match_and_save(cv_text, position.id, language)

        return JsonResponse({
            'status': 'ok',
            'saved': result.get('_metadata', {}).get('status') == 'success',
            'match_score': result.get('matching_score', {}).get('overall_score', 0),
            'match_category': result.get('final_verdict', {}).get('match_category', 'unknown'),
            'summary': result.get('final_verdict', {}).get('summary', ''),
            'error': result.get('error'),
        })

    except Position.DoesNotExist:
        return JsonResponse({'error': 'Position not found'}, status=404)
    except CV.DoesNotExist:
        return JsonResponse({'error': 'CV not found'}, status=404)
    except Exception as e:
        logger.exception("Single position match failed")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE", "POST"])
def delete_position_match(request, position_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    try:
        from apps.positions.models import Position, PositionMatch

        position = Position.objects.get(id=position_id)

        if hasattr(position, 'match') and position.match:
            position.match.delete()
            position.status = 'SCRAPED'
            position.save(update_fields=['status'])
            return JsonResponse({'status': 'ok', 'message': 'Match deleted. Position ready for re-matching.'})
        else:
            return JsonResponse({'status': 'ok', 'message': 'No match to delete.'})

    except Position.DoesNotExist:
        return JsonResponse({'error': 'Position not found'}, status=404)
    except Exception as e:
        logger.exception("Delete match failed")
        return JsonResponse({'error': str(e)}, status=500)


def position_detail_view(request, position_id):
    """Render a full-page view of a single position and its match details."""
    position = get_object_or_404(Position, id=position_id)
    match = getattr(position, 'match', None)
    
    # Calculate days until deadline for the badge logic
    if match and match.application_deadline_iso:
        try:
            from datetime import date
            deadline_date = date.fromisoformat(match.application_deadline_iso[:10])
            today = date.today()
            match.days_until_deadline = (deadline_date - today).days
        except (ValueError, TypeError):
            match.days_until_deadline = None
    
    context = {
        'position': position,
        'match': match,
    }
    return render(request, 'position_detail.html', context)