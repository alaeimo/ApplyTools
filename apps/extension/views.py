"""Views for the browser extension API endpoints (Phase 3+)."""
import logging
from urllib.parse import urlparse
from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.websites.models import Website
from apps.positions.models import Position, PositionMatch

from .authentication import ExtensionTokenAuthentication
from .models import ExtensionToken

logger = logging.getLogger(__name__)


# ─── Token management (session-authenticated) ────────────────────

class ExtensionTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = ExtensionToken.for_user(request.user)
        return Response({
            'token': token.token,
            'created_at': token.created_at.isoformat(),
            'message': 'Token generated.',
        }, status=status.HTTP_201_CREATED)

    def get(self, request):
        token = ExtensionToken.objects.filter(
            user=request.user, is_active=True
        ).first()
        if not token:
            return Response({'has_token': False})
        return Response({
            'has_token': True,
            'created_at': token.created_at.isoformat(),
            'last_used_at': token.last_used_at.isoformat() if token.last_used_at else None,
        })

    def delete(self, request):
        ExtensionToken.objects.filter(user=request.user).delete()
        return Response({'message': 'Token revoked.'}, status=200)


# ─── Extension API (token-authenticated) ─────────────────────────

class ExtensionAuthCheckView(APIView):
    authentication_classes = [ExtensionTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'authenticated': True,
            'user': request.user.username,
            'user_id': request.user.id,
        })


class WebsiteByURLView(APIView):
    """Look up a Website by URL (matches by domain).

    FIX: Returns ALL saved selectors so the extension can load its state
    when navigating between listing and detail pages.
    """

    authentication_classes = [ExtensionTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        url = request.query_params.get('url')
        if not url:
            return Response({'error': 'url parameter required'}, status=400)

        try:
            parsed = urlparse(url)
            domain = (parsed.netloc or '').lower()
            if ':' in domain:
                domain = domain.split(':')[0]
            if domain.startswith('www.'):
                domain = domain[4:]
            if not domain:
                return Response({'found': False})
        except Exception:
            return Response({'found': False})

        websites = Website.objects.filter(is_active=True)
        for website in websites:
            try:
                website_parsed = urlparse(website.base_url or '')
                website_domain = (website_parsed.netloc or '').lower()
                if ':' in website_domain:
                    website_domain = website_domain.split(':')[0]
                if website_domain.startswith('www.'):
                    website_domain = website_domain[4:]
                if not website_domain:
                    continue
                if domain == website_domain or domain.endswith('.' + website_domain):
                    
                    # FIX: Return all selector fields to the extension
                    return Response({
                        'found': True,
                        'id': website.id,
                        'name': website.name,
                        'base_url': website.base_url,
                        'has_selectors': bool(website.listing_item_selector),
                        'listing_css': website.listing_item_selector or '',
                        'title_css': website.position_title_selector or '',
                        'link_css': website.position_link_selector or '',
                        'company_css': website.position_company_selector or '',
                        'detail_container_css': website.detail_container_selector or '',
                        'pagination_url_pattern': website.pagination_url_pattern or '',
                    })
            except Exception:
                continue

        return Response({'found': False})


class WebsiteSelectorsView(APIView):
    """Save selectors chosen via the extension's picker.

    POST /api/v1/ext/websites/{id}/selectors/
    """

    authentication_classes = [ExtensionTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, website_id):
        try:
            website = Website.objects.get(id=website_id)
        except Website.DoesNotExist:
            raise Http404

        # Map extension payload keys → Website model fields
        key_map = {
            'listing_css': 'listing_item_selector',
            'link_css': 'position_link_selector',
            'title_css': 'position_title_selector',
            'company_css': 'position_company_selector',
            'detail_container_css': 'detail_container_selector',
        }
        
        updated = []
        for ext_key, model_field in key_map.items():
            # Only update if the key is explicitly provided in the request
            if ext_key in request.data:
                val = request.data.get(ext_key)
                setattr(website, model_field, val)
                updated.append(model_field)

        if updated:
            website.save(update_fields=updated)

        return Response({
            'status': 'ok',
            'website_id': website.id,
            'updated_fields': updated,
            'message': 'Saved ' + str(len(updated)) + ' selectors for "' + website.name + '"',
        })


class WebsitePositionsBulkView(APIView):
    """Receive a batch of extracted positions from the extension.

    POST /api/v1/ext/websites/{id}/positions/bulk/
    """

    authentication_classes = [ExtensionTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, website_id):
        try:
            website = Website.objects.get(id=website_id)
        except Website.DoesNotExist:
            raise Http404

        positions_data = request.data.get('positions', [])
        if not positions_data:
            return Response({
                'status': 'ok', 'saved': 0, 'skipped': 0, 'message': 'No positions sent'
            })

        saved = 0
        skipped = 0
        errors = []

        for pos_data in positions_data:
            url = pos_data.get('url')
            if not url:
                errors.append({'error': 'Missing URL', 'data': pos_data})
                continue
            _, created = Position.objects.get_or_create(
                website=website,
                url=url,
                defaults={
                    'title': pos_data.get('title', 'Unknown Title'),
                    'company': pos_data.get('company', ''),
                    'cleaned_text': pos_data.get('cleaned_text', ''),
                    'status': 'SCRAPED',
                }
            )
            if created:
                saved += 1
            else:
                skipped += 1

        if saved:
            website.last_scraped_at = timezone.now()
            website.last_scrape_count = saved
            website.total_scraped_count = (website.total_scraped_count or 0) + saved
            website.save(update_fields=['last_scraped_at', 'last_scrape_count', 'total_scraped_count'])

        return Response({
            'status': 'ok',
            'saved': saved,
            'skipped': skipped,
            'errors': errors[:5],
            'message': str(saved) + ' new, ' + str(skipped) + ' duplicates',
        })


class PositionByURLView(APIView):
    """Lookup a position by its URL.

    GET /api/v1/ext/positions/by-url/?url=https://...
    """

    authentication_classes = [ExtensionTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        url = request.query_params.get('url')
        if not url:
            return Response({'error': 'url parameter required'}, status=400)

        try:
            position = Position.objects.select_related('match').get(url=url)
        except Position.DoesNotExist:
            return Response({'found': False, 'message': 'Position not in ApplyTools'})

        match = getattr(position, 'match', None)
        return Response({
            'found': True,
            'id': position.id,
            'title': position.title,
            'company': position.company,
            'status': position.status,
            'application_status': position.application_status,
            'has_match': match is not None,
            'match_score': match.overall_score if match else None,
            'match_category': match.match_category if match else None,
            'match_summary': match.summary if match else None,
            'dashboard_url': '/api/v1/positions/' + str(position.id) + '/',
        })


# ─── Phase 2: Bulk URL lookup (for listing page badges) ─────────

class PositionBulkLookupView(APIView):
    """Check multiple URLs at once to see if they are saved positions."""
    authentication_classes = [ExtensionTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        urls = request.data.get('urls', [])
        if not urls:
            return Response({'results': []})

        # Find all matching positions in one query
        positions = Position.objects.filter(url__in=urls).select_related('match')
        results = {}
        for pos in positions:
            match = getattr(pos, 'match', None)
            results[pos.url] = {
                'found': True,
                'id': pos.id,
                'title': pos.title,
                'application_status': pos.application_status,
                'has_match': match is not None,
                'match_score': match.overall_score if match else None,
                'match_category': match.match_category if match else None,
            }
        
        # Return results in the same order as requested
        response_list = []
        for url in urls:
            if url in results:
                response_list.append(results[url])
            else:
                response_list.append({'url': url, 'found': False})
                
        return Response({'results': response_list})


# ─── Phase 5: Match trigger ────────────────────────────────────

class PositionMatchView(APIView):
    """Trigger a DeepSeek match for a position via the extension.

    POST /api/v1/ext/positions/{id}/match/
    """

    authentication_classes = [ExtensionTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, position_id):
        try:
            position = Position.objects.get(id=position_id)
        except Position.DoesNotExist:
            raise Http404

        # Check if already matched
        if hasattr(position, 'match') and position.match:
            return Response({
                'status': 'already_matched',
                'match_score': position.match.overall_score,
                'match_category': position.match.match_category,
                'message': 'Position already has a match.',
            })

        # Trigger match asynchronously (simplified — in production, use Celery)
        try:
            from apps.ai.services.matcher import match_and_save
            # Get the latest CV
            from apps.cvs.models import CV
            cv = CV.objects.filter(is_active=True).first()
            if not cv:
                return Response({'error': 'No active CV found. Create one in ApplyTools.'}, status=400)

            result = match_and_save(cv.get_text(), position.id, 'English')
            return Response({
                'status': 'ok',
                'match_score': result.get('matching_score', {}).get('overall_score', 0),
                'match_category': result.get('final_verdict', {}).get('match_category', 'unknown'),
                'message': 'Match completed.',
            })
        except Exception as e:
            logger.exception("Extension match failed")
            return Response({'error': str(e)}, status=500)